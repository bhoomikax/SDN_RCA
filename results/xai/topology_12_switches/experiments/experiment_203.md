# Explanation report: experiment 203 (12-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.735) > s4-s5 (0.094) > s2-s3 (0.058) > s5-s6 (0.038) > s6-s7 (0.027) > s1-s2 (0.025) > s7-s8 (0.008) > s8-s9 (0.006) > s9-s10 (0.006) > s11-s12 (0.003) > s10-s11 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s5_mean_anomaly (SHAP +0.063, value 2.00); s4_mean_anomaly (SHAP +0.048, value 2.14); s7_mean_anomaly (SHAP +0.037, value 1.93)
- Validation: additivity error 3.6e-16 (pass); top-3 neutralization drop 0.291 vs random 0.070 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s10-s11 (0.682) > s9-s10 (0.682) > s11-s12 (0.614) > s5-s6 (0.591) > s3-s4 (0.545) > s4-s5 (0.545) > s7-s8 (0.545) > s8-s9 (0.523) > s6-s7 (0.455) > s1-s2 (0.455) > s2-s3 (0.364)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.086 (utility 0.82); endpoint_imbalance=0.003 (utility 0.82); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s10:2=1.086, s11:1=1.089; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.994) > s4-s5 (0.003) > s2-s3 (0.002) > s8-s9 (0.000) > s10-s11 (0.000) > s11-s12 (0.000) > s9-s10 (0.000) > s6-s7 (0.000) > s7-s8 (0.000) > s1-s2 (0.000) > s5-s6 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.222); s1 tx_packet_rate (IG +0.194); s1 rx_throughput_mbps (IG -0.138)
- Validation: IG completeness gap 8.4e-04 (pass); zeroing top-2 switches ['s3', 's1'] drops score 0.646 vs random 0.129 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s3-s4 (0.868) > s2-s3 (0.068) > s4-s5 (0.041) > s7-s8 (0.009) > s6-s7 (0.009) > s1-s2 (0.001) > s10-s11 (0.001) > s5-s6 (0.001) > s11-s12 (0.000) > s8-s9 (0.000) > s9-s10 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_packet_rate (IG +0.137); s4 rx_throughput_mbps (IG +0.121); s3 tx_throughput_mbps (IG +0.104)
- Validation: IG completeness gap 1.0e-03 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.303 vs random 0.094 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.575) > s2-s3 (0.196) > s1-s2 (0.147) > s4-s5 (0.041) > s5-s6 (0.016) > s6-s7 (0.011) > s9-s10 (0.007) > s7-s8 (0.004) > s8-s9 (0.002) > s10-s11 (0.001) > s11-s12 (0.001)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.174); s5 rx_packet_rate (IG +0.139); s2 tx_throughput_mbps (IG -0.136)
- Validation: IG completeness gap 6.0e-04 (pass); zeroing top-2 switches ['s5', 's4'] drops score 0.218 vs random 0.056 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
