# Explanation report: experiment 243 (12-switch topology)

Ground-truth faulty link: **s10-s11**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s10-s11 (0.637) > s8-s9 (0.122) > s9-s10 (0.087) > s11-s12 (0.074) > s7-s8 (0.048) > s6-s7 (0.014) > s2-s3 (0.008) > s3-s4 (0.004) > s1-s2 (0.003) > s4-s5 (0.003) > s5-s6 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s10-s11: s9_max_anomaly (SHAP +0.049, value 0.39); s9_mean_anomaly (SHAP +0.042, value 0.35); s8_mean_anomaly (SHAP +0.038, value 0.35)
- Validation: additivity error 3.8e-16 (pass); top-3 neutralization drop 0.252 vs random 0.042 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.591) > s4-s5 (0.591) > s6-s7 (0.591) > s9-s10 (0.591) > s10-s11 (0.568) > s2-s3 (0.545) > s11-s12 (0.523) > s3-s4 (0.523) > s5-s6 (0.523) > s7-s8 (0.477) > s8-s9 (0.477)
- Ground truth: s10-s11; Top-1 INCORRECT; rank of truth 5
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s10 port 2, s11 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.312 (utility 0.73); endpoint_imbalance=0.002 (utility 0.55); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s1:2=0.312, s2:1=0.314; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s10-s11 (0.996) > s9-s10 (0.003) > s11-s12 (0.001) > s8-s9 (0.000) > s4-s5 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s3-s4 (0.000) > s6-s7 (0.000) > s7-s8 (0.000) > s5-s6 (0.000)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_throughput_mbps (IG +0.244); s12 rx_packet_rate (IG +0.243); s11 rx_throughput_mbps (IG +0.213)
- Validation: IG completeness gap 8.5e-04 (pass); zeroing top-2 switches ['s11', 's12'] drops score 0.866 vs random 0.242 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s10-s11 (0.916) > s11-s12 (0.047) > s8-s9 (0.018) > s9-s10 (0.011) > s7-s8 (0.002) > s4-s5 (0.002) > s1-s2 (0.001) > s5-s6 (0.001) > s2-s3 (0.001) > s6-s7 (0.001) > s3-s4 (0.001)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 tx_packet_rate (IG +0.140); s9 tx_throughput_mbps (IG +0.139); s10 rx_packet_rate (IG +0.123)
- Validation: IG completeness gap 2.7e-03 (pass); zeroing top-2 switches ['s9', 's10'] drops score 0.504 vs random 0.113 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s10-s11 (0.428) > s11-s12 (0.414) > s9-s10 (0.094) > s8-s9 (0.036) > s7-s8 (0.012) > s6-s7 (0.008) > s4-s5 (0.003) > s5-s6 (0.003) > s1-s2 (0.002) > s2-s3 (0.001) > s3-s4 (0.001)
- Ground truth: s10-s11; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s10 port 2, s11 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s12 rx_throughput_mbps (IG +0.068); s12 rx_packet_rate (IG +0.067); s11 rx_throughput_mbps (IG +0.066)
- Validation: IG completeness gap 1.7e-05 (pass); zeroing top-2 switches ['s12', 's11'] drops score 0.259 vs random 0.149 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
