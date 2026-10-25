# Explanation report: experiment 121 (8-switch topology)

Ground-truth faulty link: **s7-s8**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.464) > s7-s8 (0.194) > s4-s5 (0.192) > s5-s6 (0.124) > s3-s4 (0.016) > s2-s3 (0.010) > s1-s2 (0.000)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s7 port 2, s8 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s6_max_anomaly (SHAP +0.051, value 1.36); s5_mean_anomaly (SHAP +0.042, value 0.71); s4_mean_anomaly (SHAP +0.040, value 0.57)
- Validation: additivity error 3.2e-16 (pass); top-3 neutralization drop 0.169 vs random 0.042 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s5-s6 (0.714) > s7-s8 (0.643) > s6-s7 (0.607) > s1-s2 (0.571) > s4-s5 (0.536) > s2-s3 (0.536) > s3-s4 (0.393)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s7 port 2, s8 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.458 (utility 0.71); endpoint_imbalance=0.001 (utility 1.00); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s5:2=0.458, s6:1=0.459; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s7-s8 (1.000) > s6-s7 (0.000) > s1-s2 (0.000) > s3-s4 (0.000) > s4-s5 (0.000) > s2-s3 (0.000) > s5-s6 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_throughput_mbps (IG +0.130); s6 tx_packet_rate (IG +0.127); s5 tx_throughput_mbps (IG +0.122)
- Validation: IG completeness gap 3.7e-03 (pass); zeroing top-2 switches ['s6', 's5'] drops score 0.633 vs random 0.142 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s7-s8 (0.983) > s6-s7 (0.010) > s3-s4 (0.002) > s4-s5 (0.002) > s1-s2 (0.001) > s5-s6 (0.001) > s2-s3 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_throughput_mbps (IG +0.138); s6 tx_packet_rate (IG +0.135); s7 rx_packet_rate (IG +0.109)
- Validation: IG completeness gap 7.1e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.665 vs random 0.051 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s7-s8 (0.816) > s6-s7 (0.136) > s5-s6 (0.027) > s3-s4 (0.008) > s1-s2 (0.007) > s4-s5 (0.003) > s2-s3 (0.002)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.120); s6 rx_throughput_mbps (IG +0.100); s7 rx_packet_rate (IG +0.094)
- Validation: IG completeness gap 2.1e-03 (pass); zeroing top-2 switches ['s6', 's5'] drops score 0.773 vs random 0.268 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
