# Explanation report: experiment 206 (12-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.583) > s7-s8 (0.129) > s4-s5 (0.120) > s8-s9 (0.063) > s5-s6 (0.029) > s9-s10 (0.029) > s3-s4 (0.015) > s2-s3 (0.012) > s10-s11 (0.009) > s11-s12 (0.007) > s1-s2 (0.003)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s6_mean_anomaly (SHAP +0.033, value 1.01); s4_mean_anomaly (SHAP +0.031, value 0.25); s7_mean_anomaly (SHAP +0.030, value 1.82)
- Validation: additivity error 3.9e-16 (pass); top-3 neutralization drop 0.112 vs random 0.040 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s10-s11 (0.636) > s11-s12 (0.614) > s2-s3 (0.614) > s9-s10 (0.591) > s4-s5 (0.568) > s3-s4 (0.545) > s8-s9 (0.523) > s1-s2 (0.523) > s5-s6 (0.477) > s7-s8 (0.477) > s6-s7 (0.432)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 11
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.037 (utility 0.91); endpoint_imbalance=0.005 (utility 0.55); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s10:2=1.037, s11:1=1.042; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.998) > s7-s8 (0.001) > s5-s6 (0.000) > s4-s5 (0.000) > s8-s9 (0.000) > s1-s2 (0.000) > s11-s12 (0.000) > s9-s10 (0.000) > s10-s11 (0.000) > s2-s3 (0.000) > s3-s4 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_throughput_mbps (IG -0.124); s6 tx_throughput_mbps (IG +0.117); s5 tx_packet_rate (IG -0.113)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s7', 's8'] drops score 0.658 vs random 0.137 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.916) > s7-s8 (0.050) > s3-s4 (0.009) > s5-s6 (0.006) > s4-s5 (0.006) > s8-s9 (0.006) > s10-s11 (0.005) > s9-s10 (0.002) > s11-s12 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.089); s7 rx_packet_rate (IG +0.085); s6 tx_throughput_mbps (IG +0.075)
- Validation: IG completeness gap 2.7e-03 (pass); zeroing top-2 switches ['s7', 's8'] drops score 0.338 vs random 0.045 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.708) > s7-s8 (0.134) > s4-s5 (0.035) > s11-s12 (0.026) > s8-s9 (0.026) > s9-s10 (0.025) > s10-s11 (0.024) > s3-s4 (0.012) > s2-s3 (0.005) > s5-s6 (0.004) > s1-s2 (0.001)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 rx_throughput_mbps (IG +0.129); s8 rx_throughput_mbps (IG +0.129); s8 rx_packet_rate (IG +0.102)
- Validation: IG completeness gap 1.8e-03 (pass); zeroing top-2 switches ['s1', 's6'] drops score 0.382 vs random 0.072 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
