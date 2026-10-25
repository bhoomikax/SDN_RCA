# Explanation report: experiment 232 (12-switch topology)

Ground-truth faulty link: **s10-s11**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s10-s11 (0.403) > s8-s9 (0.243) > s11-s12 (0.224) > s7-s8 (0.063) > s9-s10 (0.045) > s6-s7 (0.015) > s2-s3 (0.004) > s4-s5 (0.002) > s3-s4 (0.001) > s5-s6 (0.000) > s1-s2 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s10-s11: s9_max_anomaly (SHAP +0.030, value 0.39); s9_first_anomaly_seconds (SHAP +0.030, value 999.00); s10_max_anomaly (SHAP +0.027, value 1.17)
- Validation: additivity error 3.7e-16 (pass); top-3 neutralization drop 0.145 vs random 0.019 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s4-s5 (0.659) > s1-s2 (0.614) > s2-s3 (0.591) > s11-s12 (0.568) > s6-s7 (0.568) > s7-s8 (0.568) > s10-s11 (0.523) > s3-s4 (0.523) > s5-s6 (0.523) > s8-s9 (0.477) > s9-s10 (0.386)
- Ground truth: s10-s11; Top-1 INCORRECT; rank of truth 7
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s10 port 2, s11 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.260 (utility 0.55); endpoint_imbalance=0.000 (utility 1.00); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s4:2=0.260, s5:1=0.261; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s10-s11 (0.934) > s9-s10 (0.054) > s11-s12 (0.010) > s2-s3 (0.002) > s8-s9 (0.000) > s6-s7 (0.000) > s7-s8 (0.000) > s1-s2 (0.000) > s4-s5 (0.000) > s5-s6 (0.000) > s3-s4 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.087); s1 tx_packet_rate (IG +0.080); s9 rx_throughput_mbps (IG +0.078)
- Validation: IG completeness gap 1.5e-03 (pass); zeroing top-2 switches ['s10', 's12'] drops score 0.336 vs random 0.201 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s10-s11 (0.890) > s11-s12 (0.062) > s9-s10 (0.024) > s8-s9 (0.012) > s7-s8 (0.008) > s6-s7 (0.002) > s4-s5 (0.001) > s2-s3 (0.001) > s5-s6 (0.001) > s1-s2 (0.000) > s3-s4 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 tx_packet_rate (IG +0.127); s9 tx_throughput_mbps (IG +0.125); s10 rx_packet_rate (IG +0.112)
- Validation: IG completeness gap 4.4e-03 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.575 vs random 0.091 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s10-s11 (0.697) > s11-s12 (0.161) > s9-s10 (0.072) > s8-s9 (0.050) > s7-s8 (0.012) > s6-s7 (0.005) > s4-s5 (0.002) > s2-s3 (0.001) > s1-s2 (0.001) > s5-s6 (0.000) > s3-s4 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_throughput_mbps (IG +0.202); s10 rx_throughput_mbps (IG -0.193); s12 rx_throughput_mbps (IG +0.186)
- Validation: IG completeness gap 1.4e-03 (pass); zeroing top-2 switches ['s12', 's11'] drops score 0.631 vs random 0.179 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
