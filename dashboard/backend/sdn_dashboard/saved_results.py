"""Read-only access to the saved, audited research results.

Everything here is loaded from the existing artifacts under results/ and the
frozen four-switch directories. Nothing is recomputed or rewritten; values are
labelled as saved evaluation results by the API.
"""

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from linear_topology import LinearTopology

from . import config

METHOD_LABELS = {
    "rf_baseline": "Random Forest",
    "topology_link_ranker": "Topology ranker",
    "graph_only": "GCN",
    "temporal_only": "LSTM",
    "graph_temporal": "GCN+LSTM",
}
NEURAL_METHODS = ("graph_only", "temporal_only", "graph_temporal")
EXPERIMENT_FILE_RE = re.compile(r"^experiment_(\d+)\.(json|md)$")


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def topology_spec(switches):
    topology = LinearTopology(switches)
    return {
        "switch_count": topology.switch_count,
        "nodes": list(topology.nodes),
        "switches": list(topology.switches),
        "hosts": list(topology.hosts),
        "edges": [list(edge) for edge in topology.edges],
        "candidate_links": list(topology.candidate_links),
        "candidate_count": topology.candidate_count,
        "bottleneck_link": topology.bottleneck_link,
        "bottleneck_params": topology.to_metadata()["bottleneck_params"],
        "chance_top1": 1.0 / topology.candidate_count,
        "chance_mrr": sum(1.0 / r for r in range(1, topology.candidate_count + 1)) / topology.candidate_count,
    }


@lru_cache(maxsize=1)
def comparison():
    path = config.COMPARISON_DIR / "comparison.json"
    rows = _read_json(path)
    for row in rows:
        row["top1_fraction"] = row["top1_count"] / row["valid_experiments"]
        row["top2_fraction"] = row["top2_count"] / row["valid_experiments"]
    return {
        "source": str(path.relative_to(config.ROOT)),
        "kind": "saved evaluation results (grouped LOEO, conditional fault-window localization)",
        "note": ("Chance Top-1 is 1/K for K candidate links (1/3, 1/7, 1/11) and random MRR is H_K/K "
                 "(0.611, 0.370, 0.275); compare models against these, not raw percentages across topologies. "
                 "Scores are uncalibrated ranking scores and the fault window is oracle-selected."),
        "rows": rows,
        "table_markdown": (config.COMPARISON_DIR / "comparison_table.md").read_text(encoding="utf-8"),
    }


def _saved(switches):
    try:
        return config.SAVED_RESULTS[int(switches)]
    except (KeyError, ValueError):
        raise ValueError("No saved results for %r switches" % (switches,))


