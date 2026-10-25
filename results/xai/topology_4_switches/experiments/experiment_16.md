# Explanation report: experiment 16 (4-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.369) > s3-s4 (0.326) > s1-s2 (0.304)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s2_mean_anomaly (SHAP -0.092, value 0.72); s2_persistence (SHAP -0.054, value 0.40); s3_persistence (SHAP +0.044, value 0.90)
- Validation: additivity error 1.1e-16 (pass); top-3 neutralization drop 0.023 vs random -0.039 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.750) > s3-s4 (0.667) > s2-s3 (0.583)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.540 (utility 0.67); endpoint_imbalance=0.020 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s1:2=0.540, s2:1=0.560; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.604) > s1-s2 (0.365) > s2-s3 (0.031)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG +0.216); s4 tx_packet_rate (IG +0.205); s3 tx_throughput_mbps (IG +0.104)
- Validation: IG completeness gap 4.4e-04 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.604 vs random 0.556 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s1-s2 (0.646) > s3-s4 (0.231) > s2-s3 (0.123)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.054); s1 tx_packet_rate (IG +0.053); s2 tx_throughput_mbps (IG +0.032)
- Validation: IG completeness gap 3.3e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.133 vs random 0.086 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.565) > s2-s3 (0.227) > s3-s4 (0.208)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.107); s1 tx_packet_rate (IG +0.098); s2 tx_throughput_mbps (IG +0.092)
- Validation: IG completeness gap 1.9e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.248 vs random 0.136 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
