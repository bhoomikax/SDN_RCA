# Explanation report: experiment 103 (8-switch topology)

Ground-truth faulty link: **s3-s4**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s3-s4 (0.546) > s4-s5 (0.254) > s2-s3 (0.080) > s1-s2 (0.071) > s5-s6 (0.032) > s7-s8 (0.010) > s6-s7 (0.007)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s3-s4: s4_max_anomaly (SHAP +0.046, value 2.30); s3_persistence (SHAP +0.045, value 0.88); s3_mean_anomaly (SHAP +0.041, value 1.30)
- Validation: additivity error 3.3e-16 (pass); top-3 neutralization drop 0.257 vs random 0.049 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s6-s7 (0.643) > s7-s8 (0.643) > s3-s4 (0.607) > s4-s5 (0.607) > s5-s6 (0.607) > s2-s3 (0.536) > s1-s2 (0.357)
- Ground truth: s3-s4; Top-1 INCORRECT; rank of truth 3
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s3 port 2, s4 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.060 (utility 0.57); endpoint_imbalance=0.009 (utility 0.86); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s6:2=1.060, s7:1=1.070; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s3-s4 (0.978) > s4-s5 (0.020) > s2-s3 (0.002) > s5-s6 (0.000) > s7-s8 (0.000) > s1-s2 (0.000) > s6-s7 (0.000)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 rx_throughput_mbps (IG +0.091); s1 tx_throughput_mbps (IG +0.088); s1 tx_packet_rate (IG +0.084)
- Validation: IG completeness gap 1.7e-03 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.935 vs random 0.294 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s3-s4 (0.791) > s4-s5 (0.151) > s2-s3 (0.031) > s6-s7 (0.013) > s1-s2 (0.008) > s5-s6 (0.006) > s7-s8 (0.001)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_packet_rate (IG +0.081); s4 rx_throughput_mbps (IG +0.076); s3 tx_packet_rate (IG +0.069)
- Validation: IG completeness gap 5.8e-04 (pass); zeroing top-2 switches ['s4', 's3'] drops score 0.405 vs random 0.092 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s3-s4 (0.831) > s4-s5 (0.079) > s2-s3 (0.066) > s1-s2 (0.011) > s7-s8 (0.006) > s5-s6 (0.004) > s6-s7 (0.002)
- Ground truth: s3-s4; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s3 port 2, s4 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s4 rx_throughput_mbps (IG +0.519); s3 rx_throughput_mbps (IG -0.514); s4 rx_packet_rate (IG +0.412)
- Validation: IG completeness gap 1.8e-03 (pass); zeroing top-2 switches ['s4', 's5'] drops score 0.815 vs random 0.367 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
