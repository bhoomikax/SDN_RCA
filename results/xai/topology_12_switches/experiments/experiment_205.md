# Explanation report: experiment 205 (12-switch topology)

Ground-truth faulty link: **s5-s6**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s5-s6 (0.455) > s3-s4 (0.233) > s2-s3 (0.146) > s4-s5 (0.099) > s1-s2 (0.036) > s7-s8 (0.017) > s6-s7 (0.008) > s9-s10 (0.006) > s10-s11 (0.000) > s11-s12 (0.000) > s8-s9 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s5-s6: s1_mean_anomaly (SHAP +0.034, value 1.44); s1_first_anomaly_seconds (SHAP +0.025, value 4.18); s1_max_anomaly (SHAP +0.022, value 2.17)
- Validation: additivity error 3.9e-16 (pass); top-3 neutralization drop 0.128 vs random 0.022 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s5-s6 (0.773) > s9-s10 (0.705) > s10-s11 (0.682) > s11-s12 (0.659) > s8-s9 (0.591) > s7-s8 (0.545) > s6-s7 (0.500) > s3-s4 (0.386) > s2-s3 (0.386) > s1-s2 (0.386) > s4-s5 (0.386)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.088 (utility 1.00); endpoint_imbalance=0.001 (utility 1.00); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s5:2=1.088, s6:1=1.089; deciding components: none (robust to any single component)
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s5-s6 (0.987) > s4-s5 (0.006) > s6-s7 (0.005) > s2-s3 (0.001) > s7-s8 (0.000) > s9-s10 (0.000) > s1-s2 (0.000) > s10-s11 (0.000) > s8-s9 (0.000) > s3-s4 (0.000) > s11-s12 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_throughput_mbps (IG +0.075); s12 rx_packet_rate (IG +0.074); s5 tx_throughput_mbps (IG +0.056)
- Validation: IG completeness gap 3.8e-04 (pass); zeroing top-2 switches ['s2', 's12'] drops score 0.017 vs random 0.088 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.854) > s1-s2 (0.117) > s4-s5 (0.018) > s6-s7 (0.003) > s2-s3 (0.003) > s9-s10 (0.002) > s11-s12 (0.001) > s7-s8 (0.001) > s8-s9 (0.001) > s3-s4 (0.000) > s10-s11 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 rx_packet_rate (IG +0.073); s1 rx_throughput_mbps (IG +0.065); s2 rx_throughput_mbps (IG +0.051)
- Validation: IG completeness gap 2.2e-03 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.581 vs random 0.174 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s5-s6 (0.644) > s2-s3 (0.152) > s1-s2 (0.119) > s4-s5 (0.061) > s9-s10 (0.010) > s3-s4 (0.006) > s11-s12 (0.003) > s6-s7 (0.002) > s8-s9 (0.001) > s10-s11 (0.001) > s7-s8 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 rx_throughput_mbps (IG +0.048); s6 rx_packet_rate (IG +0.046); s7 rx_throughput_mbps (IG +0.046)
- Validation: IG completeness gap 1.1e-03 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.130 vs random 0.076 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
