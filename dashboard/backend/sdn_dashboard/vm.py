"""SSH access to the Mininet VM.

Every command is a fixed argument list executed through the OpenSSH client with
BatchMode (no interactive prompts), a connect timeout and a command timeout.
Remote commands are composed only from validated integers and whitelisted
literals; no caller-supplied string is ever interpolated into a shell line.
"""

import io
import json
import re
import shlex
import subprocess
import tarfile
import threading
import time
from pathlib import Path

from . import config

RUN_DIR_RE = re.compile(r"^physical_(\d+)_logical_(\d+)$")
# Concurrent ssh.exe sessions from this host to the VM were observed to stall
# for the whole command timeout while single sessions take well under a
# second, so every remote command is serialised through one lock.
_SSH_LOCK = threading.Lock()
# Short-lived cache for read-only probes that several pages request at once.
_CACHE = {}
_CACHE_TTL_SECONDS = 4.0


def _cached(key, producer):
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    value = producer()
    _CACHE[key] = (now, value)
    return value


def invalidate_cache():
    _CACHE.clear()


class VMError(RuntimeError):
    """A VM command failed, timed out, or the VM is unreachable."""


def _ssh_base():
    return [
        "ssh",
        "-i", str(config.VM_KEY),
        "-o", "IdentitiesOnly=yes",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=%d" % config.SSH_CONNECT_TIMEOUT,
        "-p", str(config.VM_PORT),
        "%s@%s" % (config.VM_USER, config.VM_HOST),
    ]


def key_available():
    return config.VM_KEY.is_file()


def run_remote(remote_command, timeout=None, binary=False):
    """Run one remote shell command string (built only from constants and
    validated integers by the callers in this module)."""
    if not key_available():
        raise VMError("SSH key not found at %s (set SDN_VM_SSH_KEY)" % config.VM_KEY)
    timeout = timeout or config.SSH_COMMAND_TIMEOUT
    try:
        with _SSH_LOCK:
            completed = subprocess.run(
                _ssh_base() + [remote_command],
                capture_output=True,
                timeout=timeout,
                text=not binary,
            )
    except FileNotFoundError as exc:
        raise VMError("ssh client not available on the host: %s" % exc) from exc
    except subprocess.TimeoutExpired as exc:
        raise VMError("VM command timed out after %ss" % timeout) from exc
    if completed.returncode == 255:
        detail = completed.stderr if isinstance(completed.stderr, str) else completed.stderr.decode("utf-8", "replace")
        raise VMError("SSH connection failed: %s" % detail.strip()[-400:])
    return completed


