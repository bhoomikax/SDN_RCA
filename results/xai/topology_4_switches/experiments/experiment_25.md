# Explanation report: experiment 25 (4-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.365) > s2-s3 (0.336) > s1-s2 (0.299)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s2_max_anomaly (SHAP -0.047, value 1.06); s4_persistence (SHAP +0.046, value 1.00); s2_mean_anomaly (SHAP -0.045, value 1.06)
- Validation: additivity error 3.3e-16 (pass); top-3 neutralization drop 0.200 vs random 0.043 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.750) > s1-s2 (0.667) > s2-s3 (0.583)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.591 (utility 1.00); endpoint_imbalance=0.280 (utility 0.67); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s3:2=0.871, s4:1=0.591; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s1-s2 (0.341) > s3-s4 (0.330) > s2-s3 (0.330)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG -0.466); s4 tx_packet_rate (IG -0.466); s1 tx_throughput_mbps (IG +0.320)
- Validation: IG completeness gap 1.7e-03 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.341 vs random -0.219 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s1-s2 (0.765) > s3-s4 (0.118) > s2-s3 (0.117)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_packet_rate (IG +0.025); s1 tx_throughput_mbps (IG +0.023); s2 tx_packet_rate (IG +0.015)
- Validation: IG completeness gap 4.2e-04 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.083 vs random 0.039 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.367) > s2-s3 (0.319) > s1-s2 (0.313)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG +0.360); s1 tx_throughput_mbps (IG -0.347); s4 tx_packet_rate (IG +0.323)
- Validation: IG completeness gap 9.2e-05 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.174 vs random 0.092 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
