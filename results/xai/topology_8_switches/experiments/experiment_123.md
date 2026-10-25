# Explanation report: experiment 123 (8-switch topology)

Ground-truth faulty link: **s2-s3**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.829) > s3-s4 (0.094) > s1-s2 (0.055) > s4-s5 (0.014) > s5-s6 (0.007) > s6-s7 (0.001) > s7-s8 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s2_mean_anomaly (SHAP +0.060, value 1.25); s2_first_anomaly_seconds (SHAP +0.056, value 1.19); s2_persistence (SHAP +0.052, value 0.89)
- Validation: additivity error 2.1e-16 (pass); top-3 neutralization drop 0.325 vs random 0.133 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.571) > s2-s3 (0.571) > s4-s5 (0.571) > s5-s6 (0.571) > s6-s7 (0.571) > s7-s8 (0.571) > s1-s2 (0.571)
- Ground truth: s2-s3; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s2 port 2, s3 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.214 (utility 1.00); endpoint_imbalance=0.035 (utility 0.14); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s3:2=1.214, s4:1=1.249; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s2-s3 (0.991) > s3-s4 (0.009) > s1-s2 (0.000) > s7-s8 (0.000) > s5-s6 (0.000) > s4-s5 (0.000) > s6-s7 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.200); s1 tx_packet_rate (IG +0.199); s1 rx_throughput_mbps (IG +0.076)
- Validation: IG completeness gap 8.8e-04 (pass); zeroing top-2 switches ['s1', 's5'] drops score 0.646 vs random 0.358 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.972) > s3-s4 (0.019) > s4-s5 (0.003) > s7-s8 (0.002) > s1-s2 (0.002) > s5-s6 (0.001) > s6-s7 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 rx_packet_rate (IG +0.093); s1 tx_packet_rate (IG +0.092); s3 rx_throughput_mbps (IG +0.091)
- Validation: IG completeness gap 3.1e-03 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.782 vs random 0.133 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.913) > s3-s4 (0.051) > s1-s2 (0.030) > s7-s8 (0.003) > s5-s6 (0.002) > s4-s5 (0.001) > s6-s7 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 rx_throughput_mbps (IG +0.153); s2 rx_throughput_mbps (IG -0.132); s3 rx_packet_rate (IG +0.125)
- Validation: IG completeness gap 6.0e-04 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.651 vs random 0.162 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
