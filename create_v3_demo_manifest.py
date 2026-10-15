"""Seal hashes for the v3 saved-results replay without overwriting outputs."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create(dataset, evaluation_dir):
    dataset, evaluation_dir = Path(dataset), Path(evaluation_dir)
    target = evaluation_dir / "demo_artifact_hashes.json"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite demo manifest: {target}")
    provenance = json.loads((evaluation_dir / "evaluation_provenance.json").read_text(encoding="utf-8"))
    hashes = {
        "dataset": digest(dataset),
        "predictions": digest(evaluation_dir / "grouped_evaluation.csv"),
        "summary": digest(evaluation_dir / "evaluation_summary.json"),
        "splits": digest(evaluation_dir / "split_assignments.csv"),
        "feature_policy": digest(evaluation_dir / "fold_feature_policy.csv"),
    }
    if provenance.get("dataset_sha256") != hashes["dataset"]:
        raise ValueError("Evaluation provenance dataset hash does not match selected candidate")
    target.write_text(json.dumps({"hashes": hashes, "evaluation_dir": str(evaluation_dir)}, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(create(args.dataset, args.evaluation_dir))


if __name__ == "__main__":
    main()
