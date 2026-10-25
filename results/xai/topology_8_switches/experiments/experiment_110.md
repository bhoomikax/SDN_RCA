# Explanation report: experiment 110 (8-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.415) > s4-s5 (0.401) > s2-s3 (0.132) > s5-s6 (0.026) > s6-s7 (0.021) > s1-s2 (0.003) > s7-s8 (0.003)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s4_max_anomaly (SHAP +0.045, value 2.30); s3_mean_anomaly (SHAP +0.035, value 1.27); s3_persistence (SHAP +0.035, value 0.89)
- Validation: additivity error 3.1e-16 (pass); top-3 neutralization drop 0.218 vs random -0.001 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.607) > s3-s4 (0.571) > s4-s5 (0.571) > s5-s6 (0.571) > s6-s7 (0.571) > s7-s8 (0.571) > s1-s2 (0.536)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.280 (utility 0.29); endpoint_imbalance=0.003 (utility 1.00); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s2:2=0.280, s3:1=0.283; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.990) > s4-s5 (0.006) > s2-s3 (0.004) > s5-s6 (0.000) > s1-s2 (0.000) > s6-s7 (0.000) > s7-s8 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.093); s5 rx_packet_rate (IG +0.090); s4 rx_throughput_mbps (IG +0.085)
- Validation: IG completeness gap 1.9e-04 (pass); zeroing top-2 switches ['s5', 's4'] drops score 0.930 vs random 0.263 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s3-s4 (0.976) > s2-s3 (0.012) > s7-s8 (0.005) > s4-s5 (0.004) > s1-s2 (0.002) > s5-s6 (0.001) > s6-s7 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 tx_throughput_mbps (IG +0.070); s2 tx_packet_rate (IG +0.063); s5 rx_packet_rate (IG +0.054)
- Validation: IG completeness gap 2.2e-03 (pass); zeroing top-2 switches ['s2', 's5'] drops score 0.204 vs random 0.073 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.629) > s4-s5 (0.327) > s2-s3 (0.029) > s7-s8 (0.006) > s5-s6 (0.005) > s6-s7 (0.002) > s1-s2 (0.002)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_throughput_mbps (IG +0.142); s5 rx_throughput_mbps (IG +0.128); s4 rx_packet_rate (IG +0.112)
- Validation: IG completeness gap 9.4e-04 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.576 vs random 0.279 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
