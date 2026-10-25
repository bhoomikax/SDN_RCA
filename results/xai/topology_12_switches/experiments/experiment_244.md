# Explanation report: experiment 244 (12-switch topology)

Ground-truth faulty link: **s11-s12**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s11-s12 (0.737) > s10-s11 (0.151) > s9-s10 (0.052) > s8-s9 (0.042) > s7-s8 (0.012) > s6-s7 (0.004) > s4-s5 (0.001) > s5-s6 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s3-s4 (0.000)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s11-s12: s9_max_anomaly (SHAP +0.049, value 0.28); s9_mean_anomaly (SHAP +0.049, value 0.22); s10_first_anomaly_seconds (SHAP +0.046, value 999.00)
- Validation: additivity error 3.8e-16 (pass); top-3 neutralization drop 0.259 vs random 0.095 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.682) > s3-s4 (0.682) > s6-s7 (0.659) > s2-s3 (0.568) > s4-s5 (0.568) > s11-s12 (0.545) > s8-s9 (0.523) > s5-s6 (0.500) > s7-s8 (0.455) > s9-s10 (0.455) > s10-s11 (0.364)
- Ground truth: s11-s12; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s11 port 2, s12 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.242 (utility 0.91); endpoint_imbalance=0.000 (utility 0.73); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s1:2=0.242, s2:1=0.243; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s11-s12 (0.679) > s9-s10 (0.041) > s6-s7 (0.040) > s2-s3 (0.040) > s7-s8 (0.039) > s10-s11 (0.029) > s5-s6 (0.028) > s1-s2 (0.027) > s3-s4 (0.027) > s8-s9 (0.026) > s4-s5 (0.026)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_packet_rate (IG -0.097); s11 rx_packet_rate (IG +0.091); s12 rx_throughput_mbps (IG -0.090)
- Validation: IG completeness gap 3.4e-03 (pass); zeroing top-2 switches ['s11', 's10'] drops score 0.627 vs random 0.117 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s11-s12 (0.953) > s10-s11 (0.027) > s7-s8 (0.009) > s8-s9 (0.003) > s2-s3 (0.002) > s4-s5 (0.002) > s3-s4 (0.001) > s9-s10 (0.001) > s6-s7 (0.001) > s1-s2 (0.001) > s5-s6 (0.001)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s10 tx_throughput_mbps (IG +0.141); s10 tx_packet_rate (IG +0.139); s11 rx_packet_rate (IG +0.121)
- Validation: IG completeness gap 9.7e-05 (pass); zeroing top-2 switches ['s10', 's11'] drops score 0.812 vs random 0.065 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s11-s12 (0.395) > s10-s11 (0.324) > s7-s8 (0.078) > s6-s7 (0.066) > s8-s9 (0.061) > s9-s10 (0.056) > s4-s5 (0.010) > s3-s4 (0.004) > s1-s2 (0.003) > s2-s3 (0.002) > s5-s6 (0.001)
- Ground truth: s11-s12; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s11 port 2, s12 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_throughput_mbps (IG +0.009); s12 rx_throughput_mbps (IG -0.009); s11 rx_packet_rate (IG +0.009)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.044 vs random 0.007 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
