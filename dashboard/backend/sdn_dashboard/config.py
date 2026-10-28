"""Paths and connection settings. Secrets and host-specific values come from the
environment; nothing sensitive is stored in source."""

import os
from pathlib import Path

# Repository root: dashboard/backend/sdn_dashboard/config.py -> ../../..
ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = ROOT / "dashboard" / "backend"
STATE_DIR = BACKEND_DIR / "state"
# Isolated storage for runs fetched from the VM by the dashboard. Never raw_evidence/.
DASHBOARD_RUNS_DIR = ROOT / "dashboard_runs"
RESULTS_DIR = ROOT / "results"
XAI_DIR = RESULTS_DIR / "xai"
COMPARISON_DIR = RESULTS_DIR / "comparison_4_8_12"
RAW_EVIDENCE_DIR = ROOT / "raw_evidence"
FOUR_SWITCH_CANDIDATE = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3"
FOUR_SWITCH_GRAPH = ROOT / "derived_graphs" / "balanced_recollection_v3_portsum" / "graph_dataset.json"

SUPPORTED_SWITCHES = (4, 8, 12)

# Saved, audited evaluation artifacts per topology (read-only for the dashboard).
SAVED_RESULTS = {
    4: {
        "candidate_dir": FOUR_SWITCH_CANDIDATE,
        "graph": FOUR_SWITCH_GRAPH,
        "rf_eval_dir": RESULTS_DIR / "topology_4_switches_regression" / "loeo_rf_topology",
        "neural_eval_dir": RESULTS_DIR / "topology_4_switches_regression" / "loeo_neural",
        "xai_dir": XAI_DIR / "topology_4_switches",
        "static_mapping": True,
        "label": "4 switches (frozen v3 release, reproduced by the regression run)",
    },
    8: {
        "candidate_dir": RESULTS_DIR / "topology_8_switches" / "candidate",
        "graph": RESULTS_DIR / "topology_8_switches" / "graph" / "graph_dataset.json",
        "rf_eval_dir": RESULTS_DIR / "topology_8_switches" / "loeo_rf_topology",
        "neural_eval_dir": RESULTS_DIR / "topology_8_switches" / "loeo_neural",
        "xai_dir": XAI_DIR / "topology_8_switches",
        "static_mapping": False,
        "label": "8 switches",
    },
    12: {
        "candidate_dir": RESULTS_DIR / "topology_12_switches" / "candidate",
        "graph": RESULTS_DIR / "topology_12_switches" / "graph" / "graph_dataset.json",
        "rf_eval_dir": RESULTS_DIR / "topology_12_switches" / "loeo_rf_topology",
        "neural_eval_dir": RESULTS_DIR / "topology_12_switches" / "loeo_neural",
        "xai_dir": XAI_DIR / "topology_12_switches",
        "static_mapping": False,
        "label": "12 switches",
    },
}

# VM access. The private key path is read from the environment (default is the
# user's own key file); it is never embedded in source or sent to the browser.
VM_HOST = os.environ.get("SDN_VM_HOST", "127.0.0.1")
VM_PORT = int(os.environ.get("SDN_VM_PORT", "2222"))
VM_USER = os.environ.get("SDN_VM_USER", "mininet")
VM_KEY = Path(os.environ.get("SDN_VM_SSH_KEY", str(Path.home() / ".ssh" / "mininet_vm_ed25519")))
VM_PROJECT_DIR = os.environ.get("SDN_VM_PROJECT_DIR", "/home/mininet/sdn_project/topology_scaling_20261023")
VM_RUN_ROOT = VM_PROJECT_DIR + "/recollection_runs"
VM_LOG_DIR = VM_PROJECT_DIR + "/dashboard_logs"
VM_CONTROLLER_HOST = "127.0.0.1"
VM_CONTROLLER_PORT = 6633

SSH_CONNECT_TIMEOUT = int(os.environ.get("SDN_SSH_CONNECT_TIMEOUT", "8"))
SSH_COMMAND_TIMEOUT = int(os.environ.get("SDN_SSH_COMMAND_TIMEOUT", "40"))
VERIFY_TOPOLOGY_TIMEOUT = int(os.environ.get("SDN_VERIFY_TIMEOUT", "180"))
RUN_MAX_SECONDS = 300  # matches run_topology_batch.RUN_TIMEOUT_SECONDS

# Frontend origin allowed by CORS (local development server).
FRONTEND_ORIGIN = os.environ.get("SDN_DASHBOARD_ORIGIN", "http://localhost:3000")
BIND_HOST = os.environ.get("SDN_DASHBOARD_BIND", "127.0.0.1")
BIND_PORT = int(os.environ.get("SDN_DASHBOARD_PORT", "8765"))
# Optional shared secret for control (fault-injecting) endpoints. When set, the
# frontend must send it as X-Dashboard-Token. The API is loopback-only by default.
CONTROL_TOKEN = os.environ.get("SDN_DASHBOARD_TOKEN", "")
