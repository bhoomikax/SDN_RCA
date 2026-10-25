# Explanation report: experiment 114 (8-switch topology)

Ground-truth faulty link: **s7-s8**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.621) > s7-s8 (0.247) > s5-s6 (0.076) > s4-s5 (0.053) > s3-s4 (0.003) > s1-s2 (0.000) > s2-s3 (0.000)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s7 port 2, s8 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s6_max_anomaly (SHAP +0.075, value 0.37); s5_mean_anomaly (SHAP +0.066, value 0.28); s5_persistence (SHAP +0.059, value 0.00)
- Validation: additivity error 2.8e-16 (pass); top-3 neutralization drop 0.323 vs random 0.050 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.714) > s3-s4 (0.679) > s2-s3 (0.643) > s7-s8 (0.571) > s4-s5 (0.536) > s5-s6 (0.429) > s6-s7 (0.429)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s7 port 2, s8 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.264 (utility 0.86); endpoint_imbalance=0.001 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s1:2=0.265, s2:1=0.264; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s7-s8 (0.939) > s6-s7 (0.061) > s4-s5 (0.001) > s3-s4 (0.000) > s5-s6 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG -0.386); s8 rx_packet_rate (IG -0.369); s7 rx_throughput_mbps (IG +0.326)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s6', 's5'] drops score 0.932 vs random 0.291 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s7-s8 (0.971) > s6-s7 (0.019) > s5-s6 (0.003) > s3-s4 (0.003) > s4-s5 (0.002) > s2-s3 (0.001) > s1-s2 (0.001)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_packet_rate (IG +0.146); s6 tx_throughput_mbps (IG +0.146); s7 rx_throughput_mbps (IG +0.106)
- Validation: IG completeness gap 4.7e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.478 vs random 0.154 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s7-s8 (0.859) > s6-s7 (0.127) > s5-s6 (0.007) > s4-s5 (0.003) > s1-s2 (0.001) > s3-s4 (0.001) > s2-s3 (0.001)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG -0.311); s7 rx_throughput_mbps (IG +0.258); s8 rx_packet_rate (IG -0.246)
- Validation: IG completeness gap 1.1e-03 (pass); zeroing top-2 switches ['s6', 's5'] drops score 0.540 vs random 0.243 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
