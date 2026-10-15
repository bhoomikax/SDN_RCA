# Research review presentation outline

1. **Problem:** distinguish the initiating failed SDN link from downstream symptoms.
2. **Testbed:** Mininet/OVS/Ryu chain topology; telemetry, phase events, traffic-generator evidence, and runtime port mapping.
3. **Data integrity:** immutable historical master; validated 19-experiment candidate; physical/logical IDs; exclusions and provisional run 22.
4. **Methods:** training-normal RF baseline and existing topology-aware four-component link ranker; experiment-grouped testing.
5. **Results:** fixed revised-candidate split RF 4/6 vs topology 3/6 Top-1; LOEO RF 15/18 vs topology 10/18. Show per-link errors, particularly s2-s3.
6. **Interpretation:** conditional fault-window localization uses annotated phase timing. Existing GCN/GCN+LSTM measures phase classification and is not a localization comparison.
7. **Threats/limits:** small sample, topology scope, timing mismatch, inferred historical port maps, RX zeros, correlated TX features, run23 loss, run22 provisional status.
8. **Next experiment:** balanced repeated runs with synchronized event evidence and phase-blind causal evaluation; no claim of superiority until measured.
