# Explanation report: experiment 21 (4-switch topology)

Ground-truth faulty link: **s1-s2**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.709) > s2-s3 (0.284) > s1-s2 (0.007)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s1 port 2, s2 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s4_mean_anomaly (SHAP +0.096, value 1.08); s3_persistence (SHAP +0.080, value 1.00); s4_persistence (SHAP +0.071, value 1.00)
- Validation: additivity error 2.9e-16 (pass); top-3 neutralization drop 0.410 vs random 0.125 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.750) > s1-s2 (0.667) > s2-s3 (0.583)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s1 port 2, s2 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.597 (utility 1.00); endpoint_imbalance=0.289 (utility 0.67); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s3:2=0.886, s4:1=0.597; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.607) > s2-s3 (0.324) > s1-s2 (0.068)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG +0.157); s4 tx_packet_rate (IG +0.153); s1 tx_throughput_mbps (IG +0.066)
- Validation: IG completeness gap 7.8e-05 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.607 vs random 0.579 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s3-s4 (0.535) > s2-s3 (0.244) > s1-s2 (0.221)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG -0.272); s1 tx_packet_rate (IG -0.271); s3 tx_throughput_mbps (IG +0.198)
- Validation: IG completeness gap 8.5e-05 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.457 vs random 0.224 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.489) > s3-s4 (0.361) > s2-s3 (0.150)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 tx_throughput_mbps (IG -0.212); s1 tx_throughput_mbps (IG +0.202); s4 tx_packet_rate (IG -0.197)
- Validation: IG completeness gap 3.6e-03 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.198 vs random 0.053 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
