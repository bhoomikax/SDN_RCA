"""Inference on a new (dashboard-collected) run using the repository's own code.

Pipeline for one fetched run directory:

1. ``build_topology_candidate`` admits the run under the research rules and
   writes a one-experiment candidate (schema, phase coverage, mapping, iperf
   evidence, offered rate). Invalid runs are rejected with the recorded reason.
2. ``build_graph_multi`` builds the per-timestamp graph snapshots.
3. Random Forest and the topology ranker are refit on the saved admitted
   candidate of the same topology (all its experiments; the new run is not in
   it), then rank the new run's oracle fault window.
4. GCN / LSTM / GCN+LSTM use the saved fold checkpoints (three seeds of one
   fold) with their stored feature policy; the new run was never seen by them.

The fault window is selected from the run's own annotated fault phase (oracle),
exactly as in the research evaluation. The retrospective label is read from the
phase events and reported separately; it never enters any feature.
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import build_graph_multi
import build_topology_candidate
import evaluate_topology_loeo as rf_eval
import graph_temporal_topology as neural
from linear_topology import LinearTopology

from . import config
from .saved_results import METHOD_LABELS, NEURAL_METHODS

SCORE_SEMANTICS = {
    "rf_baseline": "RandomForest predict_proba vote fractions; uncalibrated ranking scores, not probabilities",
    "topology_link_ranker": "equal-weight rank utilities in (0, 1]; not probabilities",
    "graph_only": "mean softmax over three seed checkpoints; uncalibrated ranking scores, not probabilities",
    "temporal_only": "mean softmax over three seed checkpoints; uncalibrated ranking scores, not probabilities",
    "graph_temporal": "mean softmax over three seed checkpoints; uncalibrated ranking scores, not probabilities",
}


def _derived_dir(run_dir):
    return Path(run_dir).parent / ("%s_derived" % Path(run_dir).name)


def prepare_run(switches, run_dir):
    """Admit the run and build its candidate and graph (idempotent: existing
    derived outputs are reused, never overwritten)."""
    switches = int(switches)
    run_dir = Path(run_dir)
    derived = _derived_dir(run_dir)
    candidate_dir = derived / "candidate"
    graph_path = derived / "graph" / "graph_dataset.json"
    report = {"run_dir": str(run_dir), "derived_dir": str(derived)}
    if not candidate_dir.is_dir():
        try:
            build_topology_candidate.build_topology_candidate(switches, run_dir.parent, candidate_dir, run_dirs=[run_dir])
        except ValueError as exc:
            # Nothing admitted: surface the recorded exclusion reason.
            raise ValueError("Run not admitted by the research validation rules: %s" % exc) from exc
    exclusion = candidate_dir / "exclusion_report.csv"
    excluded = pd.read_csv(exclusion) if exclusion.is_file() else pd.DataFrame()
    if len(excluded):
        raise ValueError("Run excluded: %s" % excluded.iloc[0]["reason"])
    if not graph_path.is_file():
        build_graph_multi.build(candidate_dir / "candidate_dataset.csv", graph_path, LinearTopology(switches))
    provenance = json.loads((candidate_dir / "provenance.json").read_text(encoding="utf-8"))
    report.update({
        "candidate_dir": str(candidate_dir), "graph_path": str(graph_path),
        "candidate_sha256": provenance["dataset_sha256"],
        "admitted_experiments": provenance["admitted_logical_experiments"],
        "experiment_labels_retrospective": provenance["experiment_labels"],
    })
    return report


def _training_frame(switches):
    saved = config.SAVED_RESULTS[switches]
    topology = LinearTopology(switches)
    candidate_dir = Path(saved["candidate_dir"])
    dataset = candidate_dir / "candidate_dataset.csv"
    link_ports, basis = rf_eval.load_link_ports(candidate_dir, topology, static=saved["static_mapping"])
    frame, labels = rf_eval.load_candidate(dataset, topology)
    return topology, frame, labels, link_ports, basis, rf_eval.sha256(dataset), dataset


def rf_and_ranker(switches, prepared):
    """Refit RF and the ranker on the saved admitted candidate; rank the new run."""
    switches = int(switches)
    topology, train_frame, train_labels, link_ports, basis, train_hash, train_path = _training_frame(switches)
    new_frame, new_labels = rf_eval.load_candidate(Path(prepared["candidate_dir"]) / "candidate_dataset.csv", topology)
    new_ids = sorted(new_labels)
    if set(new_ids) & set(train_labels):
        raise ValueError("New run ID collides with a training experiment: %s" % sorted(set(new_ids) & set(train_labels)))
    new_mapping = pd.read_csv(Path(prepared["candidate_dir"]) / "link_port_mapping.csv")
    new_ports = {}
    for row in new_mapping.itertuples():
        new_ports.setdefault(row.link, []).append((row.switch, str(row.openflow_port)))
    for link, endpoints in link_ports.items():
        if sorted(endpoints) != sorted(new_ports.get(link, [])):
            raise ValueError("Runtime port mapping of the new run differs from the training candidate for %s" % link)
    combined = pd.concat([train_frame, new_frame], ignore_index=True)
    labels = dict(train_labels)
    results = {}
    for held_out in new_ids:
        started = time.monotonic()
        # fold_inputs requires a label dict only for the training IDs; held-out label is unused.
        inputs = rf_eval.fold_inputs(combined, {**labels, held_out: None}, held_out, sorted(train_labels), topology, link_ports)
        model = rf_eval.fit_rf(inputs["x_train"], inputs["y_train"])
        ranking, scores = rf_eval.stable_rf_ranking(model, inputs["x_test"])
        for link in topology.candidate_links:
            if link not in scores:
                ranking.append(link)
                scores[link] = 0.0
        rf_attr = _rf_shap(model, inputs, topology, ranking[0])
        table = rf_eval.rank_topology(inputs["held_out_scores"], held_out, inputs["threshold"], topology, link_ports)
        topo_ranking = table.index.astype(str).tolist()
        topo_scores = {str(link): float(table.loc[link, "rank_score"]) for link in table.index}
        components = {str(link): {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                                  for k, v in table.loc[link].items() if k != "candidate_link"} for link in table.index}
        results[held_out] = {
            "rf_baseline": {
                "label": METHOD_LABELS["rf_baseline"], "ranking": ranking, "scores": scores,
                "score_semantics": SCORE_SEMANTICS["rf_baseline"],
                "training": {"experiment_ids": inputs["train_ids"], "count": len(inputs["train_ids"]),
                             "candidate_sha256": train_hash, "candidate_path": str(train_path.relative_to(config.ROOT)),
                             "mapping_basis": basis, "active_metrics": list(inputs["active"])},
                "features": {name: float(v) for name, v in zip(inputs["feature_names"], inputs["x_test"])},
                "attribution": rf_attr,
                "fit_seconds": round(time.monotonic() - started, 2),
            },
            "topology_link_ranker": {
                "label": METHOD_LABELS["topology_link_ranker"], "ranking": topo_ranking, "scores": topo_scores,
                "score_semantics": SCORE_SEMANTICS["topology_link_ranker"],
                "training": {"experiment_ids": inputs["train_ids"], "count": len(inputs["train_ids"]),
                             "normal_threshold": inputs["threshold"], "candidate_sha256": train_hash},
                "components": components,
            },
        }
    return results


def _rf_shap(model, inputs, topology, predicted):
    """Exact TreeSHAP for the live RF prediction (same method as explain_rca)."""
    try:
        import shap
    except ImportError:
        return {"available": False, "reason": "shap is not installed"}
    names = inputs["feature_names"]
    x = inputs["x_test"].reshape(1, -1)
    classes = [str(c) for c in model.classes_]
    if predicted not in classes:
        return {"available": False, "reason": "predicted class absent from training classes"}
    explainer = shap.TreeExplainer(model)
    values = np.asarray(explainer.shap_values(x))
    if values.ndim == 3 and values.shape[0] == 1:
        values = values[0]
    elif values.ndim == 3:
        values = np.transpose(values[:, 0, :])
    base = np.asarray(explainer.expected_value, dtype=float).reshape(-1)
    probabilities = model.predict_proba(x)[0]
    additivity = float(np.max(np.abs(base + values.sum(axis=0) - probabilities)))
    column = classes.index(predicted)
    contribution = values[:, column]
    order = np.argsort(-np.abs(contribution))
    return {
        "available": True,
        "method": "shap.TreeExplainer exact Shapley values on the refit RandomForest; attribution to the predicted class score",
        "explained_class": predicted,
        "base_value": float(base[column]),
        "additivity_max_abs_error": additivity,
        "additivity_pass": additivity < 1e-6,
        "top_features": [{"feature": names[i], "switch": names[i].split("_")[0], "shap": float(contribution[i]),
                          "value": float(x[0, i])} for i in order[:8]],
        "support_by_switch": {sw: float(sum(contribution[i] for i, n in enumerate(names) if n.startswith(sw + "_")))
                              for sw in topology.switches},
        "limitation": "Model attribution on oracle-window anomaly statistics, not causal evidence.",
    }


def _checkpoint_fold(switches):
    """Pick the saved fold whose three seed checkpoints are all present (first fold)."""
    saved = config.SAVED_RESULTS[switches]
    checkpoint_dir = Path(saved["neural_eval_dir"]) / "checkpoints"
    if not checkpoint_dir.is_dir():
        raise FileNotFoundError("No saved checkpoints for %d switches" % switches)
    summary = json.loads((Path(saved["neural_eval_dir"]) / "evaluation_summary.json").read_text(encoding="utf-8"))
    fold_count = len(summary.get("experiment_ids") or [])
    for fold in range(1, fold_count + 1):
        complete = all(
            len(list(checkpoint_dir.glob("%s_fold%02d_heldout*_seed%d.pt" % (method, fold, seed)))) == 1
            for method in NEURAL_METHODS for seed in neural.SEEDS
        )
        if complete:
            return checkpoint_dir, fold, summary
    raise FileNotFoundError("No complete checkpoint fold for %d switches" % switches)


def neural_ensembles(switches, prepared, methods=NEURAL_METHODS):
    """Score the new run with the saved three-seed checkpoint ensemble of one fold."""
    switches = int(switches)
    topology = LinearTopology(switches)
    checkpoint_dir, fold, summary = _checkpoint_fold(switches)
    examples, feature_names, payload = neural.prepare_examples(prepared["graph_path"], topology)
    if payload.get("source_sha256") != prepared["candidate_sha256"]:
        raise ValueError("Graph snapshots do not match the new candidate hash")
    links = list(topology.candidate_links)
    results = {}
    for experiment_id, example in examples.items():
        results[experiment_id] = {}
        for method in methods:
            seed_models, policies, names = [], [], []
            for seed in neural.SEEDS:
                matches = sorted(checkpoint_dir.glob("%s_fold%02d_heldout*_seed%d.pt" % (method, fold, seed)))
                if len(matches) != 1:
                    raise FileNotFoundError("Checkpoint missing for %s fold %d seed %d" % (method, fold, seed))
                model, ckpt = neural.load_checkpoint(matches[0], topology)
                recorded = summary.get("checkpoint_sha256", {}).get(matches[0].name)
                if recorded and neural.sha256(matches[0]) != recorded:
                    raise ValueError("Checkpoint %s does not match its recorded hash" % matches[0].name)
                seed_models.append(model)
                policies.append(ckpt)
                names.append(matches[0].name)
            policy = policies[0]
            if any(p["input_features"] != policy["input_features"] or p["train_experiment_ids"] != policy["train_experiment_ids"]
                   for p in policies):
                raise ValueError("Seed checkpoints of fold %d disagree on their feature policy" % fold)
            if experiment_id in policy["train_experiment_ids"]:
                raise ValueError("New run ID %d appears in the checkpoint training set" % experiment_id)
            sequence = neural.normalize_sequence(example["sequence"], policy["input_features"],
                                                 np.asarray(policy["feature_means"], dtype=np.float32),
                                                 np.asarray(policy["feature_stds"], dtype=np.float32), topology)
            started = time.monotonic()
            with torch.no_grad():
                scores = torch.stack([torch.softmax(m(sequence), dim=0) for m in seed_models]).mean(dim=0).numpy()
            ranked = sorted(range(len(links)), key=lambda idx: (-float(scores[idx]), links[idx]))
            results[experiment_id][method] = {
                "label": METHOD_LABELS[method],
                "ranking": [links[i] for i in ranked],
                "scores": {links[i]: float(scores[i]) for i in range(len(links))},
                "score_semantics": SCORE_SEMANTICS[method],
                "training": {
                    "kind": "saved LOEO fold checkpoints (three seeds, mean softmax)",
                    "fold": fold, "checkpoints": names,
                    "experiment_ids": list(policy["train_experiment_ids"]),
                    "count": len(policy["train_experiment_ids"]),
                    "held_out_during_training": int(policy["test_experiment_ids"][0]) if policy.get("test_experiment_ids") else None,
                    "active_features": [feature_names[i] for i in policy["input_features"]],
                    "candidate_sha256": summary.get("candidate_sha256"),
                },
                "fault_window_snapshots": len(sequence),
                "inference_seconds": round(time.monotonic() - started, 3),
            }
    return results


def run_inference(switches, run_dir, methods):
    """Full inference for one fetched run directory."""
    switches = int(switches)
    prepared = prepare_run(switches, run_dir)
    wanted = list(methods)
    out = {"switch_count": switches, "prepared": prepared, "experiments": {}, "task":
           "conditional fault-window localization: the run's own annotated fault phase selects the first 10 s; "
           "this is not online detection and not causal root-cause analysis"}
    classical = [m for m in wanted if m in ("rf_baseline", "topology_link_ranker")]
    neural_wanted = [m for m in wanted if m in NEURAL_METHODS]
    per_experiment = {}
    if classical:
        for exp, methods_out in rf_and_ranker(switches, prepared).items():
            per_experiment.setdefault(exp, {}).update({m: methods_out[m] for m in classical})
    if neural_wanted:
        for exp, methods_out in neural_ensembles(switches, prepared, neural_wanted).items():
            per_experiment.setdefault(exp, {}).update(methods_out)
    for exp, methods_out in per_experiment.items():
        truth = prepared["experiment_labels_retrospective"].get(str(exp))
        for method, block in methods_out.items():
            block["ground_truth_retrospective"] = truth
            block["rank_of_truth_retrospective"] = (block["ranking"].index(truth) + 1) if truth in block["ranking"] else None
        out["experiments"][str(exp)] = methods_out
    return out
