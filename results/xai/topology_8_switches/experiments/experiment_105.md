# Explanation report: experiment 105 (8-switch topology)

Ground-truth faulty link: **s5-s6**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.397) > s4-s5 (0.193) > s5-s6 (0.184) > s7-s8 (0.169) > s2-s3 (0.034) > s3-s4 (0.023) > s1-s2 (0.000)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s5 port 2, s6 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s4_persistence (SHAP +0.041, value 0.00); s4_mean_anomaly (SHAP +0.039, value 0.33); s4_max_anomaly (SHAP +0.039, value 0.42)
- Validation: additivity error 2.4e-16 (pass); top-3 neutralization drop 0.200 vs random 0.038 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s5-s6 (0.571) > s6-s7 (0.571) > s7-s8 (0.571) > s2-s3 (0.571) > s3-s4 (0.571) > s1-s2 (0.571) > s4-s5 (0.571)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.149 (utility 1.00); endpoint_imbalance=0.012 (utility 0.14); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s5:2=1.149, s6:1=1.161; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s4-s5 (0.574) > s6-s7 (0.263) > s5-s6 (0.164) > s3-s4 (0.000) > s7-s8 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 rx_throughput_mbps (IG +0.402); s6 rx_packet_rate (IG +0.375); s5 rx_throughput_mbps (IG -0.370)
- Validation: IG completeness gap 2.4e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.570 vs random 0.186 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.589) > s4-s5 (0.206) > s5-s6 (0.193) > s3-s4 (0.007) > s7-s8 (0.003) > s1-s2 (0.001) > s2-s3 (0.001)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG +0.138); s4 tx_packet_rate (IG +0.135); s5 rx_packet_rate (IG +0.114)
- Validation: IG completeness gap 7.4e-04 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.554 vs random 0.139 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s4-s5 (0.710) > s6-s7 (0.199) > s3-s4 (0.051) > s7-s8 (0.019) > s5-s6 (0.015) > s2-s3 (0.004) > s1-s2 (0.003)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_packet_rate (IG -0.279); s4 tx_throughput_mbps (IG -0.264); s5 rx_throughput_mbps (IG -0.240)
- Validation: IG completeness gap 1.6e-03 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.669 vs random 0.347 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
