# Explanation report: experiment 242 (12-switch topology)

Ground-truth faulty link: **s9-s10**. Candidate links: 11. All scores are uncalibrated ranking scores (not probabilities). The fault window is selected with the annotated phase (oracle); attributions are associations with the model score, not causal proof.

## Random Forest

- Predicted ranking: s9-s10 (0.336) > s4-s5 (0.170) > s5-s6 (0.098) > s8-s9 (0.097) > s7-s8 (0.089) > s10-s11 (0.069) > s6-s7 (0.063) > s1-s2 (0.032) > s2-s3 (0.028) > s3-s4 (0.015) > s11-s12 (0.004)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: shap.TreeExplainer exact Shapley values on the refit held-out-fold RandomForest (48 features)
- Score semantics: RandomForest predict_proba vote fractions; uncalibrated ranking scores, not calibrated probabilities
- Main supporting features for predicted s9-s10: s9_mean_anomaly (SHAP +0.042, value 1.27); s8_persistence (SHAP +0.030, value 0.25); s8_mean_anomaly (SHAP +0.019, value 0.61)
- Validation: additivity error 4.1e-16 (pass); top-3 neutralization drop 0.170 vs random 0.009 (pass)
- Limitations: Attribution is to RF anomaly-statistic features, not raw counters; features are z-score summaries per switch. SHAP explains the model's vote fraction, not a causal effect of the link on telemetry. Classes absent from the training fold cannot receive attribution.

## Topology ranker

- Predicted ranking: s10-s11 (0.659) > s9-s10 (0.636) > s11-s12 (0.614) > s8-s9 (0.591) > s5-s6 (0.545) > s7-s8 (0.523) > s6-s7 (0.523) > s3-s4 (0.477) > s2-s3 (0.477) > s1-s2 (0.477) > s4-s5 (0.477)
- Ground truth: s9-s10; Top-1 INCORRECT; rank of truth 2
- Relevant switches/ports: predicted s10 port 2, s11 port 1; truth s9 port 2, s10 port 1
- Method: Transparent heuristic: four components ranked across all candidates with equal-weight utilities; leave-one-component-out sensitivity
- Score semantics: Equal-weight mean of rank utilities in (0, 1]; not a probability
- Predicted link components: link_anomaly=1.076 (utility 1.00); endpoint_imbalance=0.005 (utility 0.55); pair_onset_seconds=999.000 (utility 0.55); propagation_margin_seconds=-10.000 (utility 0.55)
- Endpoint anomaly: s10:2=1.076, s11:1=1.081; deciding components: ['link_anomaly']
- Limitations: Exposure of a fixed heuristic, not a learned attribution. Onset times are relative to the annotated fault start (oracle window). Component ties produce averaged ranks; ties are listed in the evaluation's score_ties column.

## GCN

- Predicted ranking: s9-s10 (0.786) > s10-s11 (0.193) > s7-s8 (0.011) > s8-s9 (0.009) > s6-s7 (0.001) > s11-s12 (0.000) > s1-s2 (0.000) > s2-s3 (0.000) > s5-s6 (0.000) > s3-s4 (0.000) > s4-s5 (0.000)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s9 tx_throughput_mbps (IG +0.108); s9 tx_packet_rate (IG +0.099); s11 rx_packet_rate (IG +0.083)
- Validation: IG completeness gap 4.2e-04 (pass); zeroing top-2 switches ['s10', 's11'] drops score 0.459 vs random 0.200 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## LSTM

- Predicted ranking: s9-s10 (0.957) > s5-s6 (0.015) > s8-s9 (0.007) > s1-s2 (0.006) > s4-s5 (0.005) > s10-s11 (0.004) > s6-s7 (0.004) > s2-s3 (0.001) > s7-s8 (0.001) > s11-s12 (0.000) > s3-s4 (0.000)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_throughput_mbps (IG +0.046); s5 tx_throughput_mbps (IG +0.046); s5 tx_packet_rate (IG +0.043)
- Validation: IG completeness gap 1.5e-04 (pass); zeroing top-2 switches ['s5', 's6'] drops score 0.173 vs random 0.021 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.

## GCN+LSTM

- Predicted ranking: s9-s10 (0.867) > s5-s6 (0.038) > s4-s5 (0.031) > s8-s9 (0.019) > s2-s3 (0.016) > s1-s2 (0.009) > s10-s11 (0.008) > s11-s12 (0.004) > s7-s8 (0.003) > s6-s7 (0.002) > s3-s4 (0.002)
- Ground truth: s9-s10; Top-1 CORRECT; rank of truth 1
- Relevant switches/ports: predicted s9 port 2, s10 port 1; truth s9 port 2, s10 port 1
- Method: Integrated gradients (512 steps) on the normalized fault-window graph sequence through the 3-seed mean-softmax ensemble; node/edge/timestep occlusion
- Score semantics: Mean softmax over seeds; uncalibrated ranking scores, not calibrated probabilities
- Main supporting switch/feature attributions: s11 rx_packet_rate (IG +0.040); s11 rx_throughput_mbps (IG +0.040); s1 rx_throughput_mbps (IG +0.032)
- Validation: IG completeness gap 1.4e-04 (pass); zeroing top-2 switches ['s11', 's2'] drops score 0.295 vs random 0.189 (pass)
- Limitations: Attributions are to normalized switch-level port-sum telemetry, not raw counters or individual ports. IG baseline is the training-mean fault-window state; a different baseline changes attributions. GNNExplainer (PyG) was not applied: it expects a single-graph forward(x, edge_index); these models consume a graph sequence. Explanations describe the ensemble's score function, not a causal mechanism in the network.
