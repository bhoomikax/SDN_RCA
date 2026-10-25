# Explanation report: experiment 10 (4-switch topology)

Ground-truth faulty link: **s2-s3**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.614) > s1-s2 (0.274) > s3-s4 (0.113)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s3_persistence (SHAP -0.074, value 0.89); s4_first_anomaly_seconds (SHAP +0.069, value 1.16); s4_mean_anomaly (SHAP +0.062, value 0.98)
- Validation: additivity error 2.8e-16 (pass); top-3 neutralization drop 0.084 vs random 0.020 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.750) > s1-s2 (0.667) > s3-s4 (0.583)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.573 (utility 0.67); endpoint_imbalance=0.230 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s2:2=0.803, s3:1=0.573; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s2-s3 (0.759) > s3-s4 (0.153) > s1-s2 (0.087)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.271); s1 tx_packet_rate (IG +0.268); s1 rx_packet_rate (IG -0.206)
- Validation: IG completeness gap 1.3e-03 (pass); zeroing top-2 switches ['s1', 's3'] drops score 0.145 vs random 0.252 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.903) > s3-s4 (0.092) > s1-s2 (0.005)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_packet_rate (IG +0.400); s1 tx_throughput_mbps (IG +0.345); s2 tx_throughput_mbps (IG +0.138)
- Validation: IG completeness gap 1.6e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.772 vs random 0.329 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s2-s3 (0.985) > s3-s4 (0.015) > s1-s2 (0.001)
- Ground truth: s2-s3; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s2 port 2, s3 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_throughput_mbps (IG +0.323); s1 tx_throughput_mbps (IG -0.319); s4 tx_throughput_mbps (IG +0.301)
- Validation: IG completeness gap 1.3e-04 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.942 vs random 0.786 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
