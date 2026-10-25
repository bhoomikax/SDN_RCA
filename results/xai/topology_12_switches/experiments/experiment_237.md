# Explanation report: experiment 237 (12-switch topology)

Ground-truth faulty link: **s4-s5**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s5-s6 (0.306) > s1-s2 (0.160) > s2-s3 (0.154) > s4-s5 (0.103) > s6-s7 (0.086) > s9-s10 (0.066) > s7-s8 (0.052) > s8-s9 (0.034) > s3-s4 (0.028) > s10-s11 (0.011) > s11-s12 (0.000)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s4 port 2, s5 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s5-s6: s1_max_anomaly (SHAP +0.035, value 2.17); s2_max_anomaly (SHAP +0.020, value 2.21); s4_mean_anomaly (SHAP +0.015, value 1.46)
- Validation: additivity error 3.7e-16 (pass); top-3 neutralization drop 0.085 vs random 0.023 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.682) > s9-s10 (0.682) > s10-s11 (0.636) > s8-s9 (0.636) > s5-s6 (0.636) > s4-s5 (0.545) > s7-s8 (0.523) > s6-s7 (0.455) > s1-s2 (0.432) > s3-s4 (0.386) > s2-s3 (0.386)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s4 port 2, s5 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.038 (utility 0.91); endpoint_imbalance=0.007 (utility 0.73); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=1.038, s12:1=1.044; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s4-s5 (0.536) > s5-s6 (0.371) > s2-s3 (0.047) > s3-s4 (0.023) > s6-s7 (0.011) > s9-s10 (0.004) > s7-s8 (0.003) > s8-s9 (0.002) > s10-s11 (0.001) > s11-s12 (0.000) > s1-s2 (0.000)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_throughput_mbps (IG -0.097); s4 tx_throughput_mbps (IG +0.083); s3 tx_packet_rate (IG -0.077)
- Validation: IG completeness gap 7.3e-04 (pass); zeroing top-2 switches ['s4', 's6'] drops score 0.356 vs random 0.144 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.635) > s2-s3 (0.166) > s3-s4 (0.084) > s4-s5 (0.066) > s1-s2 (0.013) > s7-s8 (0.009) > s10-s11 (0.009) > s9-s10 (0.008) > s8-s9 (0.004) > s6-s7 (0.003) > s11-s12 (0.001)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_throughput_mbps (IG +0.067); s3 tx_packet_rate (IG +0.062); s4 rx_packet_rate (IG +0.060)
- Validation: IG completeness gap 9.3e-04 (pass); zeroing top-2 switches ['s3', 's7'] drops score -0.009 vs random -0.056 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.433) > s9-s10 (0.297) > s5-s6 (0.201) > s1-s2 (0.024) > s8-s9 (0.013) > s4-s5 (0.012) > s3-s4 (0.007) > s10-s11 (0.005) > s7-s8 (0.004) > s6-s7 (0.003) > s11-s12 (0.000)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_packet_rate (IG -0.165); s3 tx_throughput_mbps (IG -0.164); s4 tx_packet_rate (IG +0.139)
- Validation: IG completeness gap 7.8e-04 (pass); zeroing top-2 switches ['s5', 's6'] drops score 0.420 vs random -0.066 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
