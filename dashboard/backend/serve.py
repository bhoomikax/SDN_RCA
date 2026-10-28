"""Start the dashboard API on loopback.

    .\\venv\\Scripts\\python.exe dashboard\\backend\\serve.py

Environment (all optional): SDN_VM_SSH_KEY, SDN_VM_HOST, SDN_VM_PORT, SDN_VM_USER,
SDN_VM_PROJECT_DIR, SDN_DASHBOARD_PORT, SDN_DASHBOARD_ORIGIN, SDN_DASHBOARD_TOKEN.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(ROOT), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import uvicorn  # noqa: E402

from sdn_dashboard import config  # noqa: E402


if __name__ == "__main__":
    uvicorn.run("sdn_dashboard.api:app", host=config.BIND_HOST, port=config.BIND_PORT, reload=False, log_level="info")
