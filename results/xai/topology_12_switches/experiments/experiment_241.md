# Explanation report: experiment 241 (12-switch topology)

Ground-truth faulty link: **s8-s9**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s8-s9 (0.286) > s7-s8 (0.253) > s6-s7 (0.145) > s11-s12 (0.108) > s9-s10 (0.090) > s10-s11 (0.087) > s4-s5 (0.019) > s3-s4 (0.004) > s5-s6 (0.004) > s2-s3 (0.003) > s1-s2 (0.001)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s8-s9: s7_mean_anomaly (SHAP +0.027, value 0.24); s8_mean_anomaly (SHAP +0.024, value 0.99); s8_max_anomaly (SHAP +0.020, value 1.14)
- Validation: additivity error 3.8e-16 (pass); top-3 neutralization drop 0.052 vs random 0.009 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.636) > s2-s3 (0.591) > s6-s7 (0.591) > s11-s12 (0.568) > s10-s11 (0.568) > s9-s10 (0.568) > s5-s6 (0.545) > s3-s4 (0.523) > s8-s9 (0.477) > s7-s8 (0.477) > s4-s5 (0.455)
- Ground truth: s8-s9; Top-1 INCORRECT; rank of truth 9
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s8 port 2, s9 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.244 (utility 0.64); endpoint_imbalance=0.001 (utility 0.82); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s1:2=0.244, s2:1=0.244; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s8-s9 (0.994) > s9-s10 (0.003) > s7-s8 (0.003) > s3-s4 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s10-s11 (0.000) > s11-s12 (0.000) > s4-s5 (0.000) > s6-s7 (0.000) > s5-s6 (0.000)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 rx_packet_rate (IG +0.173); s9 rx_throughput_mbps (IG +0.173); s8 rx_packet_rate (IG -0.154)
- Validation: IG completeness gap 2.2e-03 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.778 vs random 0.339 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s8-s9 (0.728) > s7-s8 (0.145) > s9-s10 (0.065) > s10-s11 (0.045) > s6-s7 (0.007) > s1-s2 (0.004) > s4-s5 (0.002) > s3-s4 (0.001) > s11-s12 (0.001) > s5-s6 (0.001) > s2-s3 (0.000)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 tx_throughput_mbps (IG +0.114); s7 tx_packet_rate (IG +0.114); s8 rx_throughput_mbps (IG +0.097)
- Validation: IG completeness gap 1.7e-04 (pass); zeroing top-2 switches ['s7', 's8'] drops score 0.589 vs random 0.162 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s8-s9 (0.682) > s9-s10 (0.104) > s6-s7 (0.083) > s7-s8 (0.049) > s10-s11 (0.024) > s3-s4 (0.015) > s1-s2 (0.014) > s2-s3 (0.013) > s11-s12 (0.011) > s4-s5 (0.004) > s5-s6 (0.001)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 rx_throughput_mbps (IG +0.094); s9 rx_packet_rate (IG +0.090); s8 rx_throughput_mbps (IG -0.083)
- Validation: IG completeness gap 2.1e-03 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.330 vs random 0.186 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
