# Explanation report: experiment 112 (8-switch topology)

Ground-truth faulty link: **s5-s6**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s5-s6 (0.453) > s4-s5 (0.193) > s3-s4 (0.164) > s6-s7 (0.100) > s7-s8 (0.054) > s1-s2 (0.027) > s2-s3 (0.010)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s5-s6: s5_mean_anomaly (SHAP +0.044, value 1.49); s4_persistence (SHAP +0.039, value 0.33); s5_max_anomaly (SHAP +0.036, value 2.18)
- Validation: additivity error 2.4e-16 (pass); top-3 neutralization drop 0.013 vs random 0.017 (FAIL)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s6-s7 (0.714) > s7-s8 (0.714) > s5-s6 (0.679) > s3-s4 (0.536) > s4-s5 (0.500) > s2-s3 (0.464) > s1-s2 (0.393)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s5 port 2, s6 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.106 (utility 0.86); endpoint_imbalance=0.009 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s6:2=1.106, s7:1=1.116; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s5-s6 (0.994) > s4-s5 (0.003) > s6-s7 (0.001) > s3-s4 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s7-s8 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.081); s8 rx_packet_rate (IG +0.080); s4 rx_packet_rate (IG +0.072)
- Validation: IG completeness gap 6.4e-04 (pass); zeroing top-2 switches ['s8', 's3'] drops score 0.041 vs random 0.142 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.994) > s1-s2 (0.002) > s3-s4 (0.001) > s4-s5 (0.001) > s6-s7 (0.001) > s7-s8 (0.001) > s2-s3 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.056); s7 rx_packet_rate (IG +0.051); s2 tx_throughput_mbps (IG +0.044)
- Validation: IG completeness gap 2.8e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.358 vs random 0.046 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s5-s6 (0.957) > s1-s2 (0.023) > s3-s4 (0.010) > s7-s8 (0.004) > s6-s7 (0.003) > s2-s3 (0.002) > s4-s5 (0.001)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.110); s2 tx_throughput_mbps (IG +0.100); s1 rx_throughput_mbps (IG +0.100)
- Validation: IG completeness gap 8.2e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.417 vs random 0.224 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
