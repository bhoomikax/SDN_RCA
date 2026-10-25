"""Remove only the OVS bridges and veth interfaces recorded by one abandoned run.

Used after a runner process was killed before its own cleanup (for example by a
batch timeout following a VM suspend). It never runs `mn -c` (which would kill
the shared Ryu controller), never touches resources that the run did not
record, and refuses to act if the run is COMPLETE or a Mininet/iperf process
is still alive. Python 3.8 compatible; run as root inside the VM.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def owned_resources(run_dir):
    metadata = json.loads((Path(run_dir) / "run_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("status") == "COMPLETE":
        raise SystemExit("Refusing: run %s is COMPLETE, not abandoned" % run_dir)
    spec = metadata.get("topology_spec") or {}
    bridges = list(spec.get("switches") or [])
    interfaces = sorted({row["interface_name"] for row in metadata.get("runtime_switch_port_mapping", [])})
    if not bridges:
        raise SystemExit("Refusing: run metadata records no switches")
    return metadata, bridges, interfaces


def live_mininet_processes():
    out = subprocess.run(["ps", "-eo", "pid,args"], check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if ("mininet:" in line or "mnexec" in line or " mn " in line or "iperf " in line)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="actually delete; default is a dry run")
    args = parser.parse_args(argv)
    metadata, bridges, interfaces = owned_resources(args.run_dir)
    busy = live_mininet_processes()
    if busy:
        raise SystemExit("Refusing: Mininet/iperf processes still alive:\n" + "\n".join(busy))
    existing = set(subprocess.run(["ovs-vsctl", "list-br"], check=True, capture_output=True, text=True).stdout.split())
    links = subprocess.run(["ip", "-o", "link", "show"], check=True, capture_output=True, text=True).stdout
    present_links = {line.split(":")[1].strip().split("@")[0] for line in links.splitlines() if ":" in line}
    to_delete_bridges = [b for b in bridges if b in existing]
    to_delete_links = [i for i in interfaces if i in present_links]
    print("run %s status=%s" % (args.run_dir, metadata.get("status")))
    print("bridges recorded by this run and present: %s" % to_delete_bridges)
    print("interfaces recorded by this run and present: %s" % to_delete_links)
    print("bridges present but NOT owned by this run (left untouched): %s" % sorted(existing - set(bridges)))
    if not args.apply:
        print("dry run; pass --apply to delete the listed resources")
        return 0
    for bridge in to_delete_bridges:
        subprocess.run(["ovs-vsctl", "--if-exists", "del-br", bridge], check=True)
    for link in to_delete_links:
        subprocess.run(["ip", "link", "del", link], check=False, capture_output=True)
    remaining = subprocess.run(["ovs-vsctl", "list-br"], check=True, capture_output=True, text=True).stdout.split()
    print("remaining bridges: %s" % remaining)
    return 0 if not set(remaining) & set(bridges) else 1


if __name__ == "__main__":
    sys.exit(main())
