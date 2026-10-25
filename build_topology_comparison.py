"""Assemble the 4/8/12-switch comparison table and plot from measured LOEO outputs.

Reads only existing evaluation summaries; a topology or model without a
completed evaluation is reported as "not run" rather than filled in. Chance
levels are included because the candidate count differs per topology.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from evaluate_topology_loeo import wilson_interval  # noqa: E402


ROOT = Path(__file__).resolve().parent
MODELS = [("rf_baseline", "Random Forest"), ("topology_link_ranker", "Topology ranker"),
          ("graph_only", "GCN"), ("temporal_only", "LSTM"), ("graph_temporal", "GCN+LSTM")]
MODEL_COLORS = {"rf_baseline": "#2a78d6", "topology_link_ranker": "#eb6834", "graph_only": "#1baf7a",
                "temporal_only": "#eda100", "graph_temporal": "#6250d6"}
FOUR_SWITCH_SOURCES = {
    "rf_topology": ROOT / "evaluations" / "balanced_recollection_v3_loeo_release" / "evaluation_summary.json",
    "neural": ROOT / "evaluations" / "graph_temporal_v3_grouped_loeo_verified" / "evaluation_summary.json",
}


def _load(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _xai_status(xai_summary, method):
    if xai_summary is None or method not in xai_summary.get("methods", {}):
        return "not run"
    m = xai_summary["methods"][method]
    return "tested: %d/%d sanity checks pass" % (m["validation_pass_count"], m["explained"])


def collect_topology(switch_count, rf_topology_path, neural_path, xai_path, source_label):
    rf_summary, neural_summary, xai_summary = _load(rf_topology_path), _load(neural_path), _load(xai_path)
    candidate_count = switch_count - 1
    rows = []
    for method, label in MODELS:
        row = {"topology": "%d switches" % switch_count, "switch_count": switch_count, "candidate_links": candidate_count,
               "model": label, "method": method, "valid_experiments": None, "top1_count": None, "top2_count": None,
               "top3_count": None, "mrr": None, "top1_wilson95": None, "chance_top1": round(1 / candidate_count, 4),
               "chance_top2": round(min(1.0, 2 / candidate_count), 4),
               "chance_mrr": round(sum(1 / r for r in range(1, candidate_count + 1)) / candidate_count, 4),
               "xai_status": _xai_status(xai_summary, method), "source": source_label, "status": "not run"}
        metrics = None
        if method in ("rf_baseline", "topology_link_ranker") and rf_summary is not None:
            m = rf_summary["methods"][method]
            support = m["support"]
            if "top1_count" in m:
                metrics = m
            else:  # frozen four-switch release format
                top1, top2, top3 = (round(m[k] * support) for k in ("top1_accuracy", "top2_accuracy", "top3_accuracy"))
                mrr = None
                if neural_summary is not None:
                    mrr = neural_summary["same_fold_reference_baselines"][method]["mean_reciprocal_rank"]
                metrics = {"support": support, "top1_count": top1, "top2_count": top2, "top3_count": top3,
                           "mean_reciprocal_rank": mrr, "top1_wilson95": wilson_interval(top1, support)}
        elif method in ("graph_only", "temporal_only", "graph_temporal") and neural_summary is not None:
            metrics = neural_summary["methods"][method]["mean_score_ensemble_metrics"]
            if "top3_count" not in metrics:
                metrics = {**metrics, "top3_count": metrics["support"]}
        if metrics is not None:
            row.update({"valid_experiments": metrics["support"], "top1_count": metrics["top1_count"],
                        "top2_count": metrics["top2_count"], "top3_count": metrics.get("top3_count"),
                        "mrr": None if metrics.get("mean_reciprocal_rank") is None else round(metrics["mean_reciprocal_rank"], 4),
                        "top1_wilson95": [round(v, 3) for v in metrics["top1_wilson95"]], "status": "measured"})
        rows.append(row)
    return rows


def fmt(row, key):
    if row["status"] != "measured" or row[key] is None:
        return "not run"
    n = row["valid_experiments"]
    return "%d/%d (%.0f%%)" % (row[key], n, 100.0 * row[key] / n)


def write_outputs(rows, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["topology", "switch_count", "candidate_links", "valid_experiments", "model", "method", "top1_count",
              "top2_count", "top3_count", "mrr", "top1_wilson95", "chance_top1", "chance_top2", "chance_mrr",
              "xai_status", "status", "source"]
    with (output_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in row.items() if k in fields})
    (output_dir / "comparison.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = ["# Cross-topology comparison (grouped LOEO, conditional fault-window localization)", "",
             "Top-k and MRR are not comparable across topologies at face value: the candidate count grows with topology size, "
             "so chance Top-1 is 1/3, 1/7, and 1/11 and random MRR is 0.611, 0.370, and 0.275 for 4, 8, and 12 switches. "
             "Seeds and folds are not independent experiments; the independent unit is the experiment. "
             "Scores are uncalibrated ranking scores and the fault window is oracle-selected.", "",
             "| Topology | Valid experiments | Candidates | Model | Top-1 | Top-2 | MRR | Top-1 Wilson 95% CI | Chance Top-1 / MRR | XAI status |",
             "|---|---:|---:|---|---:|---:|---:|---|---|---|"]
    for row in rows:
        ci = "not run" if row["top1_wilson95"] is None else "[%.1f%%, %.1f%%]" % (100 * row["top1_wilson95"][0], 100 * row["top1_wilson95"][1])
        mrr = "not run" if row["mrr"] is None else "%.4f" % row["mrr"]
        lines.append("| %s | %s | %d | %s | %s | %s | %s | %s | %.3f / %.3f | %s |" % (
            row["topology"], row["valid_experiments"] if row["valid_experiments"] is not None else "not run",
            row["candidate_links"], row["model"], fmt(row, "top1_count"), fmt(row, "top2_count"), mrr, ci,
            row["chance_top1"], row["chance_mrr"], row["xai_status"]))
    (output_dir / "comparison_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot(rows, output_dir / "comparison.png")


def plot(rows, path):
    topologies = sorted({row["switch_count"] for row in rows})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), facecolor="#fcfcfb")
    width = 0.15
    for axis, key, title, chance_key in ((axes[0], "top1", "Top-1 accuracy (experiment-level LOEO)", "chance_top1"),
                                         (axes[1], "mrr", "Mean reciprocal rank", "chance_mrr")):
        axis.set_facecolor("#fcfcfb")
        for index, (method, label) in enumerate(MODELS):
            xs, ys = [], []
            for t_index, count in enumerate(topologies):
                row = next(r for r in rows if r["switch_count"] == count and r["method"] == method)
                if row["status"] != "measured" or (key == "mrr" and row["mrr"] is None):
                    continue
                value = row["top1_count"] / row["valid_experiments"] if key == "top1" else row["mrr"]
                xs.append(t_index + (index - 2) * width)
                ys.append(value)
            bars = axis.bar(xs, ys, width=width * 0.9, color=MODEL_COLORS[method], label=label, linewidth=0)
            for bar, value in zip(bars, ys):
                axis.text(bar.get_x() + bar.get_width() / 2, value + 0.012, "%.2f" % value, ha="center", va="bottom",
                          fontsize=7, color="#52514e")
        for t_index, count in enumerate(topologies):
            chance = next(r for r in rows if r["switch_count"] == count)[chance_key]
            axis.hlines(chance, t_index - 0.42, t_index + 0.42, colors="#52514e", linestyles="dotted", linewidth=1.2)
            axis.text(t_index + 0.43, chance, "chance", fontsize=7, color="#52514e", va="center")
        axis.set_xticks(range(len(topologies)))
        axis.set_xticklabels(["%d switches\n(%d candidates)" % (c, c - 1) for c in topologies])
        axis.set_ylim(0, 1.08)
        axis.set_title(title, fontsize=10, loc="left", color="#0b0b0b")
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#c3c2b7")
        axis.grid(axis="y", color="#e8e7e3", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(colors="#52514e", labelsize=8)
    axes[0].legend(frameon=False, fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(1.05, -0.18))
    fig.suptitle("Faulty-link localization across linear topology sizes (dotted: uniform-random chance level)",
                 fontsize=11, x=0.02, ha="left", color="#0b0b0b")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "comparison_4_8_12")
    args = parser.parse_args(argv)
    rows = collect_topology(4, FOUR_SWITCH_SOURCES["rf_topology"], FOUR_SWITCH_SOURCES["neural"],
                            args.results_root / "xai" / "topology_4_switches" / "xai_summary.json",
                            "frozen v3 release + verified grouped neural evaluation (existing results)")
    for count in (8, 12):
        base = args.results_root / ("topology_%d_switches" % count)
        rows += collect_topology(count, base / "loeo_rf_topology" / "evaluation_summary.json",
                                 base / "loeo_neural" / "evaluation_summary.json",
                                 args.results_root / "xai" / ("topology_%d_switches" % count) / "xai_summary.json",
                                 "new collection: %s" % base)
    write_outputs(rows, args.output_dir)
    print((args.output_dir / "comparison_table.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
