# Explanation report: experiment 233 (12-switch topology)

Ground-truth faulty link: **s11-s12**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s11-s12 (0.663) > s10-s11 (0.219) > s8-s9 (0.068) > s7-s8 (0.021) > s9-s10 (0.017) > s6-s7 (0.008) > s2-s3 (0.004) > s1-s2 (0.000) > s3-s4 (0.000) > s4-s5 (0.000) > s5-s6 (0.000)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s11-s12: s9_mean_anomaly (SHAP +0.044, value 0.20); s11_mean_anomaly (SHAP +0.040, value 0.99); s10_first_anomaly_seconds (SHAP +0.039, value 999.00)
- Validation: additivity error 3.8e-16 (pass); top-3 neutralization drop 0.193 vs random 0.077 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.705) > s4-s5 (0.659) > s1-s2 (0.636) > s3-s4 (0.614) > s5-s6 (0.614) > s11-s12 (0.545) > s6-s7 (0.500) > s7-s8 (0.500) > s10-s11 (0.455) > s8-s9 (0.386) > s9-s10 (0.386)
- Ground truth: s11-s12; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s11 port 2, s12 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.232 (utility 0.91); endpoint_imbalance=0.001 (utility 0.82); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s2:2=0.232, s3:1=0.233; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s11-s12 (0.999) > s10-s11 (0.001) > s4-s5 (0.000) > s5-s6 (0.000) > s2-s3 (0.000) > s1-s2 (0.000) > s3-s4 (0.000) > s6-s7 (0.000) > s7-s8 (0.000) > s9-s10 (0.000) > s8-s9 (0.000)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_throughput_mbps (IG -0.090); s1 rx_packet_rate (IG -0.087); s11 rx_packet_rate (IG +0.087)
- Validation: IG completeness gap 5.2e-03 (pass); zeroing top-2 switches ['s10', 's9'] drops score 0.721 vs random 0.165 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s11-s12 (0.945) > s10-s11 (0.033) > s7-s8 (0.005) > s8-s9 (0.004) > s5-s6 (0.003) > s4-s5 (0.003) > s9-s10 (0.002) > s1-s2 (0.002) > s2-s3 (0.002) > s3-s4 (0.001) > s6-s7 (0.001)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s10 tx_packet_rate (IG +0.122); s10 tx_throughput_mbps (IG +0.121); s11 rx_packet_rate (IG +0.103)
- Validation: IG completeness gap 8.3e-04 (pass); zeroing top-2 switches ['s10', 's9'] drops score 0.414 vs random 0.059 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s10-s11 (0.455) > s11-s12 (0.241) > s9-s10 (0.117) > s8-s9 (0.104) > s7-s8 (0.043) > s3-s4 (0.012) > s1-s2 (0.012) > s6-s7 (0.008) > s2-s3 (0.004) > s5-s6 (0.003) > s4-s5 (0.001)
- Ground truth: s11-s12; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_throughput_mbps (IG +0.034); s11 rx_throughput_mbps (IG -0.032); s12 rx_packet_rate (IG +0.022)
- Validation: IG completeness gap 2.8e-03 (pass); zeroing top-2 switches ['s12', 's7'] drops score 0.062 vs random 0.008 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
