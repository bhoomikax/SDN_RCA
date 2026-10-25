# Explanation report: experiment 23 (4-switch topology)

Ground-truth faulty link: **s2-s3**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.424) > s2-s3 (0.391) > s1-s2 (0.185)
- Ground truth: s2-s3; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s2 port 2, s3 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s4_mean_anomaly (SHAP +0.061, value 1.01); s4_persistence (SHAP -0.056, value 0.89); s3_persistence (SHAP +0.048, value 1.00)
- Validation: additivity error 1.7e-16 (pass); top-3 neutralization drop 0.157 vs random 0.044 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.750) > s3-s4 (0.750) > s1-s2 (0.500)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.654 (utility 1.00); endpoint_imbalance=0.116 (utility 0.67); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s2:2=0.770, s3:1=0.654; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s2-s3 (0.993) > s3-s4 (0.007) > s1-s2 (0.000)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_throughput_mbps (IG +0.245); s3 tx_packet_rate (IG +0.244); s2 rx_packet_rate (IG +0.236)
- Validation: IG completeness gap 3.2e-04 (pass); zeroing top-2 switches ['s3', 's2'] drops score 0.985 vs random 0.778 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.801) > s3-s4 (0.197) > s1-s2 (0.001)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.318); s1 tx_packet_rate (IG +0.283); s2 tx_throughput_mbps (IG +0.067)
- Validation: IG completeness gap 6.1e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.747 vs random 0.069 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.982) > s3-s4 (0.015) > s1-s2 (0.003)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG -0.444); s1 tx_packet_rate (IG -0.431); s3 tx_throughput_mbps (IG +0.339)
- Validation: IG completeness gap 6.8e-04 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.969 vs random 0.803 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
