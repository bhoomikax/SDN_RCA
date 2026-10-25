# Explanation report: experiment 101 (8-switch topology)

Ground-truth faulty link: **s1-s2**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s1-s2 (0.727) > s2-s3 (0.253) > s5-s6 (0.017) > s3-s4 (0.003) > s4-s5 (0.000) > s6-s7 (0.000) > s7-s8 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s1-s2: s1_mean_anomaly (SHAP +0.080, value 1.42); s2_max_anomaly (SHAP +0.078, value 2.36); s2_mean_anomaly (SHAP +0.066, value 2.28)
- Validation: additivity error 3.3e-16 (pass); top-3 neutralization drop 0.411 vs random 0.114 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.571) > s2-s3 (0.571) > s1-s2 (0.571) > s4-s5 (0.571) > s5-s6 (0.571) > s6-s7 (0.571) > s7-s8 (0.571)
- Ground truth: s1-s2; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s1 port 2, s2 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.247 (utility 1.00); endpoint_imbalance=0.037 (utility 0.14); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s3:2=1.247, s4:1=1.284; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s1-s2 (0.994) > s2-s3 (0.006) > s3-s4 (0.000) > s5-s6 (0.000) > s6-s7 (0.000) > s7-s8 (0.000) > s4-s5 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 rx_throughput_mbps (IG -0.234); s2 rx_throughput_mbps (IG +0.225); s1 rx_packet_rate (IG -0.215)
- Validation: IG completeness gap 1.8e-03 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.975 vs random 0.098 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s1-s2 (0.986) > s2-s3 (0.007) > s3-s4 (0.003) > s5-s6 (0.002) > s4-s5 (0.001) > s6-s7 (0.000) > s7-s8 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s2 rx_packet_rate (IG +0.118); s2 rx_throughput_mbps (IG +0.115); s1 tx_packet_rate (IG +0.098)
- Validation: IG completeness gap 1.4e-03 (pass); zeroing top-2 switches ['s2', 's1'] drops score 0.562 vs random 0.041 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s1-s2 (0.990) > s3-s4 (0.004) > s2-s3 (0.003) > s5-s6 (0.002) > s7-s8 (0.001) > s6-s7 (0.000) > s4-s5 (0.000)
- Ground truth: s1-s2; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s1 port 2, s2 port 1; truth s1 port 2, s2 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s1 rx_throughput_mbps (IG -0.159); s1 tx_throughput_mbps (IG +0.127); s1 tx_packet_rate (IG +0.116)
- Validation: IG completeness gap 2.9e-03 (pass); zeroing top-2 switches ['s2', 's3'] drops score 0.693 vs random 0.134 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
