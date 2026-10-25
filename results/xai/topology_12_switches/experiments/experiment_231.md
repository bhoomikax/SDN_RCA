# Explanation report: experiment 231 (12-switch topology)

Ground-truth faulty link: **s9-s10**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s9-s10 (0.285) > s8-s9 (0.245) > s10-s11 (0.170) > s7-s8 (0.081) > s6-s7 (0.059) > s4-s5 (0.059) > s5-s6 (0.040) > s11-s12 (0.026) > s2-s3 (0.024) > s1-s2 (0.006) > s3-s4 (0.005)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s9-s10: s9_mean_anomaly (SHAP +0.030, value 1.09); s9_max_anomaly (SHAP +0.030, value 1.84); s8_persistence (SHAP +0.023, value 0.12)
- Validation: additivity error 3.9e-16 (pass); top-3 neutralization drop 0.076 vs random 0.003 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s7-s8 (0.591) > s11-s12 (0.568) > s10-s11 (0.568) > s9-s10 (0.568) > s4-s5 (0.568) > s6-s7 (0.568) > s2-s3 (0.545) > s1-s2 (0.545) > s8-s9 (0.545) > s3-s4 (0.477) > s5-s6 (0.455)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 4
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s9 port 2, s10 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.341 (utility 0.27); endpoint_imbalance=0.000 (utility 1.00); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s7:2=0.341, s8:1=0.341; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s9-s10 (0.977) > s8-s9 (0.017) > s10-s11 (0.005) > s1-s2 (0.000) > s2-s3 (0.000) > s7-s8 (0.000) > s4-s5 (0.000) > s3-s4 (0.000) > s11-s12 (0.000) > s6-s7 (0.000) > s5-s6 (0.000)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_throughput_mbps (IG +0.104); s11 rx_packet_rate (IG +0.100); s10 rx_throughput_mbps (IG +0.087)
- Validation: IG completeness gap 2.3e-04 (pass); zeroing top-2 switches ['s10', 's11'] drops score 0.647 vs random 0.387 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s9-s10 (0.993) > s10-s11 (0.002) > s8-s9 (0.001) > s4-s5 (0.001) > s6-s7 (0.001) > s5-s6 (0.001) > s1-s2 (0.001) > s3-s4 (0.000) > s7-s8 (0.000) > s11-s12 (0.000) > s2-s3 (0.000)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_packet_rate (IG +0.030); s11 rx_throughput_mbps (IG +0.029); s10 tx_packet_rate (IG +0.027)
- Validation: IG completeness gap 7.2e-03 (pass); zeroing top-2 switches ['s3', 's10'] drops score 0.014 vs random 0.012 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s9-s10 (0.615) > s4-s5 (0.122) > s1-s2 (0.091) > s2-s3 (0.066) > s5-s6 (0.056) > s8-s9 (0.016) > s11-s12 (0.011) > s10-s11 (0.010) > s3-s4 (0.008) > s6-s7 (0.004) > s7-s8 (0.002)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_throughput_mbps (IG +0.043); s12 rx_throughput_mbps (IG +0.040); s11 rx_packet_rate (IG +0.036)
- Validation: IG completeness gap 1.0e-04 (pass); zeroing top-2 switches ['s11', 's12'] drops score -0.028 vs random 0.012 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
