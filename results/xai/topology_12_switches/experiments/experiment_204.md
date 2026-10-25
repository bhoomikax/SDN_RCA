# Explanation report: experiment 204 (12-switch topology)

Ground-truth faulty link: **s4-s5**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.311) > s3-s4 (0.182) > s4-s5 (0.142) > s5-s6 (0.133) > s2-s3 (0.070) > s7-s8 (0.060) > s1-s2 (0.040) > s11-s12 (0.027) > s9-s10 (0.016) > s8-s9 (0.015) > s10-s11 (0.003)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s4 port 2, s5 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s3_mean_anomaly (SHAP +0.023, value 0.26); s3_max_anomaly (SHAP +0.020, value 0.31); s2_mean_anomaly (SHAP +0.017, value 0.26)
- Validation: additivity error 3.9e-16 (pass); top-3 neutralization drop 0.088 vs random 0.009 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.636) > s9-s10 (0.614) > s10-s11 (0.591) > s5-s6 (0.568) > s1-s2 (0.568) > s4-s5 (0.545) > s3-s4 (0.545) > s2-s3 (0.523) > s8-s9 (0.500) > s7-s8 (0.500) > s6-s7 (0.409)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s4 port 2, s5 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.055 (utility 0.91); endpoint_imbalance=0.005 (utility 0.55); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=1.055, s12:1=1.060; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s4-s5 (0.888) > s3-s4 (0.073) > s8-s9 (0.025) > s9-s10 (0.006) > s5-s6 (0.004) > s10-s11 (0.002) > s6-s7 (0.001) > s1-s2 (0.001) > s11-s12 (0.000) > s2-s3 (0.000) > s7-s8 (0.000)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.244); s1 tx_packet_rate (IG +0.218); s2 tx_throughput_mbps (IG +0.151)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s5', 's4'] drops score 0.744 vs random 0.193 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.650) > s4-s5 (0.236) > s3-s4 (0.096) > s7-s8 (0.009) > s8-s9 (0.002) > s1-s2 (0.002) > s9-s10 (0.001) > s5-s6 (0.001) > s10-s11 (0.001) > s2-s3 (0.000) > s11-s12 (0.000)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 tx_throughput_mbps (IG +0.087); s3 tx_throughput_mbps (IG +0.086); s4 rx_throughput_mbps (IG +0.078)
- Validation: IG completeness gap 1.6e-03 (pass); zeroing top-2 switches ['s3', 's2'] drops score 0.418 vs random 0.052 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.369) > s6-s7 (0.153) > s7-s8 (0.151) > s5-s6 (0.085) > s2-s3 (0.058) > s4-s5 (0.055) > s9-s10 (0.037) > s1-s2 (0.033) > s8-s9 (0.029) > s11-s12 (0.019) > s10-s11 (0.011)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.097); s6 rx_throughput_mbps (IG +0.093); s4 rx_throughput_mbps (IG -0.087)
- Validation: IG completeness gap 2.5e-04 (pass); zeroing top-2 switches ['s5', 's6'] drops score 0.346 vs random -0.003 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
