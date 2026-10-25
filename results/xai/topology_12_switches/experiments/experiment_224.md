# Explanation report: experiment 224 (12-switch topology)

Ground-truth faulty link: **s2-s3**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s1-s2 (0.280) > s4-s5 (0.209) > s2-s3 (0.205) > s6-s7 (0.071) > s8-s9 (0.065) > s5-s6 (0.059) > s9-s10 (0.041) > s3-s4 (0.040) > s7-s8 (0.025) > s10-s11 (0.004) > s11-s12 (0.000)
- Ground truth: s2-s3; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s2 port 2, s3 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s1-s2: s3_max_anomaly (SHAP +0.024, value 2.21); s1_persistence (SHAP -0.022, value 0.00); s2_persistence (SHAP +0.021, value 0.86)
- Validation: additivity error 3.9e-16 (pass); top-3 neutralization drop 0.078 vs random 0.018 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s11-s12 (0.636) > s9-s10 (0.614) > s10-s11 (0.568) > s5-s6 (0.568) > s3-s4 (0.545) > s2-s3 (0.545) > s4-s5 (0.545) > s7-s8 (0.523) > s1-s2 (0.523) > s8-s9 (0.500) > s6-s7 (0.432)
- Ground truth: s2-s3; Top-1 INCORRECT; rank of truth 6
- Relevant switches/ports: predicted s11 port 2, s12 port 1; truth s2 port 2, s3 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.998 (utility 0.73); endpoint_imbalance=0.006 (utility 0.73); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s11:2=0.998, s12:1=1.004; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s2-s3 (0.994) > s3-s4 (0.006) > s4-s5 (0.000) > s1-s2 (0.000) > s6-s7 (0.000) > s5-s6 (0.000) > s9-s10 (0.000) > s7-s8 (0.000) > s8-s9 (0.000) > s11-s12 (0.000) > s10-s11 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG -0.094); s1 tx_packet_rate (IG -0.086); s2 tx_throughput_mbps (IG +0.085)
- Validation: IG completeness gap 3.3e-03 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.333 vs random 0.172 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.877) > s4-s5 (0.069) > s3-s4 (0.040) > s5-s6 (0.007) > s1-s2 (0.003) > s7-s8 (0.002) > s9-s10 (0.001) > s6-s7 (0.000) > s10-s11 (0.000) > s11-s12 (0.000) > s8-s9 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 rx_packet_rate (IG +0.116); s3 rx_throughput_mbps (IG +0.104); s2 tx_throughput_mbps (IG +0.102)
- Validation: IG completeness gap 1.5e-03 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.519 vs random 0.111 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.639) > s4-s5 (0.209) > s5-s6 (0.069) > s3-s4 (0.039) > s1-s2 (0.031) > s10-s11 (0.004) > s9-s10 (0.004) > s7-s8 (0.002) > s8-s9 (0.001) > s6-s7 (0.001) > s11-s12 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s8 rx_throughput_mbps (IG +0.081); s5 rx_throughput_mbps (IG +0.079); s9 rx_throughput_mbps (IG +0.077)
- Validation: IG completeness gap 1.4e-04 (pass); zeroing top-2 switches ['s3', 's5'] drops score 0.318 vs random 0.156 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
