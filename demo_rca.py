"""Display a read-only replay of a saved conditional link-localization evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_EVALUATION = ROOT / "evaluations" / "recollected_13_6_split_v4"
DEFAULT_CANDIDATE = (
    ROOT / "derived_datasets" / "candidate_with_reaudited_physical21_and_physical23_v2"
    / "candidate_dataset.csv"
)
TOPOLOGY = ("h1-s1", "s1-s2", "s2-s3", "s3-s4", "s4-h2")
REQUIRED_RESULT_COLUMNS = {
    "record_type", "method", "experiment_id", "actual_link", "rank1_link",
    "rank2_link", "rank3_link", "top1_hit", "top2_hit", "top3_hit",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_demo(evaluation_dir: Path, candidate: Path):
    results_path = evaluation_dir / "topology_link_rca_results.csv"
    evaluation_provenance_path = evaluation_dir / "evaluation_provenance.json"
    candidate_provenance_path = candidate.parent / "provenance.json"
    for path in (results_path, evaluation_provenance_path, candidate, candidate_provenance_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required saved demo artifact is missing: {path}")

    provenance = json.loads(evaluation_provenance_path.read_text(encoding="utf-8"))
    dataset_provenance = json.loads(candidate_provenance_path.read_text(encoding="utf-8"))
    actual_hash = sha256(candidate)
    if actual_hash != provenance.get("dataset_sha256"):
        raise ValueError("Candidate hash does not match evaluation provenance")
    if actual_hash != dataset_provenance.get("dataset_sha256"):
        raise ValueError("Candidate hash does not match candidate provenance")

    with results_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_RESULT_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Saved evaluation CSV is missing columns: {sorted(missing)}")
        rows = list(reader)
    experiment_rows = [row for row in rows if row["record_type"] == "experiment"]
    methods = sorted({row["method"] for row in experiment_rows})
    if not experiment_rows or not methods:
        raise ValueError("Saved evaluation contains no per-experiment rankings")
    return provenance, dataset_provenance, experiment_rows, methods


def render(evaluation_dir: Path, candidate: Path) -> str:
    provenance, dataset_provenance, rows, methods = load_demo(evaluation_dir, candidate)
    lines = [
        "SDN RCA - saved evaluation replay (no training or live inference)",
        f"Data quality: {dataset_provenance.get('validation', 'validation status not recorded')}; "
        f"{len(dataset_provenance.get('included_logical_experiments', []))} logical experiments; "
        f"{dataset_provenance.get('run_23_rows', 'n/a')} rows from physical run 23",
        f"Candidate SHA-256: {sha256(candidate)}",
        "Topology: " + " - ".join(TOPOLOGY),
        f"Task: {provenance.get('task', 'task not recorded')}",
        f"Split: train={provenance['split']['train_logical_ids']}; "
        f"test={provenance['split']['test_logical_ids']}",
        "Oracle caveat: annotated fault-phase information selected the evaluation window; "
        "this output is not online detection.",
        "",
        "Stored test rankings (actual labels shown only for retrospective evaluation):",
    ]
    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        top1 = sum(row["top1_hit"].strip().lower() == "true" for row in method_rows)
        top2 = sum(row["top2_hit"].strip().lower() == "true" for row in method_rows)
        lines.append(f"\n{method}: Top-1 {top1}/{len(method_rows)}, Top-2 {top2}/{len(method_rows)}")
        for row in method_rows:
            ranking = " > ".join(row[f"rank{rank}_link"] for rank in (1, 2, 3))
            lines.append(
                f"  experiment {row['experiment_id']}: {ranking}; "
                f"actual={row['actual_link']}"
            )
    lines.extend(("", "All three links are ranked, so Top-3 is nondiscriminative."))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-dir", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args(argv)
    try:
        print(render(args.evaluation_dir, args.candidate))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
