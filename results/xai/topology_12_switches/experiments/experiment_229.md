# Explanation report: experiment 229 (12-switch topology)

Ground-truth faulty link: **s7-s8**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s7-s8 (0.399) > s6-s7 (0.235) > s8-s9 (0.110) > s9-s10 (0.060) > s4-s5 (0.059) > s5-s6 (0.055) > s3-s4 (0.048) > s10-s11 (0.021) > s1-s2 (0.009) > s2-s3 (0.005) > s11-s12 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s7-s8: s7_mean_anomaly (SHAP +0.029, value 1.07); s6_mean_anomaly (SHAP +0.023, value 0.23); s7_max_anomaly (SHAP +0.022, value 1.11)
- Validation: additivity error 5.0e-16 (pass); top-3 neutralization drop 0.043 vs random 0.020 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s10-s11 (0.591) > s9-s10 (0.591) > s3-s4 (0.591) > s4-s5 (0.591) > s11-s12 (0.568) > s2-s3 (0.568) > s6-s7 (0.545) > s7-s8 (0.500) > s1-s2 (0.500) > s8-s9 (0.477) > s5-s6 (0.477)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 8
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s7 port 2, s8 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.079 (utility 0.91); endpoint_imbalance=0.006 (utility 0.36); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s10:2=1.079, s11:1=1.085; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s7-s8 (0.998) > s6-s7 (0.001) > s8-s9 (0.001) > s5-s6 (0.000) > s4-s5 (0.000) > s1-s2 (0.000) > s10-s11 (0.000) > s9-s10 (0.000) > s2-s3 (0.000) > s11-s12 (0.000) > s3-s4 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_throughput_mbps (IG +0.100); s5 tx_packet_rate (IG +0.091); s1 tx_throughput_mbps (IG +0.090)
- Validation: IG completeness gap 1.0e-03 (pass); zeroing top-2 switches ['s8', 's9'] drops score 0.345 vs random 0.224 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s7-s8 (0.966) > s8-s9 (0.012) > s6-s7 (0.011) > s4-s5 (0.003) > s10-s11 (0.002) > s9-s10 (0.002) > s1-s2 (0.001) > s5-s6 (0.001) > s2-s3 (0.001) > s11-s12 (0.001) > s3-s4 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_packet_rate (IG +0.153); s6 tx_throughput_mbps (IG +0.152); s7 rx_packet_rate (IG +0.133)
- Validation: IG completeness gap 2.4e-03 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.849 vs random 0.139 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s7-s8 (0.537) > s6-s7 (0.391) > s8-s9 (0.038) > s4-s5 (0.020) > s3-s4 (0.004) > s9-s10 (0.003) > s10-s11 (0.003) > s11-s12 (0.002) > s5-s6 (0.001) > s1-s2 (0.001) > s2-s3 (0.001)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG +0.106); s1 tx_throughput_mbps (IG -0.095); s4 tx_packet_rate (IG +0.084)
- Validation: IG completeness gap 2.5e-04 (pass); zeroing top-2 switches ['s10', 's9'] drops score 0.080 vs random 0.062 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