def evaluation(switches):
    """Per-experiment saved rankings for all five methods on one topology."""
    saved = _saved(switches)
    rf_rows = _read_csv(saved["rf_eval_dir"] / "grouped_evaluation.csv")
    neural_rows = _read_csv(saved["neural_eval_dir"] / "mean_seed_ensemble_predictions.csv")
    rf_summary = _read_json(saved["rf_eval_dir"] / "evaluation_summary.json")
    neural_summary = _read_json(saved["neural_eval_dir"] / "evaluation_summary.json")
    links = list(LinearTopology(int(switches)).candidate_links)
    per_experiment = {}
    for row in rf_rows:
        exp = int(row["experiment_id"])
        entry = per_experiment.setdefault(exp, {"experiment_id": exp, "actual_link": row["actual_link"], "methods": {}})
        scores = json.loads(row["scores_json"]) if row.get("scores_json") else {}
        entry["methods"][row["method"]] = {
            "ranking": json.loads(row["ranking_json"]),
            "scores": scores,
            "rank": int(row["rank"]),
            "top1_hit": row["top1_hit"] == "True",
            "train_experiment_ids": [int(v) for v in row["train_experiment_ids"].split(";") if v],
        }
    for row in neural_rows:
        exp = int(row["experiment_id"])
        entry = per_experiment.setdefault(exp, {"experiment_id": exp, "actual_link": row["actual_link"], "methods": {}})
        ranking = json.loads(row["ranking_json"])
        mean_scores = json.loads(row["mean_seed_scores_json"])
        entry["methods"][row["method"]] = {
            "ranking": ranking,
            "scores": {links[i]: mean_scores[i] for i in range(len(links))},
            "rank": int(row["rank"]),
            "top1_hit": row["top1_hit"] == "True",
        }
    methods = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        summary = rf_summary["methods"][method]
        methods[method] = _metric_block(summary)
    for method in NEURAL_METHODS:
        summary = neural_summary["methods"][method]["mean_score_ensemble_metrics"]
        methods[method] = _metric_block(summary)
        methods[method]["per_seed_top1"] = {
            seed: value.get("top1_count") for seed, value in neural_summary["methods"][method].get("per_seed_metrics", {}).items()
        } if isinstance(neural_summary["methods"][method].get("per_seed_metrics"), dict) else None
    return {
        "switch_count": int(switches),
        "label": saved["label"],
        "kind": "saved evaluation results",
        "candidate_links": links,
        "candidate_sha256": rf_summary.get("dataset_sha256"),
        "protocol": rf_summary.get("protocol"),
        "task": rf_summary.get("task"),
        "score_semantics": rf_summary.get("score_semantics"),
        "class_support": rf_summary.get("class_support"),
        "experiment_ids": rf_summary.get("experiment_ids"),
        "method_labels": METHOD_LABELS,
        "methods": methods,
        "per_experiment": [per_experiment[k] for k in sorted(per_experiment)],
        "sources": {
            "rf_topology": str(saved["rf_eval_dir"].relative_to(config.ROOT)),
            "neural": str(saved["neural_eval_dir"].relative_to(config.ROOT)),
        },
    }


def _metric_block(summary):
    return {
        "support": summary["support"],
        "top1_count": summary["top1_count"],
        "top2_count": summary["top2_count"],
        "top3_count": summary.get("top3_count"),
        "top1": summary["top1"],
        "top2": summary["top2"],
        "mrr": summary["mean_reciprocal_rank"],
        "top1_wilson95": summary.get("top1_wilson95"),
        "chance": summary.get("chance_level"),
        "per_class": summary.get("per_class"),
        "confusion_matrix": summary.get("confusion_matrix_rows_actual_cols_rank1"),
        "confusion_labels": summary.get("confusion_labels"),
        "top1_errors": summary.get("top1_errors"),
        "adjacent_link_error_fraction": summary.get("adjacent_link_error_fraction"),
    }


def xai_index():
    """Which explanation reports exist, per topology."""
    out = []
    for switches, saved in config.SAVED_RESULTS.items():
        xai_dir = saved["xai_dir"]
        experiments_dir = xai_dir / "experiments"
        if not experiments_dir.is_dir():
            out.append({"switch_count": switches, "available": False, "experiments": []})
            continue
        summary = _read_json(xai_dir / "xai_summary.json") if (xai_dir / "xai_summary.json").is_file() else {}
        ids = sorted({int(m.group(1)) for p in experiments_dir.iterdir() if (m := EXPERIMENT_FILE_RE.match(p.name))})
        validation = {}
        for method, block in (summary.get("methods") or {}).items():
            per = block.get("per_experiment") or []
            validation[method] = {
                "label": block.get("label", METHOD_LABELS.get(method, method)),
                "explained": block.get("explained", len(per)),
                "validation_pass_count": sum(1 for p in per if p.get("validation_pass")),
                "failed_experiments": [p["experiment_id"] for p in per if not p.get("validation_pass")],
                "attribution_on_predicted_endpoints_rate": block.get("attribution_on_predicted_endpoints_rate"),
            }
        out.append({
            "switch_count": switches,
            "available": True,
            "experiments": ids,
            "candidate_sha256": summary.get("candidate_sha256"),
            "ig_steps": summary.get("ig_steps"),
            "validation_criteria": summary.get("validation_criteria"),
            "validation": validation,
            "global_feature_importance": summary.get("global_feature_importance"),
            "score_semantics": summary.get("score_semantics"),
            "source": str(xai_dir.relative_to(config.ROOT)),
        })
    return out


