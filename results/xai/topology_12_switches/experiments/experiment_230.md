# Explanation report: experiment 230 (12-switch topology)

Ground-truth faulty link: **s8-s9**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s8-s9 (0.330) > s7-s8 (0.264) > s10-s11 (0.162) > s9-s10 (0.086) > s6-s7 (0.078) > s4-s5 (0.020) > s5-s6 (0.020) > s2-s3 (0.015) > s11-s12 (0.012) > s3-s4 (0.010) > s1-s2 (0.002)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s8-s9: s7_first_anomaly_seconds (SHAP +0.019, value 999.00); s8_mean_anomaly (SHAP +0.019, value 1.06); s7_persistence (SHAP +0.018, value 0.00)
- Validation: additivity error 4.4e-16 (pass); top-3 neutralization drop 0.092 vs random 0.018 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.659) > s2-s3 (0.614) > s11-s12 (0.568) > s10-s11 (0.568) > s9-s10 (0.568) > s4-s5 (0.568) > s3-s4 (0.523) > s6-s7 (0.523) > s8-s9 (0.477) > s5-s6 (0.477) > s7-s8 (0.455)
- Ground truth: s8-s9; Top-1 INCORRECT; rank of truth 9
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s8 port 2, s9 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.294 (utility 0.64); endpoint_imbalance=0.000 (utility 0.91); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s1:2=0.294, s2:1=0.294; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s8-s9 (0.988) > s9-s10 (0.010) > s7-s8 (0.001) > s10-s11 (0.000) > s6-s7 (0.000) > s11-s12 (0.000) > s2-s3 (0.000) > s1-s2 (0.000) > s4-s5 (0.000) > s5-s6 (0.000) > s3-s4 (0.000)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.106); s10 rx_packet_rate (IG +0.096); s1 tx_packet_rate (IG +0.093)
- Validation: IG completeness gap 1.9e-04 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.443 vs random 0.309 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s8-s9 (0.832) > s7-s8 (0.072) > s9-s10 (0.042) > s6-s7 (0.014) > s10-s11 (0.014) > s3-s4 (0.009) > s4-s5 (0.009) > s2-s3 (0.003) > s5-s6 (0.003) > s11-s12 (0.002) > s1-s2 (0.000)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 tx_throughput_mbps (IG +0.085); s7 tx_packet_rate (IG +0.085); s8 rx_packet_rate (IG +0.071)
- Validation: IG completeness gap 1.7e-04 (pass); zeroing top-2 switches ['s8', 's7'] drops score 0.454 vs random 0.068 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s8-s9 (0.583) > s7-s8 (0.190) > s6-s7 (0.152) > s9-s10 (0.036) > s10-s11 (0.015) > s11-s12 (0.009) > s4-s5 (0.005) > s2-s3 (0.005) > s3-s4 (0.003) > s5-s6 (0.002) > s1-s2 (0.001)
- Ground truth: s8-s9; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s8 port 2, s9 port 1; truth s8 port 2, s9 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.097); s7 rx_packet_rate (IG +0.090); s8 rx_throughput_mbps (IG +0.073)
- Validation: IG completeness gap 2.2e-04 (pass); zeroing top-2 switches ['s8', 's7'] drops score 0.485 vs random 0.095 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
