"""Run the existing RF/topology comparison on a validated candidate, separately.

Uses the milestone evaluator implementation without modifying it. Each run
gets an exclusive output directory and records dataset/evaluator hashes.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "derived_datasets" / "candidate_validated_through_physical23" / "candidate_dataset.csv"
DEFAULT_OUTPUT = ROOT / "evaluations" / "validated_candidate_physical23_loeo"
EVALUATOR = ROOT / "evaluate_grouped_rca_generalized.py"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate(dataset, output_dir):
    dataset, output_dir = Path(dataset), Path(output_dir)
    if not dataset.is_file() or not EVALUATOR.is_file():
        raise FileNotFoundError("Validated dataset or reference evaluator is missing")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("sdn_rca_grouped_evaluator", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATA = dataset
    module.RESULTS = output_dir / "grouped_evaluation.csv"
    module.SUMMARY = output_dir / "evaluation_summary.json"
    module.SPLITS = output_dir / "split_assignments.csv"
    module.FEATURES_OUT = output_dir / "fold_feature_policy.csv"
    module.evaluate()

    summary_path = module.SUMMARY
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["topology_mapping"] = (
        "Added physical runs 21 and 23-29 carry independently validated captured "
        "runtime OVS switch-port mappings. Historical source runs have no captured "
        "runtime mapping and retain setup-inferred port assignments. Physical run "
        "20 is invalid and run 22 remains provisional; neither is included."
    )
    with summary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    run_record = {
        "dataset_path": str(dataset), "dataset_sha256": sha256(dataset),
        "reference_evaluator_path": str(EVALUATOR),
        "reference_evaluator_sha256": sha256(EVALUATOR),
        "python": sys.version,
        "protocol": summary["protocol"], "task": summary["task"],
        "outputs": {"predictions": str(module.RESULTS), "summary": str(summary_path),
                    "splits": str(module.SPLITS), "feature_policy": str(module.FEATURES_OUT)},
        "methods": summary["methods"],
        "interpretation": "Conditional fault-window localization using oracle phase annotations; not online detection. Three candidate links mean Top-3 is nondiscriminative.",
    }
    with (output_dir / "evaluation_provenance.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(run_record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return run_record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    record = evaluate(args.dataset, args.output_dir)
    print(json.dumps(record["methods"], indent=2))


if __name__ == "__main__":
    main()