def xai_experiment(switches, experiment_id):
    saved = _saved(switches)
    experiment_id = int(experiment_id)
    base = saved["xai_dir"] / "experiments" / ("experiment_%d" % experiment_id)
    json_path, md_path = base.with_suffix(".json"), base.with_suffix(".md")
    if not json_path.is_file():
        raise FileNotFoundError("No saved explanation for experiment %d on %s switches" % (experiment_id, switches))
    payload = _read_json(json_path)
    return {
        "switch_count": int(switches),
        "experiment_id": experiment_id,
        "kind": "saved explanation report",
        "source_json": str(json_path.relative_to(config.ROOT)),
        "source_markdown": str(md_path.relative_to(config.ROOT)) if md_path.is_file() else None,
        "markdown": md_path.read_text(encoding="utf-8") if md_path.is_file() else None,
        "methods": payload,
        "method_labels": METHOD_LABELS,
    }


def history():
    """Admitted experiments per topology from the saved manifests, plus raw-evidence
    exclusions. These are the historical research runs; dashboard runs are listed
    separately and are never merged into them."""
    out = []
    for switches, saved in config.SAVED_RESULTS.items():
        manifest_path = saved["candidate_dir"] / "experiment_manifest.csv"
        exclusion_path = saved["candidate_dir"] / "exclusion_report.csv"
        provenance_path = saved["candidate_dir"] / "provenance.json"
        entry = {"switch_count": switches, "label": saved["label"], "candidate_dir": str(saved["candidate_dir"].relative_to(config.ROOT))}
        if manifest_path.is_file():
            rows = _read_csv(manifest_path)
            entry["experiments"] = [{
                "experiment_id": int(r["experiment_id"]), "physical_run_id": int(r["physical_run_id"]),
                "fault_link": r["fault_link"], "normal_event": r["normal_event"], "fault_event": r["fault_event"],
                "recovery_event": r["recovery_event"], "telemetry_rows": int(r["telemetry_rows"]),
                "median_sample_interval_seconds": float(r["median_sample_interval_seconds"]) if r["median_sample_interval_seconds"] else None,
                "fault_window_10s_timestamps": int(r["fault_window_10s_timestamps"]),
                "iperf_sender_mbps": float(r["iperf_sender_mbps"]) if r["iperf_sender_mbps"] else None,
                "status": r["status"], "run_dir": r["run_dir"],
            } for r in rows]
        elif (saved["rf_eval_dir"] / "grouped_evaluation.csv").is_file():
            # Frozen four-switch candidate: no manifest; take IDs and labels from the saved evaluation rows.
            seen = {}
            for r in _read_csv(saved["rf_eval_dir"] / "grouped_evaluation.csv"):
                seen.setdefault(int(r["experiment_id"]), r["actual_link"])
            entry["experiments"] = [{"experiment_id": k, "fault_link": v, "status": "ADMITTED (frozen v3)"}
                                    for k, v in sorted(seen.items())]
            entry["note"] = "Frozen four-switch v3 candidate; see docs/DATASET_CARD_BALANCED_V3.md for its admission ledger."
        else:
            entry["experiments"] = []
        entry["excluded"] = _read_csv(exclusion_path) if exclusion_path.is_file() else []
        if provenance_path.is_file():
            provenance = _read_json(provenance_path)
            entry["dataset_sha256"] = provenance.get("dataset_sha256")
            entry["rows"] = provenance.get("rows")
            entry["experiments_per_link"] = provenance.get("experiments_per_link") or provenance.get("label_support")
        out.append(entry)
    return out
