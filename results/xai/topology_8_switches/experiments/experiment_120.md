# Explanation report: experiment 120 (8-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.781) > s7-s8 (0.134) > s4-s5 (0.039) > s5-s6 (0.036) > s3-s4 (0.010) > s1-s2 (0.000) > s2-s3 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s6_mean_anomaly (SHAP +0.059, value 1.13); s6_max_anomaly (SHAP +0.056, value 1.27); s5_mean_anomaly (SHAP +0.051, value 0.31)
- Validation: additivity error 1.7e-16 (pass); top-3 neutralization drop 0.263 vs random 0.083 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.643) > s2-s3 (0.643) > s3-s4 (0.643) > s6-s7 (0.571) > s7-s8 (0.571) > s4-s5 (0.500) > s5-s6 (0.429)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.278 (utility 0.71); endpoint_imbalance=0.001 (utility 0.71); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s1:2=0.279, s2:1=0.278; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.997) > s5-s6 (0.002) > s7-s8 (0.001) > s4-s5 (0.000) > s2-s3 (0.000) > s1-s2 (0.000) > s3-s4 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 rx_packet_rate (IG +0.105); s6 rx_throughput_mbps (IG +0.103); s1 tx_throughput_mbps (IG +0.083)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s6', 's5'] drops score 0.582 vs random 0.184 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.993) > s5-s6 (0.003) > s7-s8 (0.003) > s4-s5 (0.001) > s3-s4 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_throughput_mbps (IG +0.173); s5 tx_packet_rate (IG +0.169); s6 rx_throughput_mbps (IG +0.136)
- Validation: IG completeness gap 1.5e-03 (pass); zeroing top-2 switches ['s5', 's6'] drops score 0.949 vs random 0.134 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.937) > s5-s6 (0.040) > s4-s5 (0.012) > s7-s8 (0.008) > s3-s4 (0.002) > s2-s3 (0.001) > s1-s2 (0.001)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.106); s5 tx_throughput_mbps (IG +0.102); s5 tx_packet_rate (IG +0.097)
- Validation: IG completeness gap 1.1e-03 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.763 vs random 0.352 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
