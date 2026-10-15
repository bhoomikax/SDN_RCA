"""Evaluate the original stratified 13/6 split using physical runs 21 and 23.

The research evaluator is imported unchanged. Inputs and output paths are
overridden only in memory so historical datasets/results stay untouched.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "derived_datasets" / "candidate_with_reaudited_physical21_and_physical23" / "candidate_dataset.csv"
DEFAULT_OUTPUT_DIR = ROOT / "evaluations" / "recollected_13_6_split"
EVALUATOR = ROOT / "evaluate_topology_link_rca.py"
EXPECTED_TRAIN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 17, 19]
EXPECTED_TEST = [10, 11, 12, 15, 16, 18]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate(dataset, output_dir):
    dataset, output_dir = Path(dataset), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation directory: {output_dir}")
    if not dataset.is_file() or not EVALUATOR.is_file():
        raise FileNotFoundError("Candidate dataset or original evaluator is missing")
    output_dir.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("sdn_rca_original_evaluator", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.INPUT = dataset
    module.OUTPUT = output_dir / "topology_link_rca_results.csv"
    module.main()
    results = pd.read_csv(module.OUTPUT)
    overall = results[results["record_type"] == "overall_metric"]
    methods = {}
    for _, row in overall.iterrows():
        method = str(row["method"])
        folds = results[(results["record_type"] == "experiment") & (results["method"] == method)]
        ranks = []
        for _, fold in folds.iterrows():
            ranking = [str(fold[f"rank{rank}_link"]) for rank in (1, 2, 3)]
            ranks.append(ranking.index(str(fold["actual_link"])) + 1)
        per_class = {}
        for label in sorted(set(folds["actual_link"].astype(str))):
            selected = folds[folds["actual_link"].astype(str) == label]
            support = len(selected)
            true_positive = int((selected["rank1_link"].astype(str) == label).sum())
            predicted = int((folds["rank1_link"].astype(str) == label).sum())
            precision = true_positive / predicted if predicted else 0.0
            recall = true_positive / support if support else 0.0
            per_class[label] = {
                "support": support, "top1_precision": precision, "top1_recall": recall,
                "top1_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                "top2_recall": float(selected["top2_hit"].astype(bool).mean()),
                "top3_recall": float(selected["top3_hit"].astype(bool).mean()),
            }
        methods[method] = {
            "test_support": int(row["test_support"]),
            "top1_accuracy": float(row["top1_accuracy"]),
            "top2_accuracy": float(row["top2_accuracy"]),
            "top3_accuracy": float(row["top3_accuracy"]),
            "mean_reciprocal_rank": sum(1 / rank for rank in ranks) / len(ranks),
            "mean_rank": sum(ranks) / len(ranks),
            "per_class": per_class,
        }
    if set(methods) != {"rf_baseline", "topology_link_ranker"}:
        raise ValueError("Original evaluator did not produce both expected methods")
    record = {
        "dataset_path": str(dataset), "dataset_sha256": sha256(dataset),
        "original_evaluator_path": str(EVALUATOR),
        "original_evaluator_sha256": sha256(EVALUATOR),
        "split": {"train_logical_ids": EXPECTED_TRAIN, "test_logical_ids": EXPECTED_TEST,
                  "run_mapping": {"physical_23": 3, "physical_21": 10}},
        "fit_scope": "RF and topology normal baselines use training runs only; test experiment labels are evaluated after rankings are produced.",
        "task": "Conditional fault localization; the evaluator uses annotated phase labels to select the fault window and is not an online detector.",
        "methods": methods,
        "results_csv": str(module.OUTPUT),
        "python": sys.version,
    }
    with (output_dir / "evaluation_provenance.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.dataset, args.output_dir)["methods"], indent=2))


if __name__ == "__main__":
    main()
