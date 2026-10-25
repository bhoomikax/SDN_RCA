# Explanation report: experiment 6 (4-switch topology)

Ground-truth faulty link: **s1-s2**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s1-s2 (1.000) > s2-s3 (0.000) > s3-s4 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s1-s2: s3_persistence (SHAP +0.113, value 0.80); s4_persistence (SHAP +0.097, value 0.80); s2_first_anomaly_seconds (SHAP +0.069, value 2.12)
- Validation: additivity error 4.4e-16 (pass); top-3 neutralization drop 0.413 vs random 0.193 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.833) > s3-s4 (0.667) > s2-s3 (0.500)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.589 (utility 1.00); endpoint_imbalance=0.117 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s1:2=0.706, s2:1=0.589; deciding components: none (robust to any single component)
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s1-s2 (0.998) > s3-s4 (0.002) > s2-s3 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG -0.002); s4 tx_packet_rate (IG -0.002); s1 tx_throughput_mbps (IG +0.001)
- Validation: IG completeness gap 5.3e-06 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.295 vs random 0.074 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s1-s2 (0.753) > s3-s4 (0.163) > s2-s3 (0.084)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_packet_rate (IG +0.084); s1 tx_throughput_mbps (IG +0.082); s2 rx_throughput_mbps (IG +0.052)
- Validation: IG completeness gap 8.5e-04 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.486 vs random 0.054 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.993) > s2-s3 (0.005) > s3-s4 (0.002)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.197); s1 tx_packet_rate (IG +0.194); s4 tx_throughput_mbps (IG -0.091)
- Validation: IG completeness gap 8.2e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.855 vs random 0.320 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
