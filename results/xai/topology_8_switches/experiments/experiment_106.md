# Explanation report: experiment 106 (8-switch topology)

Ground-truth faulty link: **s6-s7**. Candidate links: 7. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s6-s7 (0.636) > s7-s8 (0.176) > s5-s6 (0.132) > s4-s5 (0.040) > s2-s3 (0.007) > s3-s4 (0.007) > s1-s2 (0.003)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (32 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s6-s7: s5_mean_anomaly (SHAP +0.054, value 0.33); s6_max_anomaly (SHAP +0.045, value 1.28); s5_persistence (SHAP +0.044, value 0.00)
- Validation: additivity error 2.9e-16 (pass); top-3 neutralization drop 0.289 vs random 0.075 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s3-s4 (0.607) > s6-s7 (0.571) > s7-s8 (0.571) > s2-s3 (0.571) > s4-s5 (0.571) > s5-s6 (0.571) > s1-s2 (0.536)
- Ground truth: s6-s7; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s3 port 2, s4 port 1; truth s6 port 2, s7 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=0.282 (utility 0.57); endpoint_imbalance=0.002 (utility 0.71); pair_onset_seconds=999.000 (utility 0.57); propagation_margin_seconds=-10.000 (utility 0.57)
- Endpoint anomaly: s3:2=0.282, s4:1=0.284; deciding components: ['link_anomaly', 'endpoint_imbalance']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s6-s7 (0.998) > s5-s6 (0.001) > s7-s8 (0.000) > s4-s5 (0.000) > s3-s4 (0.000) > s2-s3 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_packet_rate (IG +0.087); s5 tx_throughput_mbps (IG +0.082); s1 tx_throughput_mbps (IG +0.069)
- Validation: IG completeness gap 1.2e-03 (pass); zeroing top-2 switches ['s5', 's4'] drops score 0.916 vs random 0.157 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s6-s7 (0.995) > s5-s6 (0.002) > s7-s8 (0.002) > s4-s5 (0.001) > s2-s3 (0.000) > s3-s4 (0.000) > s1-s2 (0.000)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s5 tx_throughput_mbps (IG +0.151); s5 tx_packet_rate (IG +0.149); s6 rx_packet_rate (IG +0.121)
- Validation: IG completeness gap 1.7e-03 (pass); zeroing top-2 switches ['s5', 's6'] drops score 0.874 vs random 0.052 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s6-s7 (0.644) > s7-s8 (0.126) > s5-s6 (0.114) > s4-s5 (0.057) > s3-s4 (0.042) > s2-s3 (0.012) > s1-s2 (0.004)
- Ground truth: s6-s7; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s6 port 2, s7 port 1; truth s6 port 2, s7 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s7 rx_throughput_mbps (IG +0.053); s8 rx_throughput_mbps (IG +0.053); s6 rx_throughput_mbps (IG -0.049)
- Validation: IG completeness gap 1.8e-03 (pass); zeroing top-2 switches ['s7', 's8'] drops score 0.395 vs random 0.096 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
