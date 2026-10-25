# Explanation report: experiment 113 (8-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.746) > s7-s8 (0.186) > s4-s5 (0.054) > s5-s6 (0.010) > s3-s4 (0.004) > s1-s2 (0.000) > s2-s3 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s5_mean_anomaly (SHAP +0.061, value 0.30); s6_mean_anomaly (SHAP +0.053, value 1.13); s6_max_anomaly (SHAP +0.053, value 1.25)
- Validation: additivity error 2.4e-16 (pass); top-3 neutralization drop 0.266 vs random 0.045 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.679) > s4-s5 (0.607) > s6-s7 (0.571) > s7-s8 (0.571) > s2-s3 (0.571) > s3-s4 (0.571) > s5-s6 (0.429)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.272 (utility 0.71); endpoint_imbalance=0.001 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s1:2=0.272, s2:1=0.273; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.998) > s5-s6 (0.002) > s7-s8 (0.000) > s4-s5 (0.000) > s2-s3 (0.000) > s1-s2 (0.000) > s3-s4 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.109); s5 rx_packet_rate (IG +0.106); s8 rx_throughput_mbps (IG +0.105)
- Validation: IG completeness gap 1.1e-03 (pass); zeroing top-2 switches ['s5', 's8'] drops score 0.314 vs random 0.273 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.992) > s5-s6 (0.002) > s7-s8 (0.002) > s4-s5 (0.001) > s2-s3 (0.001) > s3-s4 (0.001) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_packet_rate (IG +0.187); s5 tx_throughput_mbps (IG +0.180); s3 tx_throughput_mbps (IG +0.156)
- Validation: IG completeness gap 1.0e-04 (pass); zeroing top-2 switches ['s5', 's4'] drops score 0.768 vs random 0.290 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.956) > s7-s8 (0.035) > s5-s6 (0.007) > s4-s5 (0.002) > s3-s4 (0.001) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.176); s1 tx_packet_rate (IG +0.139); s2 tx_throughput_mbps (IG +0.129)
- Validation: IG completeness gap 1.4e-03 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.275 vs random 0.417 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
