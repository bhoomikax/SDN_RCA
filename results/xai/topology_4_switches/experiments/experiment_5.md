# Explanation report: experiment 5 (4-switch topology)

Ground-truth faulty link: **s2-s3**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.849) > s3-s4 (0.135) > s1-s2 (0.016)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s2_first_anomaly_seconds (SHAP +0.071, value 1.09); s2_persistence (SHAP +0.067, value 0.90); s2_mean_anomaly (SHAP +0.065, value 1.01)
- Validation: additivity error 2.2e-16 (pass); top-3 neutralization drop 0.287 vs random 0.099 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.833) > s2-s3 (0.667) > s1-s2 (0.500)
- Ground truth: s2-s3; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s2 port 2, s3 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.565 (utility 1.00); endpoint_imbalance=0.250 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s3:2=0.814, s4:1=0.565; deciding components: none (robust to any single component)
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s2-s3 (0.999) > s3-s4 (0.001) > s1-s2 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_throughput_mbps (IG +0.269); s3 tx_packet_rate (IG +0.263); s2 tx_throughput_mbps (IG +0.257)
- Validation: IG completeness gap 3.8e-04 (pass); zeroing top-2 switches ['s3', 's2'] drops score 0.666 vs random 0.510 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.998) > s3-s4 (0.001) > s1-s2 (0.001)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_packet_rate (IG +0.382); s1 tx_throughput_mbps (IG +0.322); s2 tx_throughput_mbps (IG +0.067)
- Validation: IG completeness gap 8.6e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.881 vs random 0.450 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.797) > s3-s4 (0.167) > s1-s2 (0.036)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_packet_rate (IG +0.172); s3 tx_throughput_mbps (IG +0.171); s2 tx_packet_rate (IG +0.135)
- Validation: IG completeness gap 7.9e-04 (pass); zeroing top-2 switches ['s3', 's2'] drops score 0.641 vs random 0.579 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
