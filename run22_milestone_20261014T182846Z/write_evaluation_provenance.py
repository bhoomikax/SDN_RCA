"""Create a one-time, no-overwrite provenance summary for this evaluation."""

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = ROOT / "evaluation_provenance.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    split_path = ROOT / "split_assignments.csv"
    with split_path.open(newline="", encoding="utf-8") as stream:
        splits = list(csv.DictReader(stream))
    summary = json.loads((ROOT / "evaluation_summary.json").read_text(encoding="utf-8"))
    provenance = {
        "validation": "PASS",
        "created_utc_date": "2026-10-15",
        "source_candidate_sha256": "e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2",
        "source_manifest_sha256": "80f12f94a7fb0dd6b648126d1021993e78616aad0daf2ab7f4c1d423c8e16d7c",
        "raw_run22_sha256": json.loads((ROOT / "audit" / "run22_raw_provenance.json").read_text(encoding="utf-8"))["sha256"],
        "candidate_sha256": digest(ROOT / "candidate_master_dataset.csv"),
        "evaluation_code_sha256": digest(ROOT / "evaluate_grouped_rca.py"),
        "candidate_builder_sha256": digest(ROOT / "build_candidate.py"),
        "offline_regression_test_sha256": digest(ROOT / "test_grouped_rca.py"),
        "output_sha256": {
            name: digest(ROOT / name)
            for name in ("grouped_evaluation.csv", "evaluation_summary.json", "split_assignments.csv", "fold_feature_policy.csv")
        },
        "exact_commands_from_repository_root": [
            r"& '.\venv\Scripts\python.exe' '.\run22_milestone_20261014T182846Z\build_candidate.py'",
            r"& '.\venv\Scripts\python.exe' '.\run22_milestone_20261014T182846Z\evaluate_grouped_rca.py'",
            r"Push-Location '.\run22_milestone_20261014T182846Z'; & '..\venv\Scripts\python.exe' -m unittest -v test_grouped_rca.py; Pop-Location",
            "Ubuntu VM, /home/mininet/sdn_project: python3 -B -m unittest discover -q",
        ],
        "grouped_splits": splits,
        "evaluation_protocol": summary["protocol"],
        "task_scope": summary["task"],
        "software": summary["software"],
        "random_seed": summary["random_seed"],
        "model": summary["model"],
        "metrics": summary["methods"],
        "offline_tests": {
            "new_grouped_rca_tests": {"count": 6, "result": "PASS"},
            "ubuntu_project_suite": {"count": 37, "result": "PASS", "command": "python3 -B -m unittest discover -q"},
            "windows_project_suite_attempt": {"result": "FAILED_PLATFORM_INCOMPATIBLE", "reason": "10 tests patch os.geteuid, which is unavailable on Windows; the intended Ubuntu suite passed."},
            "syntax_checks": {"result": "PASS", "command": "python -m py_compile build_candidate.py evaluate_grouped_rca.py test_grouped_rca.py"},
        },
        "notes": [
            "No Mininet experiment, fault injection, or Ryu lifecycle command was run for this milestone.",
            "The evaluator performs conditional fault-window localization using phase timestamps as oracle information; it does not evaluate online detection.",
            "Top-3 is 100% by construction because all three known candidate links are ranked.",
            "Previous 13/6 metrics use a different split and are not directly comparable to this leave-one-experiment-out result.",
        ],
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(provenance, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"WROTE {output}")
    print(f"SHA256 {digest(output)}")


if __name__ == "__main__":
    main()
