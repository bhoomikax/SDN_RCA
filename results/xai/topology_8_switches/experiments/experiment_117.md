# Explanation report: experiment 117 (8-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.359) > s3-s4 (0.251) > s5-s6 (0.187) > s1-s2 (0.173) > s4-s5 (0.028) > s7-s8 (0.003) > s6-s7 (0.000)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s4_first_anomaly_seconds (SHAP +0.040, value 0.00); s3_first_anomaly_seconds (SHAP +0.034, value 1.17); s4_persistence (SHAP +0.028, value 1.00)
- Validation: additivity error 2.8e-16 (pass); top-3 neutralization drop 0.189 vs random 0.040 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s6-s7 (0.643) > s7-s8 (0.643) > s5-s6 (0.607) > s3-s4 (0.571) > s4-s5 (0.571) > s1-s2 (0.500) > s2-s3 (0.464)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.115 (utility 0.57); endpoint_imbalance=0.010 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s6:2=1.115, s7:1=1.125; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.772) > s2-s3 (0.162) > s1-s2 (0.040) > s5-s6 (0.017) > s4-s5 (0.007) > s7-s8 (0.001) > s6-s7 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.176); s1 tx_packet_rate (IG +0.175); s2 tx_packet_rate (IG +0.132)
- Validation: IG completeness gap 9.1e-04 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.754 vs random 0.345 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.532) > s3-s4 (0.345) > s1-s2 (0.075) > s2-s3 (0.029) > s4-s5 (0.014) > s7-s8 (0.004) > s6-s7 (0.002)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_packet_rate (IG -0.164); s4 rx_throughput_mbps (IG -0.154); s3 tx_packet_rate (IG -0.140)
- Validation: IG completeness gap 1.2e-03 (pass); zeroing top-2 switches ['s2', 's6'] drops score 0.383 vs random 0.097 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.564) > s5-s6 (0.389) > s2-s3 (0.037) > s6-s7 (0.004) > s3-s4 (0.003) > s4-s5 (0.001) > s7-s8 (0.001)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_throughput_mbps (IG +0.618); s3 rx_throughput_mbps (IG -0.537); s4 rx_packet_rate (IG +0.401)
- Validation: IG completeness gap 7.7e-04 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.433 vs random -0.028 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
