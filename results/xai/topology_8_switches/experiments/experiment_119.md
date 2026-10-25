# Explanation report: experiment 119 (8-switch topology)

Ground-truth faulty link: **s5-s6**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s5-s6 (0.749) > s3-s4 (0.094) > s4-s5 (0.059) > s1-s2 (0.050) > s2-s3 (0.033) > s6-s7 (0.008) > s7-s8 (0.007)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s5-s6: s5_mean_anomaly (SHAP +0.059, value 1.55); s4_persistence (SHAP +0.055, value 0.33); s6_mean_anomaly (SHAP +0.041, value 2.08)
- Validation: additivity error 2.2e-16 (pass); top-3 neutralization drop 0.083 vs random 0.032 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s7-s8 (0.679) > s6-s7 (0.643) > s5-s6 (0.607) > s3-s4 (0.571) > s4-s5 (0.571) > s2-s3 (0.464) > s1-s2 (0.464)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s5 port 2, s6 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.133 (utility 0.71); endpoint_imbalance=0.007 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s7:2=1.133, s8:1=1.141; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s5-s6 (0.997) > s4-s5 (0.001) > s3-s4 (0.001) > s6-s7 (0.001) > s1-s2 (0.000) > s7-s8 (0.000) > s2-s3 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.103); s8 rx_packet_rate (IG +0.102); s2 tx_throughput_mbps (IG +0.078)
- Validation: IG completeness gap 4.0e-04 (pass); zeroing top-2 switches ['s8', 's3'] drops score 0.089 vs random 0.153 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.994) > s1-s2 (0.003) > s3-s4 (0.002) > s6-s7 (0.000) > s4-s5 (0.000) > s2-s3 (0.000) > s7-s8 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 rx_packet_rate (IG +0.087); s6 rx_throughput_mbps (IG +0.083); s7 rx_throughput_mbps (IG +0.069)
- Validation: IG completeness gap 8.2e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.460 vs random 0.090 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s5-s6 (0.850) > s2-s3 (0.075) > s1-s2 (0.056) > s3-s4 (0.013) > s4-s5 (0.003) > s6-s7 (0.002) > s7-s8 (0.001)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 rx_throughput_mbps (IG +0.061); s1 tx_throughput_mbps (IG +0.059); s1 tx_packet_rate (IG +0.058)
- Validation: IG completeness gap 2.9e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.258 vs random 0.016 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
