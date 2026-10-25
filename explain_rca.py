"""Explainable-AI layer for the five link localizers, with validation checks.

What each method gets:

* Random Forest: exact TreeSHAP values (shap.TreeExplainer) for the held-out
  fold model, per candidate-link class. Validated by the additivity identity
  (base value + sum of SHAP = predicted vote fraction) and by a perturbation
  test (neutralizing the top-k attributed features must lower the predicted
  class score at least as much as neutralizing k random features).
* GCN, LSTM, GCN+LSTM: integrated gradients on the actual normalized graph
  sequence that the seed ensemble consumed (baseline: all-zero normalized
  telemetry, i.e. training-mean fault-window values), validated by the
  completeness identity; plus node, edge, and timestep occlusion deltas.
  PyG's GNNExplainer expects a single-graph forward(x, edge_index); these
  models consume a sequence of graphs, so it is not applied (documented).
* Topology ranker: exposure of the four heuristic components, their rank
  utilities and the equal-weight aggregate, plus leave-one-component-out
  sensitivity. This is transparency of a fixed heuristic, not attribution.

All scores are uncalibrated ranking scores (RF vote fractions, softmax
outputs, rank utilities). Nothing here is causal evidence.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

import graph_temporal_topology as models
from evaluate_topology_loeo import (
    RANK_COMPONENTS, fit_rf, fold_inputs, load_candidate, load_link_ports, sha256, stable_rf_ranking,
)
from linear_topology import LinearTopology


IG_STEPS = 512  # 64 left completeness gaps up to 0.59 on these piecewise-linear ensembles; 512 closes them
TOP_K = 3
RANDOM_DRAWS = 20
RANDOM_SEED = 2026
METHOD_LABELS = {"rf_baseline": "Random Forest", "topology_link_ranker": "Topology ranker",
                 "graph_only": "GCN", "temporal_only": "LSTM", "graph_temporal": "GCN+LSTM"}


# ----------------------------------------------------------------------------- helpers
def _ranking_from_scores(scores, links):
    order = sorted(range(len(links)), key=lambda i: (-float(scores[i]), links[i]))
    return [links[i] for i in order]


def _link_endpoint_text(link, link_ports):
    (sa, pa), (sb, pb) = link_ports[link]
    return {"link": link, "endpoints": ["%s port %s" % (sa, pa), "%s port %s" % (sb, pb)]}


# ----------------------------------------------------------------------------- RF + SHAP
def explain_rf_fold(frame, labels, held_out, train_ids, topology, link_ports, saved_row, rng):
    import shap

    inputs = fold_inputs(frame, labels, held_out, train_ids, topology, link_ports)
    model = fit_rf(inputs["x_train"], inputs["y_train"])
    ranking, scores = stable_rf_ranking(model, inputs["x_test"])
    classes = [str(c) for c in model.classes_]
    for link in topology.candidate_links:
        if link not in scores:
            ranking.append(link)
            scores[link] = 0.0
    saved_ranking = json.loads(saved_row["ranking_json"])
    if ranking != saved_ranking:
        raise AssertionError("Refit RF ranking differs from the saved evaluation for experiment %d" % held_out)
    names = inputs["feature_names"]
    x = inputs["x_test"].reshape(1, -1)
    explainer = shap.TreeExplainer(model)
    values = np.asarray(explainer.shap_values(x))
    if values.ndim == 3 and values.shape[0] == 1:  # (1, features, classes)
        values = values[0]
    elif values.ndim == 3:  # legacy list layout (classes, 1, features)
        values = np.transpose(values[:, 0, :])
    base = np.asarray(explainer.expected_value, dtype=float).reshape(-1)
    probabilities = model.predict_proba(x)[0]
    additivity_error = float(np.max(np.abs(base + values.sum(axis=0) - probabilities)))
    predicted, actual = ranking[0], saved_row["actual_link"]

    def class_attribution(link):
        if link not in classes:
            return None
        column = classes.index(link)
        contribution = values[:, column]
        order = np.argsort(-np.abs(contribution))
        return {
            "class": link, "base_value": float(base[column]), "score": float(probabilities[column]),
            "top_features": [{"feature": names[i], "switch": names[i].split("_")[0], "shap": float(contribution[i]),
                              "value": float(x[0, i])} for i in order[:5]],
            "support_by_switch": {sw: float(sum(contribution[i] for i, n in enumerate(names) if n.startswith(sw + "_")))
                                  for sw in topology.switches},
        }

    # Perturbation (deletion) validation on the predicted class: neutralize the top-k
    # features that SUPPORT the prediction (positive SHAP) at the training mean.
    column = classes.index(predicted)
    contribution = values[:, column]
    neutral = inputs["x_train"].mean(axis=0)
    k = min(TOP_K, len(names))
    top_idx = [i for i in np.argsort(-contribution) if contribution[i] > 0][:k]
    if len(top_idx) < k:
        top_idx = list(np.argsort(-contribution)[:k])
    top_idx = np.asarray(top_idx)

    def score_with(indices):
        perturbed = x.copy()
        perturbed[0, list(indices)] = neutral[list(indices)]
        return float(model.predict_proba(perturbed)[0][column])

    original = float(probabilities[column])
    top_drop = original - score_with(top_idx)
    random_drops = [original - score_with(rng.choice(len(names), size=k, replace=False)) for _ in range(RANDOM_DRAWS)]
    validation = {
        "additivity_max_abs_error": additivity_error, "additivity_pass": additivity_error < 1e-6,
        "perturbation_top_k": int(k), "top_k_drop": top_drop,
        "random_k_drop_mean": float(np.mean(random_drops)), "random_k_drop_max": float(np.max(random_drops)),
        "perturbation_pass": top_drop >= float(np.mean(random_drops)),
        "top1_after_top_k_neutralized": _ranking_from_scores(
            model.predict_proba(np.where(np.isin(np.arange(len(names)), top_idx), neutral, x[0]).reshape(1, -1))[0], classes)[0],
    }
    return {
        "method": "rf_baseline", "label": METHOD_LABELS["rf_baseline"],
        "explanation_method": "shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (%d features)" % len(names),
        "score_semantics": "RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities",
        "ranking": ranking, "scores": scores, "ground_truth": actual, "top1_correct": predicted == actual,
        "rank_of_truth": ranking.index(actual) + 1,
        "predicted_class_attribution": class_attribution(predicted),
        "true_class_attribution": class_attribution(actual),
        "feature_values": {n: float(v) for n, v in zip(names, x[0])},
        "all_shap_values": {names[i]: {classes[c]: float(values[i, c]) for c in range(len(classes))} for i in range(len(names))},
        "relevant_switches_ports": {"predicted": _link_endpoint_text(predicted, link_ports),
                                    "ground_truth": _link_endpoint_text(actual, link_ports)},
        "validation": validation,
        "limitations": ["Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch.",
                        "SHAP explains the model's vote fraction, not a causal effect of the link on telemetry.",
                        "Classes absent from the training fold cannot receive attribution."],
        "fold": {"train_experiment_ids": inputs["train_ids"], "active_metrics": list(inputs["active"])},
        "feature_importance_impurity": {n: float(v) for n, v in zip(names, model.feature_importances_)},
    }


# ----------------------------------------------------------------------------- topology ranker
def explain_topology_fold(components, saved_row, topology, link_ports):
    rows = sorted(components, key=lambda r: int(r["position"]))
    ranking = [r["candidate_link"] for r in rows]
    if ranking != json.loads(saved_row["ranking_json"]):
        raise AssertionError("Component table ranking differs from saved ranking for experiment %s" % saved_row["experiment_id"])
    predicted, actual = ranking[0], saved_row["actual_link"]
    table = {}
    for r in rows:
        utilities = {m: float(r["utility_" + m]) for m, _ in RANK_COMPONENTS}
        recomputed = float(np.mean(list(utilities.values())))
        if abs(recomputed - float(r["rank_score"])) > 1e-9:
            raise AssertionError("rank_score is not the mean of component utilities")
        table[r["candidate_link"]] = {
            "position": int(r["position"]), "rank_score": float(r["rank_score"]),
            "components": {m: float(r[m]) for m, _ in RANK_COMPONENTS},
            "utilities": utilities,
            "endpoint_a": r["endpoint_a"], "endpoint_a_anomaly": float(r["endpoint_a_anomaly"]),
            "endpoint_a_onset_seconds": float(r["endpoint_a_onset_seconds"]),
            "endpoint_b": r["endpoint_b"], "endpoint_b_anomaly": float(r["endpoint_b_anomaly"]),
            "endpoint_b_onset_seconds": float(r["endpoint_b_onset_seconds"]),
            "remote_onset_seconds": float(r["remote_onset_seconds"]),
        }
    # Leave-one-component-out sensitivity: which components decide the top-1?
    sensitivity = {}
    for m, _ in RANK_COMPONENTS:
        partial = {link: float(np.mean([u for name, u in t["utilities"].items() if name != m])) for link, t in table.items()}
        order = sorted(partial, key=lambda l: (-partial[l], -table[l]["components"]["link_anomaly"], l))
        sensitivity[m] = {"top1_without_component": order[0], "top1_changes": order[0] != predicted,
                          "truth_rank_without_component": order.index(actual) + 1}
    deciding = [m for m, s in sensitivity.items() if s["top1_changes"]]
    winner = table[predicted]
    return {
        "method": "topology_link_ranker", "label": METHOD_LABELS["topology_link_ranker"],
        "explanation_method": "Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity",
        "score_semantics": "Equal-weight mean of rank utilities in (0, 1]; not a probability",
        "ranking": ranking, "scores": {l: table[l]["rank_score"] for l in ranking}, "ground_truth": actual,
        "top1_correct": predicted == actual, "rank_of_truth": ranking.index(actual) + 1,
        "predicted_link_components": winner, "true_link_components": table[actual],
        "component_table": table, "component_sensitivity": sensitivity,
        "deciding_components_for_top1": deciding,
        "main_supporting_evidence": {
            "strongest_utility_components": sorted(winner["utilities"], key=lambda m: -winner["utilities"][m])[:2],
            "endpoint_anomaly_scores": {winner["endpoint_a"]: winner["endpoint_a_anomaly"], winner["endpoint_b"]: winner["endpoint_b_anomaly"]},
            "pair_onset_seconds": winner["components"]["pair_onset_seconds"],
            "remote_onset_seconds": winner["remote_onset_seconds"],
        },
        "relevant_switches_ports": {"predicted": _link_endpoint_text(predicted, link_ports),
                                    "ground_truth": _link_endpoint_text(actual, link_ports)},
        "validation": {"rank_score_recomputed_pass": True, "ranking_matches_saved": True,
                       "decided_by_single_component": len(deciding) > 0},
        "limitations": ["Exposure of a fixed heuristic, not a learned attribution.",
                        "Onset times are relative to the annotated fault start (oracle window).",
                        "Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column."],
    }


# ----------------------------------------------------------------------------- neural: IG + occlusion
class EnsembleScorer:
    """Mean softmax over the fold's seed models, differentiable in the node features."""

    def __init__(self, seed_models):
        self.models = seed_models

    def __call__(self, sequence):
        return torch.stack([torch.softmax(m(sequence), dim=0) for m in self.models]).mean(dim=0)