def _int(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be an integer" % name)
    if number < 0:
        raise ValueError("%s must be non-negative" % name)
    return number


def _switches(value):
    number = _int(value, "switches")
    if number not in config.SUPPORTED_SWITCHES:
        raise ValueError("switches must be one of %s" % (config.SUPPORTED_SWITCHES,))
    return number


def remote_run_dir(switches, logical_id, physical_id):
    switches = _switches(switches)
    name = "physical_%d_logical_%d" % (_int(physical_id, "physical_id"), _int(logical_id, "logical_id"))
    if switches == 4:
        return "%s/%s" % (config.VM_RUN_ROOT, name)
    return "%s/topology_%d_switches/%s" % (config.VM_RUN_ROOT, switches, name)


def probe():
    """Read-only state of the VM: controller listener, OVS bridges, busy processes,
    runner hashes, clock. Never starts anything. Cached for a few seconds."""
    return _cached("probe", _probe_uncached)


def _probe_uncached():
    script = " ; ".join([
        "echo __HOST__ $(hostname)",
        "echo __PY__ $(python3 --version 2>&1)",
        "echo __SUDO__ $(sudo -n true 2>/dev/null && echo ok || echo denied)",
        "echo __CTRL__ $(ss -ltn 2>/dev/null | awk '{print $4}' | grep -E ':%d$' | head -1)" % config.VM_CONTROLLER_PORT,
        "echo __RYU__ $(pgrep -af ryu-manager | head -1)",
        "echo __OVS__ $(sudo -n ovs-vsctl list-br 2>&1 | tr '\\n' ' ')",
        "echo __OVSRC__ $(sudo -n ovs-vsctl --version >/dev/null 2>&1 && echo ok || echo missing)",
        "echo __MN__ $(command -v mn >/dev/null 2>&1 && echo ok || echo missing)",
        "echo __IPERF__ $(command -v iperf >/dev/null 2>&1 && echo ok || echo missing)",
        "echo __BUSY__ $(ps -eo pid,args | grep -E '[ ]mn( |$)|[i]perf |experiment_runner_recollection' | grep -v grep | wc -l)",
        "echo __RUNNER__ $(sha256sum %s/experiment_runner_recollection.py 2>/dev/null | cut -c1-64)" % config.VM_PROJECT_DIR,
        "echo __NTP__ $(timedatectl show -p NTPSynchronized --value 2>/dev/null)",
        "echo __DATE__ $(date -Is)",
    ])
    completed = run_remote(script)
    values = {}
    for line in completed.stdout.splitlines():
        if line.startswith("__") and "__ " in line:
            key, _, rest = line.partition("__ ")
            values[key.strip("_")] = rest.strip()
        elif line.startswith("__"):
            values[line.strip("_ ")] = ""
    return {
        "reachable": True,
        "hostname": values.get("HOST", ""),
        "python": values.get("PY", ""),
        "sudo_nopasswd": values.get("SUDO") == "ok",
        "controller_listening": bool(values.get("CTRL")),
        "controller_process": values.get("RYU", ""),
        "ovs_available": values.get("OVSRC") == "ok",
        "ovs_bridges": [b for b in values.get("OVS", "").split() if b],
        "mininet_available": values.get("MN") == "ok",
        "iperf_available": values.get("IPERF") == "ok",
        "busy_process_count": int(values.get("BUSY") or 0),
        "runner_sha256": values.get("RUNNER", ""),
        "ntp_synchronized": values.get("NTP", ""),
        "vm_time": values.get("DATE", ""),
    }


def list_runs(switches):
    """Run directories and metadata status for one topology size (read-only, cached briefly)."""
    switches = _switches(switches)
    return _cached(("list_runs", switches), lambda: _list_runs_uncached(switches))


def _list_runs_uncached(switches):
    root = config.VM_RUN_ROOT if switches == 4 else "%s/topology_%d_switches" % (config.VM_RUN_ROOT, switches)
    script = (
        "sudo -n python3 - %s <<'EOF'\n"
        "import json, os, sys\n"
        "root = sys.argv[1]\n"
        "out = []\n"
        "if os.path.isdir(root):\n"
        "    for d in sorted(os.listdir(root)):\n"
        "        p = os.path.join(root, d)\n"
        "        if not (os.path.isdir(p) and d.startswith('physical_')):\n"
        "            continue\n"
        "        rec = {'name': d, 'path': p, 'files': sorted(os.listdir(p))}\n"
        "        mp = os.path.join(p, 'run_metadata.json')\n"
        "        if os.path.isfile(mp):\n"
        "            try:\n"
        "                m = json.load(open(mp))\n"
        "                rec.update({'status': m.get('status'), 'started_at': m.get('started_at'),\n"
        "                            'completed_at': m.get('completed_at'), 'failed_at': m.get('failed_at'),\n"
        "                            'failure': m.get('failure'), 'fault_link': m.get('fault_link'),\n"
        "                            'logical_experiment_id': m.get('logical_experiment_id'),\n"
        "                            'physical_run_id': m.get('physical_run_id')})\n"
        "            except Exception as exc:\n"
        "                rec['status'] = 'UNREADABLE'; rec['failure'] = str(exc)\n"
        "        else:\n"
        "            rec['status'] = 'NO_METADATA'\n"
        "        out.append(rec)\n"
        "print(json.dumps(out))\n"
        "EOF\n" % shlex.quote(root)
    )
    completed = run_remote(script)
    if completed.returncode != 0:
        raise VMError("Could not list VM runs: %s" % completed.stderr.strip()[-400:])
    try:
        return json.loads(completed.stdout.strip() or "[]")
    except ValueError as exc:
        raise VMError("Unparseable run listing from VM") from exc


def read_run_files(switches, logical_id, physical_id):
    """Current contents of the incrementally written run files (sudo read).
    Returns None for files that do not exist yet."""
    run_dir = remote_run_dir(switches, logical_id, physical_id)
    files = ("run_metadata.json", "phase_events.csv", "telemetry.csv", "iperf_client.log", "iperf_server.log")
    # One SSH session per poll: VM clock and runner PIDs are read in the same
    # session as the files, because every extra session costs CPU on the
    # single-vCPU VM while an experiment is running.
    # "[e]xperiment" cannot match the shell that carries this pattern on its own command line.
    pattern = "[e]xperiment_runner_recollection.py.*--logical-id %d --physical-id %d" % (
        _int(logical_id, "logical_id"), _int(physical_id, "physical_id"))
    script = ("echo __NOW__ $(date -Is); echo __PIDS__ $(pgrep -f %s | tr '\\n' ' '); "
              % shlex.quote(pattern))
    # Run directories are root-owned (0750); every read goes through sudo -n.
    script += "sudo -n test -d %s || { echo __NODIR__; exit 0; }; " % shlex.quote(run_dir)
    for name in files:
        script += "echo __FILE__ %s; sudo -n cat %s 2>/dev/null; echo; echo __END__; " % (
            name, shlex.quote(run_dir + "/" + name))
    completed = run_remote(script, timeout=config.SSH_COMMAND_TIMEOUT)
    text = completed.stdout
    meta = {"_now": None, "_pids": []}
    for line in text.splitlines()[:3]:
        if line.startswith("__NOW__"):
            meta["_now"] = line[len("__NOW__"):].strip() or None
        elif line.startswith("__PIDS__"):
            meta["_pids"] = [int(p) for p in line[len("__PIDS__"):].split() if p.isdigit()]
    if "__NODIR__" in text.split("__FILE__")[0]:
        return {"_exists": False, **meta}
    result = {"_exists": True, **meta}
    for block in text.split("__FILE__ ")[1:]:
        name, _, body = block.partition("\n")
        body = body.split("\n__END__")[0]
        name = name.strip()
        result[name] = body if body.strip() else None
    return result


def runner_process_running(logical_id, physical_id):
    # "[e]xperiment" cannot match the shell that carries this pattern on its own command line.
    pattern = "[e]xperiment_runner_recollection.py.*--logical-id %d --physical-id %d" % (
        _int(logical_id, "logical_id"), _int(physical_id, "physical_id"))
    completed = run_remote("pgrep -f %s | head -5" % shlex.quote(pattern))
    return [int(p) for p in completed.stdout.split() if p.isdigit()]


def preflight(switches, logical_id, physical_id):
    """The runner's own read-only preflight (no --run). Returns (ok, payload_or_error)."""
    switches, logical_id, physical_id = _switches(switches), _int(logical_id, "logical_id"), _int(physical_id, "physical_id")
    command = ("cd %s && sudo -n python3 -B experiment_runner_recollection.py --switches %d --logical-id %d --physical-id %d"
               % (shlex.quote(config.VM_PROJECT_DIR), switches, logical_id, physical_id))
    completed = run_remote(command, timeout=config.SSH_COMMAND_TIMEOUT)
    stdout, stderr = completed.stdout, completed.stderr
    if completed.returncode != 0:
        tail = (stderr.strip().splitlines() or [stdout.strip()])[-1] if (stderr.strip() or stdout.strip()) else "unknown error"
        return False, {"error": tail, "stderr": stderr[-2000:], "stdout": stdout[-2000:]}
    try:
        payload = json.loads(stdout.split("\nPreflight only")[0])
    except ValueError:
        return False, {"error": "Preflight output was not JSON", "stdout": stdout[-2000:]}
    return True, payload


def verify_topology(switches):
    """The runner's --verify-topology: starts the N-switch network, records the
    mapping, pings, stops. Modifies the isolated Mininet environment briefly;
    no run directory and no fault."""
    switches = _switches(switches)
    command = ("cd %s && sudo -n python3 -B experiment_runner_recollection.py --switches %d --verify-topology"
               % (shlex.quote(config.VM_PROJECT_DIR), switches))
    completed = run_remote(command, timeout=config.VERIFY_TOPOLOGY_TIMEOUT)
    if completed.returncode != 0:
        tail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "unknown error"
        return False, {"error": tail, "stderr": completed.stderr[-3000:], "stdout": completed.stdout[-2000:]}
    try:
        return True, json.loads(completed.stdout)
    except ValueError:
        return False, {"error": "verify output was not JSON", "stdout": completed.stdout[-3000:]}


def start_run(switches, logical_id, physical_id):
    """Launch the real runner with --run in the background on the VM. Returns the
    remote PID and log path. The caller is responsible for locking and preflight."""
    switches, logical_id, physical_id = _switches(switches), _int(logical_id, "logical_id"), _int(physical_id, "physical_id")
    log_name = "run_%d_switches_physical_%d_logical_%d.log" % (switches, physical_id, logical_id)
    log_path = "%s/%s" % (config.VM_LOG_DIR, log_name)
    # The '&' must bind to the runner command alone. With 'a && b && runner &'
    # the whole list is backgrounded as a subshell whose stdout is still the SSH
    # channel, and the SSH session then blocks until the run ends.
    command = (
        "mkdir -p %s; cd %s || exit 1; "
        "sudo -n nohup python3 -B experiment_runner_recollection.py --switches %d --logical-id %d --physical-id %d "
        "--normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run > %s 2>&1 < /dev/null & echo __PID__ $!"
        % (shlex.quote(config.VM_LOG_DIR), shlex.quote(config.VM_PROJECT_DIR), switches, logical_id, physical_id,
           shlex.quote(log_path))
    )
    completed = run_remote(command, timeout=config.SSH_COMMAND_TIMEOUT)
    invalidate_cache()
    pid = None
    for line in completed.stdout.splitlines():
        if line.startswith("__PID__"):
            try:
                pid = int(line.split()[1])
            except (IndexError, ValueError):
                pid = None
    if completed.returncode != 0 or pid is None:
        raise VMError("Could not launch the runner: %s" % (completed.stderr.strip()[-400:] or completed.stdout[-400:]))
    return {"remote_pid": pid, "log_path": log_path, "launched_at": time.time()}


def read_log(log_path):
    if not log_path.startswith(config.VM_LOG_DIR + "/") or "/.." in log_path:
        raise ValueError("Log path outside the dashboard log directory")
    completed = run_remote("tail -c 20000 %s 2>/dev/null" % shlex.quote(log_path))
    return completed.stdout


def fetch_run(switches, logical_id, physical_id, destination_root):
    """Copy a run directory from the VM into an isolated local directory as a
    tar stream. Refuses to overwrite an existing local copy."""
    switches, logical_id, physical_id = _switches(switches), _int(logical_id, "logical_id"), _int(physical_id, "physical_id")
    run_dir = remote_run_dir(switches, logical_id, physical_id)
    parent, name = run_dir.rsplit("/", 1)
    destination_root = Path(destination_root)
    target = destination_root / name
    if target.exists():
        raise FileExistsError("Local copy already exists: %s" % target)
    completed = run_remote("sudo -n tar czf - -C %s %s" % (shlex.quote(parent), shlex.quote(name)),
                           timeout=config.SSH_COMMAND_TIMEOUT * 3, binary=True)
    if completed.returncode != 0 or not completed.stdout:
        raise VMError("Could not fetch run %s: %s" % (name, completed.stderr.decode("utf-8", "replace")[-400:]))
    destination_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts or member_path.parts[0] != name:
                raise VMError("Unexpected path in fetched archive: %s" % member.name)
            if not (member.isfile() or member.isdir()):
                raise VMError("Unexpected entry type in fetched archive: %s" % member.name)
        archive.extractall(destination_root)
    return target
