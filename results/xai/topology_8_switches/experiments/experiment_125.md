# Explanation report: experiment 125 (8-switch topology)

Ground-truth faulty link: **s4-s5**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s4-s5 (0.724) > s6-s7 (0.078) > s3-s4 (0.077) > s2-s3 (0.070) > s5-s6 (0.031) > s1-s2 (0.013) > s7-s8 (0.007)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s4-s5: s4_max_anomaly (SHAP +0.054, value 1.27); s4_mean_anomaly (SHAP +0.048, value 1.13); s5_mean_anomaly (SHAP +0.043, value 1.98)
- Validation: additivity error 2.2e-16 (pass); top-3 neutralization drop 0.089 vs random 0.056 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s2-s3 (0.607) > s3-s4 (0.607) > s4-s5 (0.571) > s5-s6 (0.571) > s6-s7 (0.571) > s7-s8 (0.571) > s1-s2 (0.500)
- Ground truth: s4-s5; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s2 port 2, s3 port 1; truth s4 port 2, s5 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.251 (utility 0.43); endpoint_imbalance=0.002 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s2:2=0.251, s3:1=0.254; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s4-s5 (0.996) > s3-s4 (0.003) > s5-s6 (0.002) > s6-s7 (0.000) > s2-s3 (0.000) > s7-s8 (0.000) > s1-s2 (0.000)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.099); s7 rx_packet_rate (IG +0.098); s8 rx_throughput_mbps (IG +0.093)
- Validation: IG completeness gap 9.9e-04 (pass); zeroing top-2 switches ['s6', 's3'] drops score 0.316 vs random 0.195 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s4-s5 (0.994) > s3-s4 (0.003) > s5-s6 (0.001) > s2-s3 (0.001) > s6-s7 (0.000) > s7-s8 (0.000) > s1-s2 (0.000)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_packet_rate (IG +0.117); s3 tx_throughput_mbps (IG +0.116); s4 rx_throughput_mbps (IG +0.099)
- Validation: IG completeness gap 8.7e-04 (pass); zeroing top-2 switches ['s3', 's4'] drops score 0.754 vs random 0.262 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s4-s5 (0.763) > s3-s4 (0.150) > s5-s6 (0.060) > s6-s7 (0.016) > s7-s8 (0.005) > s2-s3 (0.005) > s1-s2 (0.000)
- Ground truth: s4-s5; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s4 port 2, s5 port 1; truth s4 port 2, s5 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_packet_rate (IG +0.167); s3 tx_throughput_mbps (IG +0.154); s4 rx_throughput_mbps (IG +0.102)
- Validation: IG completeness gap 3.8e-04 (pass); zeroing top-2 switches ['s3', 's2'] drops score 0.621 vs random 0.156 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
