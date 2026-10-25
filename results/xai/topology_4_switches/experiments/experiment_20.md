# Explanation report: experiment 20 (4-switch topology)

Ground-truth faulty link: **s1-s2**. Candidate links: 3. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s2-s3 (0.425) > s3-s4 (0.407) > s1-s2 (0.168)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s1 port 2, s2 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (16 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s2-s3: s4_persistence (SHAP +0.075, value 0.89); s4_mean_anomaly (SHAP -0.042, value 1.03); s3_persistence (SHAP +0.036, value 0.89)
- Validation: additivity error 2.8e-16 (pass); top-3 neutralization drop 0.020 vs random -0.040 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.833) > s3-s4 (0.667) > s1-s2 (0.500)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s1 port 2, s2 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.682 (utility 1.00); endpoint_imbalance=0.066 (utility 1.00); pair_onset_seconds=999.000 (utility 0.67); propagation_margin_seconds=-10.000 (utility 0.67)
- Endpoint anomaly: s2:2=0.748, s3:1=0.682; deciding components: none (robust to any single component)
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s1-s2 (0.973) > s3-s4 (0.017) > s2-s3 (0.010)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.025); s1 tx_packet_rate (IG +0.024); s1 rx_packet_rate (IG -0.022)
- Validation: IG completeness gap 2.7e-05 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.849 vs random 0.146 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s2-s3 (0.501) > s3-s4 (0.441) > s1-s2 (0.058)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 tx_throughput_mbps (IG +0.177); s2 tx_packet_rate (IG +0.170); s1 rx_packet_rate (IG +0.131)
- Validation: IG completeness gap 4.4e-04 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.378 vs random 0.300 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.804) > s3-s4 (0.122) > s2-s3 (0.073)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 tx_throughput_mbps (IG +0.256); s1 tx_packet_rate (IG +0.233); s1 rx_throughput_mbps (IG -0.183)
- Validation: IG completeness gap 1.2e-03 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.792 vs random 0.318 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
