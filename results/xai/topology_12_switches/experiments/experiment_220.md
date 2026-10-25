# Explanation report: experiment 220 (12-switch topology)

Ground-truth faulty link: **s9-s10**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s11-s12 (0.395) > s10-s11 (0.210) > s8-s9 (0.163) > s7-s8 (0.085) > s6-s7 (0.059) > s9-s10 (0.043) > s3-s4 (0.027) > s4-s5 (0.017) > s2-s3 (0.001) > s1-s2 (0.000) > s5-s6 (0.000)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s9 port 2, s10 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s11-s12: s7_mean_anomaly (SHAP +0.048, value 0.17); s7_max_anomaly (SHAP +0.040, value 0.20); s8_mean_anomaly (SHAP +0.031, value 0.16)
- Validation: additivity error 4.0e-16 (pass); top-3 neutralization drop 0.205 vs random 0.039 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.636) > s2-s3 (0.614) > s4-s5 (0.591) > s7-s8 (0.591) > s9-s10 (0.568) > s10-s11 (0.545) > s1-s2 (0.545) > s11-s12 (0.523) > s6-s7 (0.523) > s8-s9 (0.432) > s5-s6 (0.432)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s9 port 2, s10 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.208 (utility 0.55); endpoint_imbalance=0.000 (utility 0.91); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s3:2=0.208, s4:1=0.208; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s9-s10 (0.929) > s8-s9 (0.045) > s10-s11 (0.026) > s4-s5 (0.000) > s7-s8 (0.000) > s2-s3 (0.000) > s11-s12 (0.000) > s5-s6 (0.000) > s1-s2 (0.000) > s6-s7 (0.000) > s3-s4 (0.000)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.118); s8 rx_packet_rate (IG +0.116); s9 rx_throughput_mbps (IG +0.088)
- Validation: IG completeness gap 1.4e-03 (pass); zeroing top-2 switches ['s8', 's7'] drops score 0.595 vs random 0.223 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s8-s9 (0.636) > s10-s11 (0.196) > s11-s12 (0.061) > s7-s8 (0.046) > s9-s10 (0.033) > s1-s2 (0.011) > s5-s6 (0.006) > s4-s5 (0.006) > s6-s7 (0.004) > s3-s4 (0.001) > s2-s3 (0.001)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 tx_throughput_mbps (IG -0.181); s8 tx_packet_rate (IG -0.175); s9 rx_packet_rate (IG -0.145)
- Validation: IG completeness gap 1.2e-03 (pass); zeroing top-2 switches ['s10', 's4'] drops score 0.434 vs random 0.077 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s8-s9 (0.463) > s9-s10 (0.215) > s10-s11 (0.120) > s7-s8 (0.079) > s11-s12 (0.068) > s6-s7 (0.026) > s4-s5 (0.008) > s1-s2 (0.007) > s2-s3 (0.006) > s5-s6 (0.005) > s3-s4 (0.003)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 tx_throughput_mbps (IG -0.121); s8 tx_packet_rate (IG -0.112); s9 tx_throughput_mbps (IG +0.087)
- Validation: IG completeness gap 8.2e-03 (pass); zeroing top-2 switches ['s9', 's3'] drops score 0.302 vs random 0.088 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