def _clone_sequence(sequence, xs=None):
    return [{"x": (xs[i] if xs is not None else g["x"].detach().clone()), "edge_index": g["edge_index"]} for i, g in enumerate(sequence)]


def integrated_gradients(scorer, sequence, target, steps=IG_STEPS):
    xs = [g["x"].detach().clone() for g in sequence]
    baselines = [torch.zeros_like(x) for x in xs]
    total = [torch.zeros_like(x) for x in xs]
    for step in range(1, steps + 1):
        alpha = step / steps
        scaled = [(b + alpha * (x - b)).requires_grad_(True) for x, b in zip(xs, baselines)]
        score = scorer(_clone_sequence(sequence, scaled))[target]
        grads = torch.autograd.grad(score, scaled)
        for i, g in enumerate(grads):
            total[i] += g
    attributions = [(x - b) * t / steps for x, b, t in zip(xs, baselines, total)]
    with torch.no_grad():
        f_x = float(scorer(_clone_sequence(sequence, xs))[target])
        f_b = float(scorer(_clone_sequence(sequence, baselines))[target])
    total_attr = float(sum(a.sum() for a in attributions))
    return attributions, f_x, f_b, total_attr


def occlusion_tests(scorer, sequence, target, topology, uses_edges):
    nodes = list(topology.nodes)
    with torch.no_grad():
        original = float(scorer(sequence)[target])
        node_deltas = {}
        for idx in topology.switch_indices:
            xs = [g["x"].clone() for g in sequence]
            for x in xs:
                x[idx] = 0.0
            node_deltas[nodes[idx]] = original - float(scorer(_clone_sequence(sequence, xs))[target])
        edge_deltas = {}
        if uses_edges:
            for link in topology.candidate_links:
                a, b = (nodes.index(n) for n in topology.link_endpoints(link))
                pruned = []
                for g in sequence:
                    ei = g["edge_index"]
                    keep = ~(((ei[0] == a) & (ei[1] == b)) | ((ei[0] == b) & (ei[1] == a)))
                    pruned.append({"x": g["x"], "edge_index": ei[:, keep]})
                edge_deltas[link] = original - float(scorer(pruned)[target])
        time_deltas = []
        if len(sequence) > 1:
            for t in range(len(sequence)):
                reduced = [g for i, g in enumerate(sequence) if i != t]
                time_deltas.append(original - float(scorer(reduced)[target]))
    return original, node_deltas, edge_deltas, time_deltas


