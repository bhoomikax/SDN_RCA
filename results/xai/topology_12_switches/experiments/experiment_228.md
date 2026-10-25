# Explanation report: experiment 228 (12-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.373) > s7-s8 (0.219) > s8-s9 (0.154) > s4-s5 (0.116) > s9-s10 (0.049) > s10-s11 (0.023) > s5-s6 (0.022) > s2-s3 (0.020) > s3-s4 (0.015) > s1-s2 (0.008) > s11-s12 (0.002)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s6_mean_anomaly (SHAP +0.027, value 0.97); s4_mean_anomaly (SHAP +0.022, value 0.25); s7_max_anomaly (SHAP +0.020, value 1.94)
- Validation: additivity error 3.8e-16 (pass); top-3 neutralization drop 0.080 vs random 0.023 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.659) > s1-s2 (0.636) > s10-s11 (0.591) > s9-s10 (0.591) > s2-s3 (0.545) > s3-s4 (0.545) > s4-s5 (0.545) > s8-s9 (0.500) > s7-s8 (0.500) > s5-s6 (0.455) > s6-s7 (0.432)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 11
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.991 (utility 1.00); endpoint_imbalance=0.005 (utility 0.55); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=0.991, s12:1=0.996; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.988) > s7-s8 (0.009) > s5-s6 (0.003) > s4-s5 (0.000) > s8-s9 (0.000) > s9-s10 (0.000) > s11-s12 (0.000) > s10-s11 (0.000) > s3-s4 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.119); s1 tx_packet_rate (IG +0.117); s12 rx_throughput_mbps (IG +0.112)
- Validation: IG completeness gap 2.1e-04 (pass); zeroing top-2 switches ['s7', 's6'] drops score 0.661 vs random 0.078 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.936) > s7-s8 (0.027) > s8-s9 (0.015) > s10-s11 (0.007) > s3-s4 (0.005) > s5-s6 (0.004) > s4-s5 (0.003) > s9-s10 (0.001) > s11-s12 (0.001) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_packet_rate (IG +0.071); s7 rx_throughput_mbps (IG +0.068); s6 tx_throughput_mbps (IG +0.064)
- Validation: IG completeness gap 4.7e-04 (pass); zeroing top-2 switches ['s6', 's7'] drops score 0.262 vs random 0.076 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.834) > s7-s8 (0.087) > s4-s5 (0.027) > s9-s10 (0.017) > s3-s4 (0.012) > s11-s12 (0.010) > s8-s9 (0.005) > s10-s11 (0.005) > s5-s6 (0.003) > s1-s2 (0.001) > s2-s3 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.079); s3 tx_packet_rate (IG +0.074); s8 rx_packet_rate (IG +0.067)
- Validation: IG completeness gap 6.5e-03 (pass); zeroing top-2 switches ['s6', 's8'] drops score 0.347 vs random 0.090 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
