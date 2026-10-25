# Explanation report: experiment 239 (12-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.620) > s4-s5 (0.119) > s7-s8 (0.106) > s8-s9 (0.037) > s5-s6 (0.029) > s11-s12 (0.027) > s3-s4 (0.025) > s9-s10 (0.020) > s10-s11 (0.009) > s2-s3 (0.007) > s1-s2 (0.001)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s4_mean_anomaly (SHAP +0.036, value 0.24); s6_mean_anomaly (SHAP +0.033, value 1.01); s5_mean_anomaly (SHAP +0.031, value 0.22)
- Validation: additivity error 6.7e-16 (pass); top-3 neutralization drop 0.127 vs random 0.045 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.636) > s9-s10 (0.614) > s2-s3 (0.614) > s3-s4 (0.591) > s10-s11 (0.568) > s7-s8 (0.523) > s1-s2 (0.523) > s4-s5 (0.523) > s8-s9 (0.500) > s5-s6 (0.477) > s6-s7 (0.432)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 11
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.039 (utility 1.00); endpoint_imbalance=0.005 (utility 0.45); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=1.039, s12:1=1.045; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.962) > s7-s8 (0.036) > s5-s6 (0.001) > s8-s9 (0.001) > s9-s10 (0.000) > s4-s5 (0.000) > s10-s11 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s11-s12 (0.000) > s3-s4 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.145); s7 rx_packet_rate (IG +0.127); s6 tx_packet_rate (IG +0.117)
- Validation: IG completeness gap 1.1e-03 (pass); zeroing top-2 switches ['s7', 's8'] drops score 0.625 vs random 0.159 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.985) > s7-s8 (0.007) > s4-s5 (0.003) > s8-s9 (0.002) > s9-s10 (0.001) > s5-s6 (0.000) > s3-s4 (0.000) > s11-s12 (0.000) > s2-s3 (0.000) > s10-s11 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_packet_rate (IG +0.048); s2 tx_throughput_mbps (IG +0.045); s7 rx_throughput_mbps (IG +0.042)
- Validation: IG completeness gap 3.3e-04 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.029 vs random 0.031 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.661) > s7-s8 (0.148) > s9-s10 (0.075) > s8-s9 (0.046) > s4-s5 (0.030) > s2-s3 (0.011) > s10-s11 (0.008) > s3-s4 (0.007) > s5-s6 (0.006) > s1-s2 (0.005) > s11-s12 (0.004)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_packet_rate (IG +0.051); s8 rx_packet_rate (IG +0.048); s4 tx_throughput_mbps (IG +0.046)
- Validation: IG completeness gap 7.5e-04 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.278 vs random 0.076 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
