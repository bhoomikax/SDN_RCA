"""Independent methodology audit of the 4/8/12-switch LOEO artifacts and XAI reports.

Recomputes every reported number from the per-experiment rows instead of
trusting summaries: grouped splits, leakage, denominators, candidate counts,
ranking permutations, Top-k/MRR, chance levels, seed-ensemble consistency,
RF/neural reference agreement, XAI/evaluation agreement and validation counts,
and paired experiment-level comparisons (exact two-sided sign test on
discordant Top-1 outcomes). Writes results/audit/methodology_audit.{json,md}.
"""

import argparse
import csv
import json
import math
from pathlib import Path

from linear_topology import LinearTopology


ROOT = Path(__file__).resolve().parent
NEURAL = ("graph_only", "temporal_only", "graph_temporal")
LABELS = {"rf_baseline": "RF", "topology_link_ranker": "Topology ranker", "graph_only": "GCN",
          "temporal_only": "LSTM", "graph_temporal": "GCN+LSTM"}


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sign_test_p(discordant_a, discordant_b):
    n = discordant_a + discordant_b
    if n == 0:
        return 1.0
    k = min(discordant_a, discordant_b)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def audit_topology(name, switch_count, candidate_csv, rf_dir, neural_dir, xai_dir, static_mapping):
    topology = LinearTopology(switch_count)
    links = list(topology.candidate_links)
    checks, problems = [], []

    def check(label, ok, detail=""):
        checks.append({"check": label, "pass": bool(ok), "detail": detail})
        if not ok:
            problems.append(label + (": " + detail if detail else ""))

    # ---- dataset: one label per experiment, labels are candidates, phases
    rows = read_csv(candidate_csv)
    ids = sorted({int(r["experiment_id"]) for r in rows})
    labels = {}
    for r in rows:
        if r["phase"] == "fault":
            labels.setdefault(int(r["experiment_id"]), set()).add(r["fault_location"])
    check("every experiment has exactly one fault label", all(len(v) == 1 for v in labels.values()) and set(labels) == set(ids))
    labels = {k: next(iter(v)) for k, v in labels.items()}
    check("all labels are candidate links", set(labels.values()) <= set(links), str(sorted(set(labels.values()) - set(links))))
    check("candidate count is N-1", len(links) == switch_count - 1, "%d" % len(links))
    check("every switch appears in telemetry", {r["switch"] for r in rows} == set(topology.switches))
    n = len(ids)

    # ---- RF / topology evaluation
    rf_rows = read_csv(Path(rf_dir) / "grouped_evaluation.csv")
    rf_summary = json.loads((Path(rf_dir) / "evaluation_summary.json").read_text(encoding="utf-8"))
    per_method_outcomes = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        sel = [r for r in rf_rows if r["method"] == method]
        held = sorted(int(r["experiment_id"]) for r in sel)
        check("%s: each experiment held out exactly once" % method, held == ids, "%d rows vs %d experiments" % (len(sel), n))
        leak = [r for r in sel if r["experiment_id"] in r["train_experiment_ids"].split(";")]
        check("%s: held-out never in training" % method, not leak)
        sizes = {len(r["train_experiment_ids"].split(";")) for r in sel}
        check("%s: training size is n-1" % method, sizes == {n - 1}, str(sizes))
        perm_ok, rank_ok, top1, top2, mrr = True, True, 0, 0, 0.0
        outcomes = {}
        for r in sel:
            ranking = json.loads(r["ranking_json"])
            perm_ok &= sorted(ranking) == sorted(links)
            rank = ranking.index(r["actual_link"]) + 1
            rank_ok &= rank == int(r["rank"]) and r["rank1_link"] == ranking[0]
            rank_ok &= r["actual_link"] == labels[int(r["experiment_id"])]
            top1 += rank == 1
            top2 += rank <= 2
            mrr += 1.0 / rank
            outcomes[int(r["experiment_id"])] = rank == 1
        per_method_outcomes[method] = outcomes
        check("%s: rankings are permutations of the candidates" % method, perm_ok)
        check("%s: rank columns consistent with ranking and labels" % method, rank_ok)
        s = rf_summary["methods"][method]
        check("%s: summary denominators = %d" % (method, n), s["support"] == n)
        check("%s: summary Top-1/Top-2/MRR recomputed" % method,
              s["top1_count"] == top1 and s["top2_count"] == top2 and abs(s["mean_reciprocal_rank"] - mrr / n) < 1e-9,
              "recomputed %d/%d/%.4f vs %d/%d/%.4f" % (top1, top2, mrr / n, s["top1_count"], s["top2_count"], s["mean_reciprocal_rank"]))
        check("%s: chance Top-1 reported as 1/%d" % (method, len(links)), abs(s["chance_level"]["uniform_top1"] - 1 / len(links)) < 1e-12)
    check("score semantics stated as uncalibrated", "uncalibrated" in rf_summary.get("score_semantics", ""))
    policy = read_csv(Path(rf_dir) / "fold_feature_policy.csv")
    check("feature policy recorded per fold from training experiments only",
          all(str(p["held_out_experiment_id"]) not in p["training_normal_experiments"].split(";") for p in policy) and len(policy) == n)

    # ---- neural evaluation
    neural_summary = json.loads((Path(neural_dir) / "evaluation_summary.json").read_text(encoding="utf-8"))
    seed_rows = read_csv(Path(neural_dir) / "per_seed_predictions.csv")
    ens_rows = read_csv(Path(neural_dir) / "mean_seed_ensemble_predictions.csv")
    seeds = neural_summary["seeds"]
    check("neural: candidate hash matches dataset", neural_summary["candidate_sha256"] == rf_summary["dataset_sha256"])
    for method in NEURAL:
        sel = [r for r in seed_rows if r["method"] == method]
        check("%s: per-seed rows = n x seeds" % method, len(sel) == n * len(seeds), "%d" % len(sel))
        check("%s: held-out never in training (per seed)" % method,
              all(r["experiment_id"] not in r["train_experiment_ids"].split(";") and len(r["train_experiment_ids"].split(";")) == n - 1 for r in sel))
        ens = {int(r["experiment_id"]): r for r in ens_rows if r["method"] == method}
        check("%s: ensemble covers each experiment once" % method, sorted(ens) == ids)
        mean_ok, perm_ok, top1, top2, mrr = True, True, 0, 0, 0.0
        outcomes = {}
        for exp_id, r in ens.items():
            scores = [json.loads(x["scores_json"]) for x in sel if int(x["experiment_id"]) == exp_id]
            mean = [sum(col) / len(col) for col in zip(*scores)]
            saved = json.loads(r["mean_seed_scores_json"])
            mean_ok &= len(scores) == len(seeds) and all(abs(a - b) < 1e-9 for a, b in zip(mean, saved))
            ranking = json.loads(r["ranking_json"])
            perm_ok &= sorted(ranking) == sorted(links)
            expected_order = sorted(range(len(links)), key=lambda i: (-saved[i], links[i]))
            perm_ok &= [links[i] for i in expected_order] == ranking
            rank = ranking.index(labels[exp_id]) + 1
            perm_ok &= rank == int(r["rank"]) and r["actual_link"] == labels[exp_id]
            top1 += rank == 1
            top2 += rank <= 2
            mrr += 1.0 / rank
            outcomes[exp_id] = rank == 1
        per_method_outcomes[method] = outcomes
        check("%s: ensemble scores are the seed means" % method, mean_ok)
        check("%s: ensemble rankings derive from scores and match labels" % method, perm_ok)
        m = neural_summary["methods"][method]["mean_score_ensemble_metrics"]
        check("%s: summary Top-1/Top-2/MRR recomputed" % method,
              m["top1_count"] == top1 and m["top2_count"] == top2 and abs(m["mean_reciprocal_rank"] - mrr / n) < 1e-9 and m["support"] == n,
              "recomputed %d/%d/%.4f" % (top1, top2, mrr / n))
    for method in ("rf_baseline", "topology_link_ranker"):
        ref = neural_summary["same_fold_reference_baselines"][method]
        s = rf_summary["methods"][method]
        check("neural summary's same-fold %s reference equals the RF/topology evaluation" % method,
              ref["top1_count"] == s["top1_count"] and ref["top2_count"] == s["top2_count"])

    # ---- seen vs unseen held-out classes
    unseen = [e for e in ids if sum(1 for o in ids if o != e and labels[o] == labels[e]) == 0]
    check("held-out classes seen in training (count of unseen listed)", True,
          "%d of %d experiments have a fault link that no training experiment shares" % (len(unseen), n))
    seen_ids = [e for e in ids if e not in unseen]
    seen_breakdown = {}
    for method, outcomes in per_method_outcomes.items():
        seen_breakdown[method] = {"seen_top1": sum(outcomes[e] for e in seen_ids), "seen_n": len(seen_ids),
                                  "unseen_top1": sum(outcomes[e] for e in unseen), "unseen_n": len(unseen)}

    # ---- paired comparisons (experiment-level, exact sign test on discordant pairs)
    paired = []
    methods = list(per_method_outcomes)
    for i, a in enumerate(methods):
        for b in methods[i + 1:]:
            oa, ob = per_method_outcomes[a], per_method_outcomes[b]
            a_only = sum(oa[e] and not ob[e] for e in ids)
            b_only = sum(ob[e] and not oa[e] for e in ids)
            paired.append({"a": LABELS[a], "b": LABELS[b], "a_correct_b_wrong": a_only, "b_correct_a_wrong": b_only,
                           "both_correct": sum(oa[e] and ob[e] for e in ids), "both_wrong": sum((not oa[e]) and (not ob[e]) for e in ids),
                           "exact_sign_test_p_two_sided": round(sign_test_p(a_only, b_only), 4)})

    # ---- XAI
    xai = {}
    if xai_dir and (Path(xai_dir) / "xai_summary.json").is_file():
        xs = json.loads((Path(xai_dir) / "xai_summary.json").read_text(encoding="utf-8"))
        check("xai: candidate hash matches dataset", xs["candidate_sha256"] == rf_summary["dataset_sha256"])
        explained = xs["experiments_explained"]
        check("xai: every experiment explained", sorted(explained) == ids, "%d explained" % len(explained))
        agree, val_counts, fail_list, mapping_ok = True, {}, {}, True
        rf_by_id = {int(r["experiment_id"]): r for r in rf_rows if r["method"] == "rf_baseline"}
        topo_by_id = {int(r["experiment_id"]): r for r in rf_rows if r["method"] == "topology_link_ranker"}
        ens_by = {m: {int(r["experiment_id"]): r for r in ens_rows if r["method"] == m} for m in NEURAL}
        for exp_id in explained:
            report = json.loads((Path(xai_dir) / "experiments" / ("experiment_%d.json" % exp_id)).read_text(encoding="utf-8"))
            for method, e in report.items():
                saved = (rf_by_id if method == "rf_baseline" else topo_by_id if method == "topology_link_ranker" else ens_by[method])[exp_id]
                agree &= e["ranking"] == json.loads(saved["ranking_json"]) and e["ground_truth"] == labels[exp_id]
                agree &= e["top1_correct"] == (e["ranking"][0] == labels[exp_id]) and e["rank_of_truth"] == e["ranking"].index(labels[exp_id]) + 1
                v = e["validation"]
                passed = all(bool(v[k]) for k in v if k.endswith("_pass"))
                val_counts.setdefault(method, [0, 0])
                val_counts[method][0] += passed
                val_counts[method][1] += 1
                if not passed:
                    fail_list.setdefault(method, []).append({"experiment_id": exp_id, "failed": [k for k in v if k.endswith("_pass") and not v[k]]})
                for side in ("predicted", "ground_truth"):
                    link = e["ranking"][0] if side == "predicted" else labels[exp_id]
                    endpoints = e["relevant_switches_ports"][side]["endpoints"]
                    mapping_ok &= e["relevant_switches_ports"][side]["link"] == link and {ep.split(" port ")[0] for ep in endpoints} == set(link.split("-"))
                if method == "rf_baseline":
                    mapping_ok &= set(e["feature_values"]) == set(rf_summary["predictors"]["rf_features"])
                    pa = e["predicted_class_attribution"]
                    mapping_ok &= abs(pa["base_value"] + sum(e["all_shap_values"][f][pa["class"]] for f in e["all_shap_values"]) - pa["score"]) < 1e-6
                if method in NEURAL:
                    mapping_ok &= set(e["ig_per_switch_signed"]) == set(topology.switches)
                    mapping_ok &= abs(sum(e["ig_per_switch_signed"].values()) - v["completeness_sum_attributions"]) < 1e-6
                    mapping_ok &= abs(v["completeness_f_x"] - e["scores"][e["explained_class"]]) < 1e-6
                    mapping_ok &= "not causal" in " ".join(e["limitations"]).lower() or "causal" in " ".join(e["limitations"]).lower()
        check("xai: rankings, truth, and Top-1 status agree with the evaluation rows", agree)
        check("xai: feature/switch/port mappings and identity checks recomputed", mapping_ok)
        summary_counts = {m: (d["validation_pass_count"], d["explained"]) for m, d in xs["methods"].items()}
        check("xai: summary pass counts equal recounted per-report results",
              all(tuple(val_counts[m]) == summary_counts[m] for m in summary_counts), str(val_counts))
        xai = {"validation_pass_counts": {m: "%d/%d" % tuple(c) for m, c in val_counts.items()}, "failures": fail_list,
               "ig_steps": xs.get("ig_steps"), "methods": {m: d.get("label") for m, d in xs["methods"].items()}}
    else:
        check("xai: reports present", False, "missing")

    return {"topology": name, "switch_count": switch_count, "candidate_links": len(links), "experiments": n,
            "class_support": {l: sum(v == l for v in labels.values()) for l in links},
            "unseen_class_experiments": unseen, "seen_vs_unseen_top1": seen_breakdown,
            "checks": checks, "problems": problems, "paired_top1_comparisons": paired, "xai": xai,
            "dataset_sha256": rf_summary["dataset_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "audit")
    args = parser.parse_args(argv)
    specs = [
        ("4 switches (frozen v3 via regression outputs)", 4, ROOT / "derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv",
         ROOT / "results/topology_4_switches_regression/loeo_rf_topology", ROOT / "results/topology_4_switches_regression/loeo_neural",
         ROOT / "results/xai/topology_4_switches", True),
        ("8 switches", 8, ROOT / "results/topology_8_switches/candidate/candidate_dataset.csv",
         ROOT / "results/topology_8_switches/loeo_rf_topology", ROOT / "results/topology_8_switches/loeo_neural",
         ROOT / "results/xai/topology_8_switches", False),
        ("12 switches", 12, ROOT / "results/topology_12_switches/candidate/candidate_dataset.csv",
         ROOT / "results/topology_12_switches/loeo_rf_topology", ROOT / "results/topology_12_switches/loeo_neural",
         ROOT / "results/xai/topology_12_switches", False),
    ]
    results = [audit_topology(*spec) for spec in specs if spec[2].is_file()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "methodology_audit.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    lines = ["# Methodology audit (recomputed from per-experiment artifacts)", ""]
    for r in results:
        lines += ["## %s: %d experiments, %d candidates, dataset %s" % (r["topology"], r["experiments"], r["candidate_links"], r["dataset_sha256"][:12]),
                  "", "- Checks passed: %d/%d" % (sum(c["pass"] for c in r["checks"]), len(r["checks"]))]
        if r["problems"]:
            lines += ["- PROBLEMS: " + "; ".join(r["problems"])]
        lines += ["- Class support: %s" % r["class_support"],
                  "- Experiments whose fault link is unseen in training: %d (%s)" % (len(r["unseen_class_experiments"]), r["unseen_class_experiments"] or "none"),
                  "- Top-1 on seen vs unseen classes: " + "; ".join("%s %d/%d seen, %d/%d unseen" % (LABELS[m], d["seen_top1"], d["seen_n"], d["unseen_top1"], d["unseen_n"]) for m, d in r["seen_vs_unseen_top1"].items()),
                  "- XAI validation pass counts: %s" % r["xai"].get("validation_pass_counts"),
                  "- XAI failed checks: %s" % (r["xai"].get("failures") or "none"), "",
                  "| A | B | A right, B wrong | B right, A wrong | both right | both wrong | exact sign test p |", "|---|---|---:|---:|---:|---:|---:|"]
        lines += ["| %s | %s | %d | %d | %d | %d | %.3f |" % (p["a"], p["b"], p["a_correct_b_wrong"], p["b_correct_a_wrong"], p["both_correct"], p["both_wrong"], p["exact_sign_test_p_two_sided"]) for p in r["paired_top1_comparisons"]]
        lines += [""]
    lines += ["No paired comparison is corrected for multiple testing; with n <= 25 experiments the sign test has little power, and p-values near or above 0.05 do not support a superiority claim.", ""]
    (args.output_dir / "methodology_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if not any(r["problems"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
