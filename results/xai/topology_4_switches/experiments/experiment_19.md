# Explanation report: experiment 19 (4-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.896) > s1-s2 (0.053) > s2-s3 (0.051)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s2_max_anomaly (SHAP +0.099, value 0.58); s2_mean_anomaly (SHAP +0.097, value 0.57); s2_first_anomaly_seconds (SHAP +0.094, value 999.00)
- Validation: additivity error 1.2e-16 (pass); top-3 neutralization drop 0.393 vs random 0.122 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s1-s2 (0.750) > s3-s4 (0.667) > s2-s3 (0.583)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.574 (utility 0.67); endpoint_imbalance=0.012 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s1:2=0.574, s2:1=0.586; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.957) > s2-s3 (0.043) > s1-s2 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_packet_rate (IG +0.204); s1 tx_throughput_mbps (IG +0.198); s4 tx_throughput_mbps (IG +0.164)
- Validation: IG completeness gap 1.1e-05 (pass); zeroing top-2 switches ['s1', 's4'] drops score 0.928 vs random 0.545 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s3-s4 (0.989) > s2-s3 (0.007) > s1-s2 (0.004)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.258); s1 tx_packet_rate (IG +0.211); s2 tx_throughput_mbps (IG +0.141)
- Validation: IG completeness gap 1.7e-03 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.433 vs random 0.352 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.735) > s2-s3 (0.258) > s1-s2 (0.006)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 tx_throughput_mbps (IG +0.372); s2 tx_packet_rate (IG +0.339); s3 tx_throughput_mbps (IG -0.189)
- Validation: IG completeness gap 2.2e-03 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.570 vs random 0.153 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
