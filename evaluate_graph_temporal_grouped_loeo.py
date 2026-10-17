"""Compare graph, temporal, and graph-temporal localization under grouped LOEO."""

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np

import evaluate_graph_temporal_link_rca as models


ROOT = Path(__file__).resolve().parent
DEFAULT_GRAPH = ROOT / "derived_graphs" / "balanced_recollection_v3_portsum" / "graph_dataset.json"
DEFAULT_CANDIDATE = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3" / "candidate_dataset.csv"
DEFAULT_REFERENCE = ROOT / "evaluations" / "balanced_recollection_v3_loeo_release" / "grouped_evaluation.csv"
DEFAULT_OUTPUT = ROOT / "evaluations" / "graph_temporal_v3_grouped_loeo_verified"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ordered_loo_splits(experiment_ids):
    ids = tuple(sorted(map(int, experiment_ids)))
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("Grouped LOEO requires at least two unique experiment IDs")
    for held_out in ids:
        train_ids = tuple(value for value in ids if value != held_out)
        if held_out in train_ids or set(train_ids) | {held_out} != set(ids):
            raise AssertionError("Experiment leakage in grouped split")
        yield held_out, train_ids


def _read_reference(path, experiment_ids, candidate_hash):
    provenance_path = Path(path).parent / "evaluation_provenance.json"
    if not provenance_path.is_file():
        raise FileNotFoundError(provenance_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("dataset_sha256") != candidate_hash:
        raise ValueError("RF/topology reference was not evaluated on the candidate dataset")
    expected_protocol = (
        f"leave-one-logical-experiment-out ({len(experiment_ids)} folds)"
    )
    if not provenance.get("protocol", "").startswith(expected_protocol):
        raise ValueError("RF/topology reference does not use the matching grouped LOEO split")
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"experiment_id", "method", "rank1_link", "rank2_link"}
    if rows and required - set(rows[0]):
        raise ValueError(f"Reference predictions missing {sorted(required - set(rows[0]))}")
    results = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        selected = [row for row in rows if row["method"] == method]
        by_id = {int(row["experiment_id"]): row for row in selected}
        if len(by_id) != len(selected) or set(by_id) != set(experiment_ids):
            raise ValueError(f"Reference {method} does not cover each LOEO experiment once")
        for experiment_id, row in by_id.items():
            expected_train_ids = ";".join(
                str(value) for value in experiment_ids if value != experiment_id
            )
            if row.get("train_experiment_ids") != expected_train_ids:
                raise ValueError(
                    f"Reference {method} has an unexpected training split for "
                    f"experiment {experiment_id}"
                )
        results[method] = by_id
    return results


def _metrics(rows):
    total = len(rows)
    if not total:
        raise ValueError("Cannot summarize an empty prediction set")
    top1 = sum(row["rank"] == 1 for row in rows)
    top2 = sum(row["rank"] <= 2 for row in rows)
    actuals = [row["actual_link"] for row in rows]
    predicted = [row["rank1_link"] for row in rows]
    per_class = {}
    for link in models.LINKS:
        support = sum(value == link for value in actuals)
        hits = sum(actual == link and prediction == link
                   for actual, prediction in zip(actuals, predicted))
        predicted_count = sum(value == link for value in predicted)
        precision = hits / predicted_count if predicted_count else 0.0
        recall = hits / support if support else 0.0
        per_class[link] = {
            "support": support,
            "top1_precision": precision,
            "top1_recall": recall,
            "top1_f1": 2 * precision * recall / (precision + recall)
            if precision + recall else 0.0,
            "top2_recall": sum(
                row["actual_link"] == link and row["rank"] <= 2 for row in rows
            ) / support if support else 0.0,
        }
    ranks = [row["rank"] for row in rows]
    return {
        "support": total,
        "top1": top1 / total,
        "top1_count": top1,
        "top1_wilson95": models.wilson_interval(top1, total),
        "top2": top2 / total,
        "top2_count": top2,
        "top2_wilson95": models.wilson_interval(top2, total),
        "mean_rank": statistics.mean(ranks),
        "mean_reciprocal_rank": statistics.mean(1 / rank for rank in ranks),
        "per_class": per_class,
    }


