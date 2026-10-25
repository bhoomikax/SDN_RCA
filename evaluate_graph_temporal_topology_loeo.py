"""Grouped LOEO evaluation of GCN, LSTM, and GCN+LSTM localizers on an N-switch topology.

Each fold holds out one experiment; feature policy and normalization are fit on
the training experiments only; three fixed seeds are averaged as a mean-score
ensemble. Same-fold RF/topology references are read from an
evaluate_topology_loeo.py output on the same candidate. Optionally saves every
fold/seed checkpoint so explanations can be computed on the exact fitted
models. Outputs are written to a new directory only.
"""

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

import graph_temporal_topology as models
from evaluate_topology_loeo import ordered_grouped_splits, sha256, summarize
from linear_topology import LinearTopology


def read_reference(reference_dir, experiment_ids, candidate_hash, topology):
    reference_dir = Path(reference_dir)
    provenance = json.loads((reference_dir / "evaluation_provenance.json").read_text(encoding="utf-8"))
    if provenance.get("dataset_sha256") != candidate_hash:
        raise ValueError("RF/topology reference was not evaluated on the candidate dataset")
    expected = "leave-one-logical-experiment-out (%d folds)" % len(experiment_ids)
    if not provenance.get("protocol", "").startswith(expected):
        raise ValueError("RF/topology reference does not use the matching grouped LOEO split")
    with (reference_dir / "grouped_evaluation.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    results = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        selected = [row for row in rows if row["method"] == method]
        by_id = {int(row["experiment_id"]): row for row in selected}
        if len(by_id) != len(selected) or set(by_id) != set(experiment_ids):
            raise ValueError("Reference %s does not cover each LOEO experiment once" % method)
        for experiment_id, row in by_id.items():
            expected_train = ";".join(str(v) for v in experiment_ids if v != experiment_id)
            if row.get("train_experiment_ids") != expected_train:
                raise ValueError("Reference %s has an unexpected training split for experiment %d" % (method, experiment_id))
            ranking = json.loads(row["ranking_json"]) if row.get("ranking_json") else [row["rank1_link"], row["rank2_link"], row["rank3_link"]]
            if set(ranking) != set(topology.candidate_links):
                raise ValueError("Reference %s ranking does not cover the candidate links" % method)
            row["ranking"] = ranking
        results[method] = by_id
    return results


def evaluate(graph_path, candidate_path, reference_dir, output_dir, switch_count, seeds=None, save_checkpoints=False):
    topology = LinearTopology(switch_count)
    graph_path, candidate_path, output_dir = Path(graph_path), Path(candidate_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Refusing to overwrite grouped graph evaluation: %s" % output_dir)
    for path in (graph_path, candidate_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    seeds = tuple(models.SEEDS if seeds is None else map(int, seeds))
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("At least one unique initialization seed is required")
    candidate_hash = sha256(candidate_path)
    graph_hash = sha256(graph_path)
    examples, feature_names, payload = models.prepare_examples(graph_path, topology)
    if payload.get("source_sha256") != candidate_hash:
        raise ValueError("Graph snapshots do not match the candidate dataset hash")
    experiment_ids = tuple(sorted(examples))
    reference = read_reference(reference_dir, experiment_ids, candidate_hash, topology)
    links = list(topology.candidate_links)
    output_dir.mkdir(parents=True, exist_ok=False)
    checkpoint_dir = output_dir / "checkpoints" if save_checkpoints else None

    predictions, feature_policies, checkpoint_hashes = [], [], {}
    fit_count, total_fits = 0, len(experiment_ids) * len(models.MODEL_FACTORIES) * len(seeds)
    started = time.monotonic()
    fit_seconds = {method: [] for method in models.MODEL_FACTORIES}
    for fold, (held_out, train_ids) in enumerate(ordered_grouped_splits(experiment_ids), start=1):
        active, means, stds = models.fit_feature_policy(examples, train_ids, topology)
        feature_policies.append({"fold": fold, "held_out_experiment_id": held_out,
                                 "train_experiment_ids": ";".join(map(str, train_ids)),
                                 "active_features": ";".join(feature_names[i] for i in active)})
        for method in models.MODEL_FACTORIES:
            for seed in seeds:
                checkpoint = (checkpoint_dir / ("%s_fold%02d_heldout%d_seed%d.pt" % (method, fold, held_out, seed))) if checkpoint_dir else None
                fit_started = time.monotonic()
                rows, checkpoint_hash, _model = models.train_and_predict(
                    examples, active, means, stds, seed, method, topology, train_ids, (held_out,), checkpoint)
                fit_seconds[method].append(time.monotonic() - fit_started)
                if checkpoint_hash:
                    checkpoint_hashes[checkpoint.name] = checkpoint_hash
                prediction = rows[0]
                prediction.update({"fold": fold, "train_experiment_ids": ";".join(map(str, train_ids))})
                predictions.append(prediction)
                fit_count += 1
        print("Completed grouped LOEO fold %d/%d (held out %d; %d/%d fits; %.0fs elapsed)" % (
            fold, len(experiment_ids), held_out, fit_count, total_fits, time.monotonic() - started),
            file=sys.stderr, flush=True)

    summaries, ensemble_predictions = {}, {}
    for method in models.MODEL_FACTORIES:
        method_rows = [row for row in predictions if row["method"] == method]
        per_seed = {str(seed): summarize([row for row in method_rows if row["seed"] == seed], links) for seed in seeds}
        averaged = []
        for experiment_id in experiment_ids:
            selected = [row for row in method_rows if row["experiment_id"] == experiment_id]
            if len(selected) != len(seeds):
                raise AssertionError("Missing seed prediction for a held-out experiment")
            scores = np.mean(np.asarray([row["scores"] for row in selected]), axis=0)
            actual_link = selected[0]["actual_link"]
            ranked, rank = models.score_ranking(scores, links.index(actual_link), links)
            ranking = [links[idx] for idx in ranked]
            averaged.append({"experiment_id": experiment_id, "actual_link": actual_link, "rank": rank,
                             "rank1_link": ranking[0], "rank2_link": ranking[1] if len(ranking) > 1 else "",
                             "rank3_link": ranking[2] if len(ranking) > 2 else "",
                             "top1_hit": rank == 1, "top2_hit": rank <= 2, "ranking": ranking,
                             "mean_seed_scores": scores.tolist()})
        ensemble_predictions[method] = averaged
        summaries[method] = {
            "label": models.MODEL_LABELS[method],
            "seed_metrics": per_seed,
            "mean_seed_top1": statistics.mean(v["top1"] for v in per_seed.values()),
            "sd_seed_top1": statistics.stdev(v["top1"] for v in per_seed.values()) if len(per_seed) > 1 else 0.0,
            "mean_seed_top2": statistics.mean(v["top2"] for v in per_seed.values()),
            "mean_seed_mrr": statistics.mean(v["mean_reciprocal_rank"] for v in per_seed.values()),
            "mean_score_ensemble_metrics": summarize(averaged, links),
            "mean_fit_seconds": statistics.mean(fit_seconds[method]),
            "total_fit_seconds": sum(fit_seconds[method]),
        }
    reference_summary = {}
    for method, by_id in reference.items():
        rows = []
        for experiment_id in experiment_ids:
            row = by_id[experiment_id]
            actual = links[examples[experiment_id]["label"]]
            if row.get("actual_link") != actual:
                raise ValueError("Reference ground-truth mismatch for experiment %d" % experiment_id)
            ranking = row["ranking"]
            rows.append({"experiment_id": experiment_id, "actual_link": actual, "rank1_link": ranking[0],
                         "rank": ranking.index(actual) + 1})
        reference_summary[method] = summarize(rows, links)

    prediction_fields = ["fold", "seed", "method", "experiment_id", "train_experiment_ids", "actual_link",
                         "rank1_link", "rank2_link", "rank3_link", "rank", "top1_hit", "top2_hit",
                         "fault_window_snapshots", "ranking_json", "scores_json"]
    with (output_dir / "per_seed_predictions.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=prediction_fields, lineterminator="\n")
        writer.writeheader()
        for row in predictions:
            writer.writerow({**{k: row[k] for k in prediction_fields if k not in ("ranking_json", "scores_json")},
                             "ranking_json": json.dumps(row["ranking"]),
                             "scores_json": json.dumps(row["scores"], separators=(",", ":"))})
    ensemble_fields = ["method", "experiment_id", "actual_link", "rank1_link", "rank2_link", "rank3_link",
                       "rank", "top1_hit", "top2_hit", "ranking_json", "mean_seed_scores_json"]
    with (output_dir / "mean_seed_ensemble_predictions.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=ensemble_fields, lineterminator="\n")
        writer.writeheader()
        for method, rows in ensemble_predictions.items():
            for row in rows:
                writer.writerow({"method": method,
                                 **{k: row[k] for k in ensemble_fields if k not in ("method", "ranking_json", "mean_seed_scores_json")},
                                 "ranking_json": json.dumps(row["ranking"]),
                                 "mean_seed_scores_json": json.dumps(row["mean_seed_scores"], separators=(",", ":"))})
    with (output_dir / "fold_feature_policy.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(feature_policies[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(feature_policies)
    summary = {
        "task": "conditional fault-window link localization; phase selects first ten seconds",
        "protocol": "leave-one-logical-experiment-out (%d folds); held-out experiment excluded from training and normalization" % len(experiment_ids),
        "online_detection": False,
        "topology": topology.to_metadata(), "candidate_count": topology.candidate_count,
        "candidate_sha256": candidate_hash, "graph_snapshot_sha256": graph_hash,
        "experiment_count": len(experiment_ids), "independent_test_experiments": len(experiment_ids),
        "train_count_per_fold": len(experiment_ids) - 1, "test_count_per_fold": 1,
        "experiment_ids": list(experiment_ids),
        "class_support": {link: sum(examples[v]["label"] == i for v in experiment_ids) for i, link in enumerate(links)},
        "normalization_and_feature_selection": "Per-fold active features, means, and standard deviations fit from training experiments' annotated fault-window switch-node telemetry only.",
        "oracle_information": "Annotated phase selects the first ten seconds for each example. Ground-truth link is a target only.",
        "score_semantics": "Softmax outputs averaged over seeds; uncalibrated ranking scores, not calibrated probabilities.",
        "seeds": list(seeds), "epochs": models.EPOCHS,
        "architecture": {"gcn_hidden": models.HIDDEN, "gcn_embedding": models.EMBEDDING, "lstm_hidden": models.LSTM_HIDDEN,
                         "num_nodes": len(topology.nodes), "learning_rate": models.LEARNING_RATE, "weight_decay": models.WEIGHT_DECAY},
        "methods": summaries,
        "same_fold_reference_baselines": reference_summary,
        "split_assignments": feature_policies,
        "checkpoints_saved": bool(save_checkpoints), "checkpoint_sha256": checkpoint_hashes,
        "runtime": {"total_seconds": round(time.monotonic() - started, 1), "torch_threads": torch.get_num_threads(),
                    "torch": torch.__version__, "python": sys.version},
        "limitations": [
            "%d independent experiments from one controlled %d-switch topology" % (len(experiment_ids), topology.switch_count),
            "initialization seeds are repeated fits, not independent test experiments",
            "conditional localization with oracle fault-window selection",
            "no claim of causal propagation or operational root-cause identification",
            "Top-k chance level is k/%d and random MRR is %.3f for %d candidates" % (
                topology.candidate_count, sum(1 / r for r in range(1, topology.candidate_count + 1)) / topology.candidate_count, topology.candidate_count),
        ],
    }
    summary["output_sha256"] = {p.name: sha256(p) for p in output_dir.iterdir() if p.is_file()}
    (output_dir / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switches", type=int, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True,
                        help="evaluate_topology_loeo.py output directory on the same candidate")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="*", default=None)
    parser.add_argument("--save-checkpoints", action="store_true")
    args = parser.parse_args(argv)
    summary = evaluate(args.graph, args.candidate, args.reference_dir, args.output_dir, args.switches,
                       seeds=args.seeds, save_checkpoints=args.save_checkpoints)
    print(json.dumps({m: {k: summary["methods"][m]["mean_score_ensemble_metrics"][k]
                          for k in ("support", "top1_count", "top2_count", "mean_reciprocal_rank")}
                      for m in summary["methods"]}, indent=2))


if __name__ == "__main__":
    main()
