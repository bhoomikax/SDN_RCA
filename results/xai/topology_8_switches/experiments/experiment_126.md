# Explanation report: experiment 126 (8-switch topology)

Ground-truth faulty link: **s5-s6**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s5-s6 (0.745) > s3-s4 (0.089) > s4-s5 (0.048) > s2-s3 (0.043) > s1-s2 (0.031) > s6-s7 (0.027) > s7-s8 (0.017)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s5-s6: s5_mean_anomaly (SHAP +0.055, value 1.45); s5_max_anomaly (SHAP +0.053, value 2.17); s6_mean_anomaly (SHAP +0.044, value 2.15)
- Validation: additivity error 2.1e-16 (pass); top-3 neutralization drop 0.057 vs random 0.024 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s7-s8 (0.714) > s6-s7 (0.643) > s5-s6 (0.607) > s2-s3 (0.607) > s1-s2 (0.607) > s4-s5 (0.429) > s3-s4 (0.393)
- Ground truth: s5-s6; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s7 port 2, s8 port 1; truth s5 port 2, s6 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.165 (utility 0.71); endpoint_imbalance=0.003 (utility 1.00); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s7:2=1.165, s8:1=1.168; deciding components: ['endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s5-s6 (0.999) > s4-s5 (0.001) > s6-s7 (0.000) > s1-s2 (0.000) > s3-s4 (0.000) > s7-s8 (0.000) > s2-s3 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s3 tx_throughput_mbps (IG +0.118); s3 tx_packet_rate (IG +0.111); s4 tx_throughput_mbps (IG +0.105)
- Validation: IG completeness gap 5.0e-04 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.622 vs random 0.184 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s5-s6 (0.994) > s3-s4 (0.002) > s6-s7 (0.001) > s4-s5 (0.001) > s1-s2 (0.001) > s2-s3 (0.001) > s7-s8 (0.000)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s6 rx_throughput_mbps (IG +0.037); s4 tx_throughput_mbps (IG +0.036); s4 tx_packet_rate (IG +0.036)
- Validation: IG completeness gap 2.0e-03 (pass); zeroing top-2 switches ['s4', 's6'] drops score 0.007 vs random 0.013 (FAIL)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s5-s6 (0.833) > s3-s4 (0.073) > s4-s5 (0.040) > s1-s2 (0.034) > s2-s3 (0.013) > s6-s7 (0.007) > s7-s8 (0.001)
- Ground truth: s5-s6; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s5 port 2, s6 port 1; truth s5 port 2, s6 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 rx_throughput_mbps (IG +0.098); s1 rx_packet_rate (IG +0.083); s2 rx_throughput_mbps (IG +0.070)
- Validation: IG completeness gap 5.0e-04 (pass); zeroing top-2 switches ['s1', 's2'] drops score 0.457 vs random 0.074 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
