# Explanation report: experiment 240 (12-switch topology)

Ground-truth faulty link: **s7-s8**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s8-s9 (0.318) > s6-s7 (0.267) > s7-s8 (0.175) > s11-s12 (0.072) > s9-s10 (0.071) > s10-s11 (0.061) > s4-s5 (0.019) > s3-s4 (0.008) > s2-s3 (0.008) > s5-s6 (0.002) > s1-s2 (0.001)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s7 port 2, s8 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s8-s9: s9_mean_anomaly (SHAP +0.019, value 1.73); s8_first_anomaly_seconds (SHAP +0.016, value 1.36); s9_first_anomaly_seconds (SHAP +0.016, value 1.36)
- Validation: additivity error 4.2e-16 (pass); top-3 neutralization drop 0.018 vs random 0.005 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.659) > s11-s12 (0.614) > s2-s3 (0.614) > s9-s10 (0.591) > s10-s11 (0.568) > s4-s5 (0.545) > s8-s9 (0.500) > s3-s4 (0.500) > s5-s6 (0.477) > s6-s7 (0.477) > s7-s8 (0.455)
- Ground truth: s7-s8; Top-1 INCORRECT; rank of truth 11
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s7 port 2, s8 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.230 (utility 0.55); endpoint_imbalance=0.001 (utility 1.00); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s1:2=0.230, s2:1=0.230; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s7-s8 (0.988) > s8-s9 (0.008) > s6-s7 (0.003) > s1-s2 (0.000) > s2-s3 (0.000) > s11-s12 (0.000) > s3-s4 (0.000) > s5-s6 (0.000) > s9-s10 (0.000) > s10-s11 (0.000) > s4-s5 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.127); s8 rx_packet_rate (IG +0.126); s9 rx_throughput_mbps (IG +0.126)
- Validation: IG completeness gap 5.6e-04 (pass); zeroing top-2 switches ['s8', 's9'] drops score 0.761 vs random 0.235 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s7-s8 (0.947) > s6-s7 (0.030) > s4-s5 (0.008) > s8-s9 (0.005) > s9-s10 (0.003) > s5-s6 (0.003) > s3-s4 (0.002) > s11-s12 (0.001) > s10-s11 (0.001) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_throughput_mbps (IG +0.132); s6 tx_packet_rate (IG +0.131); s7 rx_throughput_mbps (IG +0.116)
- Validation: IG completeness gap 6.6e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.524 vs random 0.184 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s7-s8 (0.577) > s6-s7 (0.150) > s8-s9 (0.098) > s10-s11 (0.066) > s11-s12 (0.045) > s9-s10 (0.043) > s4-s5 (0.011) > s2-s3 (0.004) > s3-s4 (0.003) > s1-s2 (0.002) > s5-s6 (0.001)
- Ground truth: s7-s8; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s7 port 2, s8 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 tx_throughput_mbps (IG -0.107); s6 tx_packet_rate (IG -0.106); s7 tx_packet_rate (IG +0.095)
- Validation: IG completeness gap 4.0e-04 (pass); zeroing top-2 switches ['s8', 's2'] drops score 0.418 vs random 0.169 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