def _write_ensemble_predictions(path, ensemble_predictions):
    fields = [
        "method", "experiment_id", "actual_link", "rank1_link", "rank2_link",
        "rank3_link", "rank", "top1_hit", "top2_hit", "mean_seed_scores_json",
    ]
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for method, rows in ensemble_predictions.items():
            for row in rows:
                writer.writerow({
                    "method": method,
                    **{
                        key: row[key] for key in fields
                        if key not in {"method", "mean_seed_scores_json"}
                    },
                    "mean_seed_scores_json": json.dumps(
                        row["mean_seed_scores"], separators=(",", ":")
                    ),
                })


def evaluate(graph_path, candidate_path, reference_path, output_dir, seeds=None):
    graph_path, candidate_path, reference_path, output_dir = map(
        Path, (graph_path, candidate_path, reference_path, output_dir)
    )
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite grouped graph evaluation: {output_dir}")
    for path in (graph_path, candidate_path, reference_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    seeds = tuple(models.SEEDS if seeds is None else map(int, seeds))
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("At least one unique initialization seed is required")

    candidate_hash = sha256(candidate_path)
    graph_hash = sha256(graph_path)
    examples, feature_names, payload = models.prepare_examples(graph_path)
    if payload.get("source_sha256") != candidate_hash:
        raise ValueError("Graph snapshots do not match the candidate dataset hash")
    experiment_ids = tuple(sorted(examples))
    reference = _read_reference(reference_path, experiment_ids, candidate_hash)
    predictions = []
    feature_policies = []
    fit_count = 0
    total_fits = len(experiment_ids) * len(models.MODEL_FACTORIES) * len(seeds)
    for fold, (held_out, train_ids) in enumerate(ordered_loo_splits(experiment_ids), start=1):
        active, means, stds = models.fit_feature_policy(examples, train_ids)
        feature_policies.append({
            "fold": fold,
            "held_out_experiment_id": held_out,
            "train_experiment_ids": ";".join(map(str, train_ids)),
            "active_features": ";".join(feature_names[index] for index in active),
        })
        for method in models.MODEL_FACTORIES:
            for seed in seeds:
                rows, _ = models.train_and_predict(
                    examples, active, means, stds, seed, method, output_dir.parent,
                    train_ids=train_ids,
                    test_ids=(held_out,),
                    save_checkpoint=False,
                )
                prediction = rows[0]
                prediction.update({
                    "fold": fold,
                    "train_experiment_ids": ";".join(map(str, train_ids)),
                })
                predictions.append(prediction)
                fit_count += 1
        print(
            f"Completed grouped LOEO fold {fold}/{len(experiment_ids)} "
            f"(held out {held_out}; {fit_count}/{total_fits} model fits)",
            file=sys.stderr,
            flush=True,
        )

    summaries = {}
    ensemble_predictions = {}
    for method in models.MODEL_FACTORIES:
        method_rows = [row for row in predictions if row["method"] == method]
        per_seed = {}
        for seed in seeds:
            selected = [row for row in method_rows if row["seed"] == seed]
            per_seed[str(seed)] = _metrics(selected)
        averaged = []
        for experiment_id in experiment_ids:
            selected = [
                row for row in method_rows if row["experiment_id"] == experiment_id
            ]
            if len(selected) != len(seeds):
                raise AssertionError("Missing seed prediction for a held-out experiment")
            scores = np.mean(np.asarray([row["scores"] for row in selected]), axis=0)
            actual_link = selected[0]["actual_link"]
            ranked, rank = models.score_ranking(
                scores, models.LINKS.index(actual_link)
            )
            averaged.append({
                "experiment_id": experiment_id,
                "actual_link": actual_link,
                "rank1_link": models.LINKS[ranked[0]],
                "rank2_link": models.LINKS[ranked[1]],
                "rank3_link": models.LINKS[ranked[2]],
                "rank": rank,
                "top1_hit": rank == 1,
                "top2_hit": rank <= 2,
                "mean_seed_scores": scores.tolist(),
            })
        ensemble_predictions[method] = averaged
        summaries[method] = {
            "seed_metrics": per_seed,
            "mean_seed_top1": statistics.mean(
                value["top1"] for value in per_seed.values()
            ),
            "sd_seed_top1": statistics.stdev(
                value["top1"] for value in per_seed.values()
            ) if len(per_seed) > 1 else 0.0,
            "mean_seed_top2": statistics.mean(
                value["top2"] for value in per_seed.values()
            ),
            "mean_seed_mrr": statistics.mean(
                value["mean_reciprocal_rank"] for value in per_seed.values()
            ),
            "mean_score_ensemble_metrics": _metrics(averaged),
        }

    reference_summary = {}
    for method, by_id in reference.items():
        rows = []
        for experiment_id in experiment_ids:
            row = by_id[experiment_id]
            rank1, rank2 = row["rank1_link"], row["rank2_link"]
            truth = examples[experiment_id]["label"]
            actual = models.LINKS[truth]
            if row.get("actual_link") != actual:
                raise ValueError(f"Reference ground-truth mismatch for experiment {experiment_id}")
            rows.append({
                "experiment_id": experiment_id,
                "actual_link": actual,
                "rank1_link": rank1,
                "rank2_link": rank2,
                "rank3_link": row.get("rank3_link", next(
                    link for link in models.LINKS if link not in {rank1, rank2}
                )),
                "rank": 1 if rank1 == actual else 2 if rank2 == actual else 3,
            })
        reference_summary[method] = _metrics(rows)

    output_dir.mkdir(parents=True, exist_ok=False)
    prediction_fields = [
        "fold", "seed", "method", "experiment_id", "train_experiment_ids",
        "actual_link", "rank1_link", "rank2_link", "rank3_link", "rank",
        "top1_hit", "top2_hit", "fault_window_snapshots", "scores_json",
    ]
    with (output_dir / "per_seed_predictions.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=prediction_fields, lineterminator="\n")
        writer.writeheader()
        for row in predictions:
            writer.writerow({
                **{key: row[key] for key in prediction_fields if key != "scores_json"},
                "scores_json": json.dumps(row["scores"], separators=(",", ":")),
            })
    _write_ensemble_predictions(
        output_dir / "mean_seed_ensemble_predictions.csv",
        ensemble_predictions,
    )
    with (output_dir / "fold_feature_policy.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(feature_policies[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(feature_policies)
    summary = {
        "task": "conditional fault-window link localization; phase selects first ten seconds",
        "protocol": "leave-one-logical-experiment-out; held-out experiment excluded from training and normalization",
        "online_detection": False,
        "candidate_sha256": candidate_hash,
        "graph_snapshot_sha256": graph_hash,
        "experiment_count": len(experiment_ids),
        "independent_test_experiments": len(experiment_ids),
        "train_count_per_fold": len(experiment_ids) - 1,
        "test_count_per_fold": 1,
        "experiment_ids": experiment_ids,
        "class_support": {
            link: sum(examples[value]["label"] == index for value in experiment_ids)
            for index, link in enumerate(models.LINKS)
        },
        "normalization_and_feature_selection": (
            "Per-fold active features, means, and standard deviations fit from "
            "training experiments' annotated fault-window switch-node telemetry only."
        ),
        "oracle_information": (
            "Annotated phase selects the first ten seconds for each example. Ground-truth "
            "link is a target only; held-out labels do not enter model fitting or normalization."
        ),
        "seeds": seeds,
        "epochs": models.EPOCHS,
        "methods": summaries,
        "same_fold_reference_baselines": reference_summary,
        "split_assignments": feature_policies,
        "limitations": [
            "25 independent experiments from one controlled topology",
            "initialization seeds are repeated fits, not independent test experiments",
            "conditional localization with oracle fault-window selection",
            "no claim of causal propagation or operational root-cause identification",
        ],
    }
    summary["output_sha256"] = {
        path.name: sha256(path) for path in output_dir.iterdir() if path.is_file()
    }
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = evaluate(args.graph, args.candidate, args.reference, args.output_dir)
    print(json.dumps(result["methods"], indent=2))


if __name__ == "__main__":
    main()
