import os
import csv
import time
import subprocess
import threading
import sys
from datetime import datetime
from pathlib import Path

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel
from telemetry_pipeline import PHASE_FIELDS, collector_command, experiment_paths


# ============================================================
# EXPERIMENT CONFIGURATION
# Change ONLY these values for each experiment
# ============================================================

EXPERIMENT_ID = 19

FAULT_LINK = "s3-s4"
FAULT_TYPE = "link_failure"

TRAFFIC_MBPS = 25

DURATION_NORMAL = 20
DURATION_FAULT = 20
DURATION_RECOVERY = 20

OUTPUT_DIR = Path(__file__).resolve().parent / "experiments"


# ============================================================
# HELPERS
# ============================================================

def timestamp():
    return datetime.now().isoformat()


def write_phase(writer, phase):
    writer.writerow({
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp(),
        "phase": phase,
        "fault_type": FAULT_TYPE if phase != "normal" else "none",
        "fault_location": FAULT_LINK if phase != "normal" else "none"
    })


def start_telemetry(output_path, experiment_id):
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite telemetry: {output_path}")
    collector = Path(__file__).with_name("telemetry.py")
    command = collector_command(
        collector, output_path.resolve(), experiment_id, sys.executable
    )
    return subprocess.Popen(command)


def generate_traffic(h1):
    print(f"Starting UDP traffic at {TRAFFIC_MBPS} Mbps...")

    h1.cmd(
        f"iperf -s -u -p 5001 > /tmp/iperf_server.log 2>&1 &"
    )

    time.sleep(2)

    h1.cmd(
        f"iperf -c 10.0.0.2 -u "
        f"-b {TRAFFIC_MBPS}M "
        f"-t {DURATION_NORMAL + DURATION_FAULT + DURATION_RECOVERY} "
        f"-p 5001 > /tmp/iperf_client.log 2>&1 &"
    )


def disconnect_link(net):
    print(f"Injecting fault: {FAULT_LINK}")

    s1 = net.get("s1")
    s2 = net.get("s2")

    if FAULT_LINK == "s1-s2":
        s1_intf = "s1-eth2"
        s2_intf = "s2-eth1"

    elif FAULT_LINK == "s2-s3":
        s1 = net.get("s2")
        s2 = net.get("s3")
        s1_intf = "s2-eth2"
        s2_intf = "s3-eth1"

    elif FAULT_LINK == "s3-s4":
        s1 = net.get("s3")
        s2 = net.get("s4")
        s1_intf = "s3-eth2"
        s2_intf = "s4-eth1"

    else:
        raise ValueError("Invalid FAULT_LINK")

    s1.cmd(f"ip link set {s1_intf} down")
    s2.cmd(f"ip link set {s2_intf} down")


def reconnect_link(net):
    print(f"Recovering link: {FAULT_LINK}")

    s1 = net.get("s1")
    s2 = net.get("s2")

    if FAULT_LINK == "s1-s2":
        s1_intf = "s1-eth2"
        s2_intf = "s2-eth1"

    elif FAULT_LINK == "s2-s3":
        s1 = net.get("s2")
        s2 = net.get("s3")
        s1_intf = "s2-eth2"
        s2_intf = "s3-eth1"

    elif FAULT_LINK == "s3-s4":
        s1 = net.get("s3")
        s2 = net.get("s4")
        s1_intf = "s3-eth2"
        s2_intf = "s4-eth1"

    s1.cmd(f"ip link set {s1_intf} up")
    s2.cmd(f"ip link set {s2_intf} up")


# ============================================================
# MAIN
# ============================================================

def run_experiment():

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    telemetry_file, phase_file = experiment_paths(OUTPUT_DIR, EXPERIMENT_ID)
    for output_path in (telemetry_file, phase_file):
        if output_path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing experiment evidence: {output_path}"
            )

    print()
    print("=" * 60)
    print(f"STARTING EXPERIMENT {EXPERIMENT_ID}")
    print(f"Fault: {FAULT_LINK}")
    print(f"Traffic: {TRAFFIC_MBPS} Mbps")
    print("=" * 60)

    net = None
    telemetry_process = None

    try:

        # ----------------------------------------------------
        # CREATE NETWORK
        # ----------------------------------------------------

        net = Mininet(
            controller=RemoteController,
            switch=OVSSwitch,
            link=TCLink,
            autoSetMacs=True
        )

        c0 = net.addController(
            "c0",
            controller=RemoteController,
            ip="127.0.0.1",
            port=6633
        )

        h1 = net.addHost("h1")
        h2 = net.addHost("h2")

        s1 = net.addSwitch("s1", protocols="OpenFlow13")
        s2 = net.addSwitch("s2", protocols="OpenFlow13")
        s3 = net.addSwitch("s3", protocols="OpenFlow13")
        s4 = net.addSwitch("s4", protocols="OpenFlow13")

        net.addLink(h1, s1)
        net.addLink(s1, s2)
        net.addLink(s2, s3, bw=10, delay="5ms")
        net.addLink(s3, s4)
        net.addLink(s4, h2)

        net.start()

        print("Network started.")

        time.sleep(5)

        # ----------------------------------------------------
        # PHASE LOG
        # ----------------------------------------------------

        with open(phase_file, "x", newline="", encoding="utf-8") as f:

            writer = csv.DictWriter(
                f,
                fieldnames=PHASE_FIELDS,
            )

            writer.writeheader()

            # ------------------------------------------------
            # START TELEMETRY
            # ------------------------------------------------

            telemetry_process = start_telemetry(telemetry_file, EXPERIMENT_ID)

            time.sleep(3)
            if telemetry_process.poll() is not None:
                raise RuntimeError(
                    "Telemetry collector exited before the experiment began"
                )

            # ------------------------------------------------
            # NORMAL
            # ------------------------------------------------

            print()
            print("PHASE 1: NORMAL")

            write_phase(writer, "normal")
            f.flush()

            generate_traffic(h1)

            time.sleep(DURATION_NORMAL)

            # ------------------------------------------------
            # FAULT
            # ------------------------------------------------

            print()
            print("PHASE 2: FAULT")

            disconnect_link(net)

            write_phase(writer, "fault")
            f.flush()

            time.sleep(DURATION_FAULT)

            # ------------------------------------------------
            # RECOVERY
            # ------------------------------------------------

            print()
            print("PHASE 3: RECOVERY")

            reconnect_link(net)

            write_phase(writer, "recovery")
            f.flush()

            time.sleep(DURATION_RECOVERY)

        # ----------------------------------------------------
        # STOP TELEMETRY
        # ----------------------------------------------------

        if telemetry_process:
            if telemetry_process.poll() is None:
                telemetry_process.terminate()
            try:
                telemetry_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                telemetry_process.kill()
                telemetry_process.wait(timeout=5)

            if telemetry_process.returncode != 0:
                raise RuntimeError(
                    f"Telemetry collector failed with exit code "
                    f"{telemetry_process.returncode}"
                )
            if not telemetry_file.is_file() or telemetry_file.stat().st_size == 0:
                raise RuntimeError("Telemetry collector produced no CSV output")

        print()
        print("=" * 60)
        print(f"EXPERIMENT {EXPERIMENT_ID} COMPLETE")
        print("=" * 60)

    finally:

        if telemetry_process:
            try:
                telemetry_process.terminate()
            except:
                pass

        if net:
            print("Stopping Mininet...")
            net.stop()

        print("Cleanup complete.")


if __name__ == "__main__":
    setLogLevel("info")
    run_experiment()