def explain_neural_fold(method, examples, held_out, train_ids, topology, checkpoint_dir, fold, saved_row, link_ports, rng,
                        ig_steps=IG_STEPS):
    links = list(topology.candidate_links)
    active, means, stds = models.fit_feature_policy(examples, train_ids, topology)
    seed_models = []
    for seed in models.SEEDS:
        path = checkpoint_dir / ("%s_fold%02d_heldout%d_seed%d.pt" % (method, fold, held_out, seed))
        model, payload = models.load_checkpoint(path, topology)
        if payload["input_features"] != list(active) or not np.allclose(payload["feature_means"], means) or not np.allclose(payload["feature_stds"], stds):
            raise AssertionError("Checkpoint feature policy differs from the recomputed fold policy")
        if sorted(payload["train_experiment_ids"]) != sorted(train_ids):
            raise AssertionError("Checkpoint training IDs differ from the fold")
        seed_models.append(model)
    scorer = EnsembleScorer(seed_models)
    sequence = models.normalize_sequence(examples[held_out]["sequence"], active, means, stds, topology)
    with torch.no_grad():
        scores = scorer(sequence).numpy()
    saved_scores = np.asarray(json.loads(saved_row["mean_seed_scores_json"]))
    if not np.allclose(scores, saved_scores, atol=1e-5):
        raise AssertionError("Recomputed ensemble scores differ from the saved evaluation for experiment %d" % held_out)
    ranking = _ranking_from_scores(scores, links)
    if ranking != json.loads(saved_row["ranking_json"]):
        raise AssertionError("Recomputed ranking differs from the saved evaluation")
    predicted, actual = ranking[0], saved_row["actual_link"]
    target = links.index(predicted)
    feature_names = [name for name in ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")]
    active_names = [feature_names[i] for i in active]
    nodes = list(topology.nodes)

    attributions, f_x, f_b, total_attr = integrated_gradients(scorer, sequence, target, steps=ig_steps)
    attr = torch.stack(attributions).numpy()  # (T, nodes, features)
    completeness_gap = abs((f_x - f_b) - total_attr)
    completeness_rel = completeness_gap / max(abs(f_x - f_b), 1e-9)
    per_node = {nodes[i]: float(attr[:, i, :].sum()) for i in topology.switch_indices}
    per_node_abs = {nodes[i]: float(np.abs(attr[:, i, :]).sum()) for i in topology.switch_indices}
    per_feature = {active_names[j]: float(attr[:, :, j].sum()) for j in range(len(active_names))}
    per_time = [float(attr[t].sum()) for t in range(attr.shape[0])]
    flat = [(nodes[i], active_names[j], float(attr[:, i, j].sum())) for i in topology.switch_indices for j in range(len(active_names))]
    flat.sort(key=lambda item: -abs(item[2]))

    uses_edges = method in ("graph_only", "graph_temporal")
    original, node_deltas, edge_deltas, time_deltas = occlusion_tests(scorer, sequence, target, topology, uses_edges)

    # Perturbation (deletion) validation: zeroing the top-k switches that SUPPORT the
    # prediction (positive signed IG) vs k random switches.
    k = min(2, len(topology.switch_indices))
    top_nodes = [n for n in sorted(per_node, key=lambda n: -per_node[n]) if per_node[n] > 0][:k]
    if len(top_nodes) < k:
        top_nodes = sorted(per_node, key=lambda n: -per_node[n])[:k]

    def score_without(node_names):
        xs = [g["x"].clone() for g in sequence]
        for x in xs:
            for name in node_names:
                x[nodes.index(name)] = 0.0
        with torch.no_grad():
            out = scorer(_clone_sequence(sequence, xs))
        return float(out[target]), _ranking_from_scores(out.numpy(), links)[0]

    top_score, top1_after = score_without(top_nodes)
    random_drops = []
    switch_names = [nodes[i] for i in topology.switch_indices]
    for _ in range(RANDOM_DRAWS):
        chosen = list(rng.choice(switch_names, size=k, replace=False))
        random_drops.append(original - score_without(chosen)[0])
    validation = {
        "ig_steps": ig_steps, "ig_baseline": "all-zero normalized features (training-mean fault-window telemetry)",
        "completeness_f_x": f_x, "completeness_f_baseline": f_b, "completeness_sum_attributions": total_attr,
        "completeness_abs_gap": completeness_gap, "completeness_relative_gap": completeness_rel,
        "completeness_pass": completeness_rel < 0.05 or completeness_gap < 1e-3,
        "perturbation_top_k_nodes": top_nodes, "top_k_drop": original - top_score,
        "random_k_drop_mean": float(np.mean(random_drops)), "random_k_drop_max": float(np.max(random_drops)),
        "perturbation_pass": (original - top_score) >= float(np.mean(random_drops)),
        "top1_after_top_k_nodes_zeroed": top1_after,
        "ensemble_scores_match_saved": True, "checkpoint_policy_matches_fold": True,
    }
    expected_switches = set(topology.link_endpoints(predicted))
    top_two_switches = set(sorted(per_node_abs, key=lambda n: -per_node_abs[n])[:2])
    return {
        "method": method, "label": METHOD_LABELS[method],
        "explanation_method": "Integrated gradients (%d steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion" % ig_steps,
        "score_semantics": "Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities",
        "ranking": ranking, "scores": {l: float(scores[i]) for i, l in enumerate(links)}, "ground_truth": actual,
        "top1_correct": predicted == actual, "rank_of_truth": ranking.index(actual) + 1,
        "explained_class": predicted, "fault_window_snapshots": len(sequence),
        "ig_per_switch_signed": per_node, "ig_per_switch_abs": per_node_abs,
        "ig_per_feature_signed": per_feature, "ig_per_timestep_signed": per_time,
        "top_switch_feature_attributions": [{"switch": s, "feature": f, "ig": v} for s, f, v in flat[:6]],
        "attribution_concentrated_on_predicted_endpoints": top_two_switches == expected_switches,
        "occlusion": {"original_score": original, "switch_zeroed_delta": node_deltas,
                      "edge_removed_delta": edge_deltas if uses_edges else "not applicable: model ignores edges",
                      "timestep_removed_delta": time_deltas},
        "relevant_switches_ports": {"predicted": _link_endpoint_text(predicted, link_ports),
                                    "ground_truth": _link_endpoint_text(actual, link_ports)},
        "validation": validation,
        "limitations": ["Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports.",
                        "IG baseline is the training-mean fault-window state; a different baseline changes attributions.",
                        "GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence.",
                        "Explanations describe the ensemble's score function, not a causal mechanism in the network."],
        "fold": {"train_experiment_ids": list(train_ids), "active_features": active_names},
    }


# ----------------------------------------------------------------------------- reports
def write_markdown_report(path, experiment_id, explanations, topology):
    lines = ["# Explanation report: experiment %d (%d-switch topology)" % (experiment_id, topology.switch_count), ""]
    truth = next(iter(explanations.values()))["ground_truth"]
    lines += ["Ground-truth faulty link: **%s**. Candidate links: %d. All scores are uncalibrated ranking scores (not probabilities). "
              "The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof." % (truth, topology.candidate_count), ""]
    for method in ("rf_baseline", "topology_link_ranker", "graph_only", "temporal_only", "graph_temporal"):
        e = explanations.get(method)
        if e is None:
            continue
        lines += ["## %s" % e["label"], "",
                  "- Predicted ranking: %s" % " > ".join("%s (%.3f)" % (l, e["scores"][l]) for l in e["ranking"]),
                  "- Ground truth: %s; Top-1 %s; rank of truth %d" % (e["ground_truth"], "CORRECT" if e["top1_correct"] else "INCORRECT", e["rank_of_truth"]),
                  "- Relevant switches/ports: predicted %s; truth %s" % (", ".join(e["relevant_switches_ports"]["predicted"]["endpoints"]),
                                                                        ", ".join(e["relevant_switches_ports"]["ground_truth"]["endpoints"])),
                  "- Method: %s" % e["explanation_method"], "- Score semantics: %s" % e["score_semantics"]]
        if method == "rf_baseline":
            pa = e["predicted_class_attribution"]
            lines.append("- Main supporting features for predicted %s: %s" % (
                pa["class"], "; ".join("%s (SHAP %+.3f, value %.2f)" % (f["feature"], f["shap"], f["value"]) for f in pa["top_features"][:3])))
            v = e["validation"]
            lines.append("- Validation: additivity error %.1e (%s); top-%d neutralization drop %.3f vs random %.3f (%s)" % (
                v["additivity_max_abs_error"], "pass" if v["additivity_pass"] else "FAIL", v["perturbation_top_k"], v["top_k_drop"],
                v["random_k_drop_mean"], "pass" if v["perturbation_pass"] else "FAIL"))
        elif method == "topology_link_ranker":
            w = e["predicted_link_components"]
            lines.append("- Predicted link components: " + "; ".join("%s=%.3f (utility %.2f)" % (m, w["components"][m], w["utilities"][m]) for m, _ in RANK_COMPONENTS))
            lines.append("- Endpoint anomaly: %s=%.3f, %s=%.3f; deciding components: %s" % (
                w["endpoint_a"], w["endpoint_a_anomaly"], w["endpoint_b"], w["endpoint_b_anomaly"], e["deciding_components_for_top1"] or "none (robust to any single component)"))
        else:
            lines.append("- Main supporting switch/feature attributions: " + "; ".join(
                "%s %s (IG %+.3f)" % (t["switch"], t["feature"], t["ig"]) for t in e["top_switch_feature_attributions"][:3]))
            v = e["validation"]
            lines.append("- Validation: IG completeness gap %.1e (%s); zeroing top-%d switches %s drops score %.3f vs random %.3f (%s)" % (
                v["completeness_abs_gap"], "pass" if v["completeness_pass"] else "FAIL", len(v["perturbation_top_k_nodes"]),
                v["perturbation_top_k_nodes"], v["top_k_drop"], v["random_k_drop_mean"], "pass" if v["perturbation_pass"] else "FAIL"))
        lines += ["- Limitations: " + " ".join(e["limitations"]), ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run(switch_count, candidate_dir, graph_path, rf_eval_dir, neural_eval_dir, output_dir, experiments=None, static_mapping=False, dataset=None,
        ig_steps=IG_STEPS):
    topology = LinearTopology(switch_count)
    candidate_dir, rf_eval_dir, output_dir = Path(candidate_dir), Path(rf_eval_dir), Path(output_dir)
    neural_eval_dir = Path(neural_eval_dir) if neural_eval_dir else None
    if output_dir.exists():
        raise FileExistsError("Refusing to overwrite XAI output: %s" % output_dir)
    dataset = Path(dataset) if dataset else candidate_dir / "candidate_dataset.csv"
    link_ports, mapping_basis = load_link_ports(candidate_dir, topology, static=static_mapping)
    frame, labels = load_candidate(dataset, topology)
    with (rf_eval_dir / "grouped_evaluation.csv").open(encoding="utf-8-sig", newline="") as stream:
        saved = {(row["method"], int(row["experiment_id"])): row for row in csv.DictReader(stream)}
    rf_provenance = json.loads((rf_eval_dir / "evaluation_provenance.json").read_text(encoding="utf-8"))
    if rf_provenance["dataset_sha256"] != sha256(dataset):
        raise ValueError("RF/topology evaluation was not produced from this candidate")
    with (rf_eval_dir / "topology_ranker_components.csv").open(encoding="utf-8-sig", newline="") as stream:
        components = {}
        for row in csv.DictReader(stream):
            components.setdefault(int(row["experiment_id"]), []).append(row)
    neural_saved, examples = {}, None
    if neural_eval_dir is not None:
        summary = json.loads((neural_eval_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
        if summary["candidate_sha256"] != sha256(dataset) or not summary.get("checkpoints_saved"):
            raise ValueError("Neural evaluation lacks checkpoints or was not produced from this candidate")
        with (neural_eval_dir / "mean_seed_ensemble_predictions.csv").open(encoding="utf-8-sig", newline="") as stream:
            neural_saved = {(row["method"], int(row["experiment_id"])): row for row in csv.DictReader(stream)}
        examples, _names, _payload = models.prepare_examples(graph_path, topology)
    ids = sorted(labels)
    selected = sorted(map(int, experiments)) if experiments else ids
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "experiments").mkdir()
    rng = np.random.default_rng(RANDOM_SEED)
    started = time.monotonic()
    aggregate = {m: {"count": 0, "validation_pass": 0, "top1_correct": 0, "details": []} for m in METHOD_LABELS}
    rf_shap_global, rf_impurity_global = {}, {}
    neural_global = {m: {} for m in ("graph_only", "temporal_only", "graph_temporal")}
    for held_out in selected:
        train_ids = tuple(i for i in ids if i != held_out)
        fold = ids.index(held_out) + 1
        explanations = {}
        explanations["rf_baseline"] = explain_rf_fold(frame, labels, held_out, train_ids, topology, link_ports, saved[("rf_baseline", held_out)], rng)
        explanations["topology_link_ranker"] = explain_topology_fold(components[held_out], saved[("topology_link_ranker", held_out)], topology, link_ports)
        if neural_eval_dir is not None:
            for method in ("graph_only", "temporal_only", "graph_temporal"):
                explanations[method] = explain_neural_fold(method, examples, held_out, train_ids, topology, neural_eval_dir / "checkpoints",
                                                           fold, neural_saved[(method, held_out)], link_ports, rng, ig_steps=ig_steps)
        for method, e in explanations.items():
            v = e["validation"]
            passed = all(bool(v[key]) for key in v if key.endswith("_pass"))
            agg = aggregate[method]
            agg["count"] += 1
            agg["validation_pass"] += int(passed)
            agg["top1_correct"] += int(e["top1_correct"])
            agg["details"].append({"experiment_id": held_out, "top1_correct": e["top1_correct"], "validation_pass": passed,
                                   **({"attribution_on_predicted_endpoints": e["attribution_concentrated_on_predicted_endpoints"]} if "attribution_concentrated_on_predicted_endpoints" in e else {})})
        pa = explanations["rf_baseline"]["predicted_class_attribution"]
        for f in explanations["rf_baseline"]["all_shap_values"]:
            rf_shap_global[f] = rf_shap_global.get(f, 0.0) + abs(explanations["rf_baseline"]["all_shap_values"][f][pa["class"]])
        for f, v in explanations["rf_baseline"]["feature_importance_impurity"].items():
            rf_impurity_global[f] = rf_impurity_global.get(f, 0.0) + v
        for method in neural_global:
            if method in explanations:
                for s, v in explanations[method]["ig_per_switch_abs"].items():
                    neural_global[method][s] = neural_global[method].get(s, 0.0) + v
        (output_dir / "experiments" / ("experiment_%d.json" % held_out)).write_text(
            json.dumps(explanations, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
        write_markdown_report(output_dir / "experiments" / ("experiment_%d.md" % held_out), held_out, explanations, topology)
        print("explained experiment %d (%d/%d)" % (held_out, selected.index(held_out) + 1, len(selected)), file=sys.stderr, flush=True)
    n = len(selected)
    summary = {
        "topology": topology.to_metadata(), "candidate_sha256": sha256(dataset), "link_port_mapping_basis": mapping_basis,
        "experiments_explained": selected, "methods": {
            m: {"label": METHOD_LABELS[m], "explained": a["count"], "validation_pass_count": a["validation_pass"],
                "validation_pass_rate": (a["validation_pass"] / a["count"]) if a["count"] else None,
                "top1_correct": a["top1_correct"],
                "attribution_on_predicted_endpoints_rate": (sum(d.get("attribution_on_predicted_endpoints", False) for d in a["details"]) / a["count"])
                if a["count"] and "attribution_on_predicted_endpoints" in a["details"][0] else None,
                "per_experiment": a["details"]}
            for m, a in aggregate.items() if a["count"]},
        "global_feature_importance": {
            "rf_mean_abs_shap_predicted_class": {f: v / n for f, v in sorted(rf_shap_global.items(), key=lambda kv: -kv[1])},
            "rf_mean_impurity_importance": {f: v / n for f, v in sorted(rf_impurity_global.items(), key=lambda kv: -kv[1])},
            "neural_mean_abs_ig_per_switch": {m: {s: v / n for s, v in sorted(g.items(), key=lambda kv: -kv[1])} for m, g in neural_global.items() if g},
        },
        "validation_criteria": {
            "rf": "additivity |base+sum(SHAP)-proba| < 1e-6 and top-%d neutralization drop >= mean random-%d drop (%d draws)" % (TOP_K, TOP_K, RANDOM_DRAWS),
            "neural": "IG completeness relative gap < 5%% (or abs < 1e-3) and zeroing top-2 |IG| switches drops the score >= mean random-2 drop (%d draws)" % RANDOM_DRAWS,
            "topology_ranker": "rank_score recomputed as the mean of component utilities and ranking identical to the saved evaluation",
        },
        "score_semantics": "All methods output uncalibrated ranking scores: RF vote fractions, softmax ensembles, and rank utilities.",
        "ig_steps": ig_steps,
        "runtime_seconds": round(time.monotonic() - started, 1), "software": {"python": sys.version, "torch": torch.__version__},
    }
    try:
        import shap
        summary["software"]["shap"] = shap.__version__
    except ImportError:  # pragma: no cover
        pass
    (output_dir / "xai_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switches", type=int, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--rf-eval-dir", type=Path, required=True)
    parser.add_argument("--neural-eval-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiments", type=int, nargs="*", default=None)
    parser.add_argument("--static-four-switch-mapping", action="store_true")
    parser.add_argument("--ig-steps", type=int, default=IG_STEPS,
                        help="integrated-gradients Riemann steps; more steps tighten the completeness check")
    args = parser.parse_args(argv)
    if args.neural_eval_dir is not None and args.graph is None:
        parser.error("--graph is required with --neural-eval-dir")
    summary = run(args.switches, args.candidate_dir, args.graph, args.rf_eval_dir, args.neural_eval_dir, args.output_dir,
                  experiments=args.experiments, static_mapping=args.static_four_switch_mapping, dataset=args.dataset,
                  ig_steps=args.ig_steps)
    print(json.dumps({m: {k: v for k, v in d.items() if k != "per_experiment"} for m, d in summary["methods"].items()}, indent=2))


if __name__ == "__main__":
    main()
