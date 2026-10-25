# Explanation report: experiment 207 (12-switch topology)

Ground-truth faulty link: **s7-s8**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s7-s8 (0.423) > s6-s7 (0.187) > s8-s9 (0.143) > s4-s5 (0.080) > s10-s11 (0.055) > s9-s10 (0.043) > s5-s6 (0.036) > s2-s3 (0.013) > s1-s2 (0.010) > s3-s4 (0.009) > s11-s12 (0.002)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s7-s8: s7_mean_anomaly (SHAP +0.035, value 1.07); s7_max_anomaly (SHAP +0.030, value 1.18); s6_max_anomaly (SHAP +0.022, value 0.39)
- Validation: additivity error 4.0e-16 (pass); top-3 neutralization drop 0.050 vs random 0.021 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.614) > s9-s10 (0.591) > s3-s4 (0.591) > s10-s11 (0.568) > s2-s3 (0.568) > s6-s7 (0.568) > s4-s5 (0.545) > s1-s2 (0.523) > s8-s9 (0.477) > s5-s6 (0.477) > s7-s8 (0.477)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 11
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s7 port 2, s8 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.044 (utility 1.00); endpoint_imbalance=0.006 (utility 0.36); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=1.044, s12:1=1.050; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s7-s8 (0.996) > s8-s9 (0.003) > s6-s7 (0.001) > s1-s2 (0.000) > s9-s10 (0.000) > s5-s6 (0.000) > s11-s12 (0.000) > s4-s5 (0.000) > s10-s11 (0.000) > s2-s3 (0.000) > s3-s4 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.195); s1 tx_packet_rate (IG +0.169); s8 rx_throughput_mbps (IG +0.163)
- Validation: IG completeness gap 1.5e-04 (pass); zeroing top-2 switches ['s8', 's9'] drops score 0.651 vs random 0.266 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s7-s8 (0.855) > s6-s7 (0.064) > s8-s9 (0.053) > s9-s10 (0.009) > s4-s5 (0.007) > s3-s4 (0.005) > s10-s11 (0.003) > s11-s12 (0.002) > s5-s6 (0.001) > s2-s3 (0.001) > s1-s2 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_packet_rate (IG +0.088); s6 tx_throughput_mbps (IG +0.083); s7 rx_throughput_mbps (IG +0.079)
- Validation: IG completeness gap 6.2e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.254 vs random 0.050 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s7-s8 (0.504) > s6-s7 (0.169) > s8-s9 (0.100) > s11-s12 (0.083) > s10-s11 (0.071) > s9-s10 (0.048) > s4-s5 (0.008) > s3-s4 (0.005) > s2-s3 (0.005) > s5-s6 (0.004) > s1-s2 (0.002)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 rx_throughput_mbps (IG +0.201); s9 rx_packet_rate (IG +0.154); s8 rx_throughput_mbps (IG +0.154)
- Validation: IG completeness gap 9.3e-04 (pass); zeroing top-2 switches ['s9', 's8'] drops score 0.343 vs random 0.159 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
