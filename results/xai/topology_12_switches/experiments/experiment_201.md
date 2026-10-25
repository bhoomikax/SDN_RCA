# Explanation report: experiment 201 (12-switch topology)

Ground-truth faulty link: **s1-s2**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s1-s2 (0.516) > s2-s3 (0.222) > s4-s5 (0.167) > s5-s6 (0.042) > s6-s7 (0.015) > s9-s10 (0.015) > s3-s4 (0.010) > s7-s8 (0.008) > s8-s9 (0.006) > s10-s11 (0.001) > s11-s12 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s1-s2: s1_persistence (SHAP +0.063, value 0.88); s2_max_anomaly (SHAP +0.057, value 2.21); s2_mean_anomaly (SHAP +0.046, value 2.04)
- Validation: additivity error 4.4e-16 (pass); top-3 neutralization drop 0.303 vs random 0.051 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.636) > s5-s6 (0.636) > s10-s11 (0.591) > s9-s10 (0.591) > s2-s3 (0.568) > s3-s4 (0.545) > s4-s5 (0.545) > s1-s2 (0.523) > s8-s9 (0.500) > s7-s8 (0.455) > s6-s7 (0.409)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 8
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s1 port 2, s2 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.034 (utility 0.64); endpoint_imbalance=0.005 (utility 0.82); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=1.034, s12:1=1.040; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s1-s2 (0.987) > s2-s3 (0.012) > s5-s6 (0.001) > s9-s10 (0.000) > s8-s9 (0.000) > s4-s5 (0.000) > s6-s7 (0.000) > s11-s12 (0.000) > s7-s8 (0.000) > s3-s4 (0.000) > s10-s11 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 rx_throughput_mbps (IG +0.286); s3 rx_packet_rate (IG +0.274); s2 rx_throughput_mbps (IG +0.271)
- Validation: IG completeness gap 8.6e-04 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.525 vs random 0.161 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s1-s2 (0.598) > s2-s3 (0.350) > s5-s6 (0.025) > s4-s5 (0.015) > s3-s4 (0.007) > s7-s8 (0.002) > s6-s7 (0.002) > s11-s12 (0.001) > s9-s10 (0.001) > s10-s11 (0.001) > s8-s9 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 rx_packet_rate (IG +0.075); s2 rx_throughput_mbps (IG +0.071); s7 tx_throughput_mbps (IG +0.066)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s8', 's7'] drops score 0.298 vs random 0.165 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.391) > s5-s6 (0.317) > s2-s3 (0.272) > s9-s10 (0.013) > s4-s5 (0.005) > s8-s9 (0.001) > s3-s4 (0.001) > s10-s11 (0.000) > s11-s12 (0.000) > s6-s7 (0.000) > s7-s8 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 rx_throughput_mbps (IG +0.114); s3 rx_throughput_mbps (IG +0.110); s1 rx_throughput_mbps (IG -0.104)
- Validation: IG completeness gap 7.2e-04 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.351 vs random 0.003 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
