# BCSE308L – Course Project

# Topology-Aware and Temporally Informed Root-Cause Analysis for Software-Defined Networks: Explainable Faulty-Link Localization on 4-, 8- and 12-Switch Mininet Topologies

*Submitted in partial fulfillment of the requirements for the Course in*

**Bachelor of Technology**
*in*
**Computer Science and Engineering**

*by*

| Reg. No. | Name |
|---|---|
| `<Reg. No. 1>` | `<STUDENT NAME 1>` |
| `<Reg. No. 2>` | `<Student Name 2>` |
| `<Reg. No. 3>` | `<Student Name 3>` |

(team members sorted on Register number)

**Under the Supervision of**
DR. YOGANAND S.
Assistant Professor Senior Grade-2
Centre for Artificial Intelligence and Research (CFAIR)

Vellore Institute of Technology
October 2026

---

## DECLARATION

I hereby declare that the project entitled **Topology-Aware and Temporally Informed Root-Cause Analysis for Software-Defined Networks: Explainable Faulty-Link Localization on 4-, 8- and 12-Switch Mininet Topologies** submitted by me, for the award of the course BCSE308L in Computer Science and Engineering to VIT is a record of bonafide work carried out by me under the supervision of Dr. Yoganand S.

I further declare that the work reported in this project has not been submitted and will not be submitted, either in part or in full, for the award of any other courses in this institute or any other institute or university.

Place: Vellore
Date: `<date>`

Signature of the Candidate

---

## CERTIFICATE

This is to certify that the project entitled **Topology-Aware and Temporally Informed Root-Cause Analysis for Software-Defined Networks: Explainable Faulty-Link Localization on 4-, 8- and 12-Switch Mininet Topologies** submitted by `<Student Name (Reg. No)>`, School of Computer Science and Engineering, VIT, for the award of the degree of Bachelor of Technology in Computer Science and Engineering, is a record of bonafide work carried out by him / her under my supervision during Fall Semester 2026-2027, as per the VIT code of academic and research ethics.

The contents of this report have not been submitted and will not be submitted either in part or in full, for the award of any other courses in this institute or any other institute or university. The project fulfills the requirements and regulations of the University and in my opinion meets the necessary standards for submission.

Place: Vellore
Date: `<date>`

Signature of the Guide                                        Examiner(s)

---

## ACKNOWLEDGEMENTS

I am deeply grateful to the management of Vellore Institute of Technology (VIT) for providing me with the opportunity and resources to undertake this project. Their commitment to fostering a conducive learning environment has been instrumental in my academic journey. The support and infrastructure provided by VIT have enabled me to explore and develop my ideas to their fullest potential.

My thanks to Dr. Jaisankar N, the Dean of the School of Computer Science and Engineering (SCOPE), for his unwavering support and encouragement. His leadership and vision have greatly inspired me to strive for excellence.

I express my profound appreciation to `<Head of Department's Name>`, the Head of the `<Department Name>`, for his/her insightful guidance and continuous support. His/her expertise and advice have been crucial in shaping the direction of my project.

I am immensely thankful to my project guide, Dr. Yoganand S., for his dedicated mentorship and invaluable feedback. His patience, knowledge, and encouragement have been pivotal in the successful completion of this project. His willingness to share his expertise and provide thoughtful guidance has been instrumental in refining my ideas and methodologies.

Thank you all for your contributions and support.

Name of the Candidate

---

## TABLE OF CONTENTS

| Sl.No | Contents | Page No. |
|---|---|---|
| | **Abstract** | i |
| 1. | **INTRODUCTION** | |
| | 1.1 Background | |
| | 1.2 Motivations | |
| | 1.3 Scope of the Project | |
| 2. | **PROJECT DESCRIPTION AND GOALS** | |
| | 2.1 Literature Review | |
| | 2.2 Research Gap | |
| | 2.3 Objectives | |
| | 2.4 Problem Statement | |
| | 2.5 Project Plan | |
| 3. | **TECHNICAL SPECIFICATION** | |
| | 3.1 Requirements | |
| | 3.2 Feasibility Study | |
| | 3.3 System Specification | |
| | 3.3.1 Hardware Specification | |
| | 3.3.2 Software Specification | |
| 4. | **DESIGN APPROACH AND DETAILS** | |
| | 4.1 System Architecture | |
| | 4.2 Topology and Fault Model | |
| | 4.3 Dataset Design | |
| | 4.4 Model Design | |
| 5. | **METHODOLOGY AND TESTING** | |
| | 5.1 Module Description | |
| | 5.2 Evaluation Methodology | |
| | 5.3 Testing | |
| 6. | **PROJECT DEMONSTRATION** | |
| 7. | **RESULT AND DISCUSSION** | |
| 8. | **CONCLUSION** | |
| 9. | **REFERENCES** | |
| | **APPENDIX A – SAMPLE CODE** | |

---

## List of Figures

| Figure No. | Title | Page No. |
|---|---|---|
| 1.1 | SDN control-plane / data-plane separation and the telemetry used in this project | |
| 2.1 | Project plan (Gantt-style timeline) | |
| 4.1 | End-to-end system architecture: VM collection, validation, evaluation, explanation | |
| 4.2 | Linear topologies with 4, 8 and 12 switches and their candidate links | |
| 4.3 | Graph snapshot representation used by the neural models | |
| 4.4 | GCN, LSTM and GCN+LSTM model architectures | |
| 5.1 | Grouped leave-one-experiment-out (LOEO) evaluation procedure | |
| 6.1 | Offline replay of a held-out experiment (`demo_rca_v3.py`) | |
| 6.2 | Sample explanation report for an 8-switch experiment | |
| 7.1 | Top-1 accuracy and MRR of the five models across 4, 8 and 12 switches (`results/comparison_4_8_12/comparison.png`) | |
| 7.2 | Throughput, latency and packet loss across the normal / fault / recovery phases (`review2_throughput.png`, `review2_latency.png`, `review2_packet_loss.png`) | |

## List of Tables

| Table No. | Title | Page No. |
|---|---|---|
| 2.1 | Summary of reviewed literature | |
| 2.2 | Project plan and milestones | |
| 3.1 | Hardware specification | |
| 3.2 | Software specification | |
| 4.1 | Candidate dataset schema | |
| 4.2 | Features per model | |
| 5.1 | Unit test inventory | |
| 7.1 | Data collected per topology | |
| 7.2 | Five-model grouped LOEO results, 4 switches (n = 25) | |
| 7.3 | Five-model grouped LOEO results, 8 switches (n = 24) | |
| 7.4 | Five-model grouped LOEO results, 12 switches (n = 26) | |
| 7.5 | Paired sign-test comparisons | |
| 7.6 | Explainability validation outcomes | |
| 7.7 | Runtime and resource measurements | |

## List of Abbreviations

| Abbreviation | Expansion |
|---|---|
| CI | Confidence Interval |
| CSV | Comma-Separated Values |
| GCN | Graph Convolutional Network |
| GNN | Graph Neural Network |
| IG | Integrated Gradients |
| LLDP | Link Layer Discovery Protocol |
| LOEO | Leave-One-Experiment-Out |
| LSTM | Long Short-Term Memory |
| MRR | Mean Reciprocal Rank |
| NTP | Network Time Protocol |
| OVS | Open vSwitch |
| RCA | Root-Cause Analysis |
| RF | Random Forest |
| RX | Receive (direction of a port counter) |
| SDN | Software-Defined Networking |
| SHA-256 | Secure Hash Algorithm, 256-bit |
| SHAP | SHapley Additive exPlanations |
| TX | Transmit (direction of a port counter) |
| UDP | User Datagram Protocol |
| VM | Virtual Machine |
| XAI | Explainable Artificial Intelligence |

## Symbols and Notations

| Symbol | Meaning |
|---|---|
| N | Number of switches in the linear topology (4, 8 or 12) |
| K = N − 1 | Number of candidate inter-switch links |
| n | Number of admitted experiments for a topology |
| z | Standardised anomaly score, \|x − μ\| / σ, with μ, σ fitted on training-normal rows |
| τ | Topology-ranker threshold (95th percentile of training-normal anomaly scores) |
| Top-k | Fraction of experiments whose true link is among the first k ranked candidates |
| MRR | Mean over experiments of 1 / (rank of the true link) |
| H_K | K-th harmonic number; random-ranking MRR equals H_K / K |

---

## ABSTRACT

Software-Defined Networking (SDN) separates the control plane from the data plane and exposes per-port statistics from every OpenFlow switch. When an inter-switch link fails, traffic disappears from every switch downstream of the fault, so many switches look anomalous at once and an operator cannot tell from a single alarm which link actually failed. This project builds and evaluates an auditable machine-learning pipeline that ranks the candidate inter-switch links of a linear SDN topology by how likely each one is the failed link, using only the packet and byte counters that Open vSwitch already exposes.

An emulated testbed was built with Mininet, Open vSwitch 2.13.1 and a Ryu OpenFlow 1.3 learning-switch controller on an Ubuntu 20.04 virtual machine. A configurable linear topology module generates chains of 4, 8 and 12 switches with 3, 7 and 11 candidate links respectively and a 10 Mbps / 5 ms bottleneck on the middle link. A safeguarded experiment runner drives a 6 Mbps UDP flow through 20-second normal, fault and recovery phases, injects a link-down fault on one link per experiment, records the runtime port-to-link mapping, and fails closed when any evidence is missing. A deterministic builder admits a run only if its schema, timestamps, phase coverage, port mapping, iperf process evidence, sender duration and offered rate all pass predeclared rules. The admitted data comprise 25, 24 and 26 experiments (16,956, 30,288 and 44,712 telemetry rows) for the three topologies.

Five localization methods were compared: a Random Forest on per-switch anomaly statistics, a fixed four-component topology-aware heuristic ranker, a Graph Convolutional Network (GCN), an LSTM, and a combined GCN+LSTM operating on sequences of per-timestamp graph snapshots. All methods were evaluated with grouped leave-one-experiment-out cross-validation in which every statistic, threshold and weight is fitted on the training experiments only. On 4, 8 and 12 switches the learned models localize the failed link far above the 1/3, 1/7 and 1/11 chance levels: GCN reached 20/25, 23/24 and 25/26 Top-1, Random Forest 20/25, 20/24 and 19/26, LSTM 18/25, 22/24 and 22/26, and GCN+LSTM 23/25, 22/24 and 20/26. The hand-built topology heuristic reached 13/25 on 4 switches but collapsed to 1/24 and 1/26 on the longer chains, and its failure mechanism was diagnosed. Paired sign tests do not establish superiority of any one learned model.

An explainability layer produces a validated per-experiment report for every model: exact TreeSHAP values for the Random Forest, integrated gradients with node, edge and time-step occlusion for the neural models, and component exposure for the heuristic, each checked by additivity or completeness tests and by deletion tests against random features. An independent audit script recomputes every reported number from per-experiment artifacts (49/49 checks per topology) and 115 unit tests pass. The evaluation is conditional on an oracle-selected fault window and uses one emulated topology family, so the results are preliminary evidence rather than a deployment benchmark; online detection and causal analysis remain future work.

---

# CHAPTER 1

# 1. INTRODUCTION

## 1.1 Background

Software-Defined Networking (SDN) moves the control logic of a network out of individual switches into a logically centralised controller. The switches become simple forwarding elements that apply flow rules installed by the controller through a southbound protocol, most commonly OpenFlow (McKeown et al., 2008). This separation gives the controller a global view of the topology and of the state of every switch, which is exactly the kind of information that fault management needs. Every OpenFlow switch maintains per-port statistics such as cumulative transmitted and received packets, bytes and drops, and these can be polled at regular intervals without adding any agent to the switch.

Fault management in a network has two distinct stages. Fault detection answers the question "is something wrong, and when did it start?". Root-cause analysis (RCA) answers "which component caused the symptoms?". The two are different problems. In a chain of switches a single failed link stops traffic on every switch beyond it, so an anomaly detector that looks at each switch individually will flag many switches, all of which are symptoms of the same cause. RCA must separate the initiating failure from the propagated symptoms. Because an SDN controller knows the topology, it is natural to ask whether topology-aware methods, in particular graph neural networks that process the switch graph directly, can localize the failed link better than methods that ignore structure.

This project studies that question on an emulated SDN testbed. Mininet (Lantz, Heller and McKeown, 2010) creates virtual hosts, Open vSwitch instances and links inside one Linux kernel, the Ryu framework provides the controller, and iperf generates traffic. Faults are injected deliberately, so the ground-truth failed link is known for every experiment, which allows supervised learning and exact evaluation.

Figure 1.1 shows the separation of control and data plane and the position of the per-port counters that form the only input to the models in this project.

> **Figure 1.1** SDN control-plane / data-plane separation and the telemetry used in this project. *(Draw: Ryu controller above; switches s1…sN below connected by OpenFlow 1.3; per-port counters tx/rx packets and bytes polled by `ovs-ofctl dump-ports`.)*

## 1.2 Motivations

Network operators today rely on threshold alarms and manual inspection to trace an outage to its source. In a large fabric a single link failure can raise dozens of alarms within seconds, and the time an operator spends finding the actual failed link is time during which the service remains degraded. Automating localization would shorten repair time directly.

Three aspects of SDN make the problem tractable in a way that it is not in traditional networks. First, the controller already has the topology, so the set of candidate links is known. Second, port counters are available from every switch through one uniform interface. Third, controlled fault injection on an emulator makes it possible to collect labelled data, which is rare in production networks.

At the same time, the machine-learning literature on RCA is dominated by results that are hard to trust: small datasets evaluated with random row-level splits that leak information between training and test, models that use the fault phase label as a feature, accuracies reported without chance levels or confidence intervals, and no explanation of why a model chose a particular answer. The motivation of this project is therefore twofold: to test whether topology- and time-aware models genuinely help localize link failures, and to do so with an evaluation protocol that is leak-free, auditable and honest about its limitations, including an explainability layer so that each ranking can be inspected rather than taken on faith.

## 1.3 Scope of the Project

The project covers the following, all of which were implemented and measured:

- An emulated linear SDN topology family with N ∈ {4, 8, 12} switches, two end hosts, N − 1 candidate inter-switch links and a 10 Mbps / 5 ms bottleneck on the middle link.
- One fault type, link failure, injected by administratively bringing both interface ends of one inter-switch link down for 20 seconds and then up again, on one link per experiment.
- One traffic profile: a single 6 Mbps UDP flow from h1 to h2 for 60 seconds, divided into 20-second normal, fault and recovery phases.
- Automated collection of per-port counters at roughly one-second intervals, with phase events, runtime port mapping, iperf logs and metadata preserved for every run.
- A validated candidate dataset per topology built under predeclared admission rules, with every rejection recorded.
- Five localization methods: Random Forest, a topology-aware heuristic ranker, GCN, LSTM and GCN+LSTM.
- Grouped leave-one-experiment-out evaluation with Top-k, MRR, Wilson confidence intervals, chance levels and paired sign tests.
- An explainability layer with validation checks for every model, and an independent audit script.

The following are explicitly out of scope. They are stated here so that the results are not over-read:

- **Online fault detection.** All models are given the annotated fault window (the first ten seconds after the fault event). This is conditional localization with an oracle fault time. A phase-blind anomaly detector was tried on the four-switch data and detected 0 of 25 fault windows; it is reported as a negative result and not used.
- **Causal root-cause discovery.** No module infers causal structure; attributions describe the model's score function, not physical causation.
- **Probability calibration.** All scores are ranking scores (vote fractions, softmax outputs or rank utilities) and are not calibrated probabilities.
- Non-linear topologies, multiple simultaneous faults, other fault types and other traffic profiles.

---

# CHAPTER 2

# 2. PROJECT DESCRIPTION AND GOALS

## 2.1 Literature Review

**SDN foundations.** McKeown et al. (2008) introduced OpenFlow as a way to run experimental protocols on campus networks by exposing the flow table of commodity switches to an external controller. Kreutz et al. (2015) survey the resulting SDN architecture, including the layered design, controller platforms and the fault-management opportunities created by the controller's global view. Lantz, Heller and McKeown (2010) presented Mininet, which uses Linux network namespaces and virtual Ethernet pairs to emulate a complete OpenFlow network on one machine and is the de-facto prototyping platform for SDN research. Pfaff et al. (2015) describe the design of Open vSwitch, the software switch that implements OpenFlow in Mininet and exposes the per-port counters used here. The Ryu framework (Ryu Project Team, 2014) is a component-based Python controller supporting OpenFlow 1.0 to 1.5 and is used in this project as a simple learning switch.

**Fault localization in SDN.** Scott et al. (2012) frame SDN fault localization as answering "what, where and when" and argue that the controller's visibility should be exploited to localize faults rather than only detect them. Falcon (Li et al., 2019) performs differential fault localization in the SDN control plane by comparing executions. These works focus on software faults in the control plane; data-plane link failures, which this project targets, are usually left to topology discovery protocols such as LLDP, which report a link as down but do not rank links from traffic evidence when discovery is slow or absent.

**Learning-based RCA.** Soldani and Brogi (2022) survey anomaly detection and failure root-cause analysis in service-based cloud applications and classify methods into those that use topology or dependency graphs and those that do not; they note that most evaluations use small datasets and that explainability is rarely addressed. Breiman (2001) introduced Random Forests, which remain a strong tabular baseline. Kipf and Welling (2017) proposed the Graph Convolutional Network, which propagates node features over the adjacency structure and is the graph model used here. Hochreiter and Schmidhuber (1997) introduced the LSTM, used here to model the temporal evolution of the network state. Fey and Lenssen (2019) provide PyTorch Geometric, the library used for the GCN layers.

**Explainable AI.** Lundberg and Lee (2017) unified several attribution methods under SHAP values, and Lundberg et al. (2020) gave the exact TreeExplainer algorithm for tree ensembles used in this project. Sundararajan, Taly and Yan (2017) proposed integrated gradients, an axiomatic attribution method for differentiable models with a completeness property that this project uses as a validation check. Ying et al. (2019) proposed GNNExplainer for single-graph GNNs; it was examined but not applied because the models here consume sequences of graphs.

**Evaluation statistics.** Wilson (1927) gave the score interval used for the Top-k confidence intervals, which behaves better than the normal approximation at the small sample sizes (n ≤ 26) in this project.

**Table 2.1** Summary of reviewed literature

| Work | Contribution | Relevance to this project |
|---|---|---|
| McKeown et al. (2008) | OpenFlow protocol | Switch counters and flow rules used by the testbed |
| Lantz et al. (2010) | Mininet emulator | Topology emulation platform |
| Pfaff et al. (2015) | Open vSwitch | Data-plane switch; source of telemetry |
| Kreutz et al. (2015) | SDN survey | Context for controller-side fault management |
| Scott et al. (2012) | What/where/when fault localization | Motivates localization rather than detection |
| Li et al. (2019) | Falcon, control-plane fault localization | Contrast: control plane vs data plane |
| Soldani and Brogi (2022) | RCA survey | Identifies small-data and explainability gaps |
| Breiman (2001) | Random Forest | Baseline model |
| Kipf and Welling (2017) | GCN | Topology-aware model |
| Hochreiter and Schmidhuber (1997) | LSTM | Temporal model |
| Lundberg and Lee (2017); Lundberg et al. (2020) | SHAP, TreeExplainer | RF explanations |
| Sundararajan et al. (2017) | Integrated gradients | Neural explanations and completeness check |
| Ying et al. (2019) | GNNExplainer | Considered; not applicable to graph sequences |
| Wilson (1927) | Score interval | Confidence intervals on Top-k |

## 2.2 Research Gap

The reviewed literature leaves the following gaps that this project addresses:

1. **Data-plane link localization from counters alone.** SDN fault-localization work concentrates on control-plane software faults; little work asks whether the failed data-plane link can be ranked from per-port counters that every switch already provides, without extra probes.
2. **Leak-free evaluation on real emulator runs.** Learning-based RCA studies frequently evaluate on random row splits of a single run, which leaks the fault signature between training and test. A grouped, experiment-level protocol with every fitted quantity restricted to the training fold is rarely reported.
3. **Scaling of topology-aware methods.** Whether a method that works on a tiny topology continues to work when the number of candidate links grows is seldom measured; most studies use one topology size.
4. **Explainability with validation.** Attribution methods are usually applied without checking that the attributions actually describe the model (completeness, additivity) or that the attributed inputs matter (deletion tests).
5. **Honest reporting.** Chance levels, confidence intervals, paired comparisons, negative results and the oracle assumptions behind "accuracy" numbers are often omitted.

## 2.3 Objectives

1. Build a reproducible Mininet / Open vSwitch / Ryu testbed with a linear topology parameterised by switch count, and an experiment runner that injects link failures and preserves all raw evidence.
2. Collect at least 24 valid experiments per topology for N = 4, 8 and 12 with faults balanced across candidate links, under predeclared admission rules.
3. Implement five localization methods, a conventional Random Forest baseline, a transparent topology-aware heuristic, and three neural models (GCN, LSTM, GCN+LSTM), that rank the candidate links from the fault-window telemetry.
4. Evaluate all methods with grouped leave-one-experiment-out cross-validation, reporting Top-k, MRR, Wilson intervals, chance levels and paired sign tests.
5. Provide a validated explanation for every ranking of every model.
6. Verify every reported number with an independent audit script and a regression test suite, and document all limitations.

## 2.4 Problem Statement

Given a linear SDN topology h1 – s1 – s2 – … – sN – h2 with K = N − 1 inter-switch candidate links, and the per-port telemetry (packet rate and throughput in both directions) of every switch during the first ten seconds of a known fault window, produce an ordered list of the K candidate links such that the link that actually failed appears as high in the list as possible. The method must learn only from other experiments (never from the held-out one), must not use phase labels, fault annotations or identifiers as predictors, and must provide an explanation of which inputs drove the ranking.

## 2.5 Project Plan

The work was carried out in the phases shown in Table 2.2 and Figure 2.1.

**Table 2.2** Project plan and milestones

| Phase | Weeks | Activities | Deliverable |
|---|---|---|---|
| 1. Study and setup | 1–2 | SDN, Mininet, Ryu, OpenFlow counters; VM setup; controller deployment | Working 4-switch testbed |
| 2. Collection pipeline | 3–4 | Telemetry collector, experiment runner, phase events, iperf evidence, runtime port mapping | Raw-evidence run directories |
| 3. Validation and dataset | 5 | Candidate builder, admission rules, provenance hashes, dataset card | Four-switch v3 candidate (25 experiments) |
| 4. Baselines | 6 | Random Forest, topology ranker, grouped LOEO evaluator | RF / ranker results |
| 5. Neural models | 7–8 | Graph builder, GCN, LSTM, GCN+LSTM, seed ensembles | Neural LOEO results |
| 6. Scaling | 9–10 | Generalise topology to N switches; collect 8- and 12-switch data; VM recovery | 24 + 26 admitted experiments |
| 7. Explainability | 11 | SHAP, integrated gradients, occlusion, component exposure, validation checks | Per-experiment explanation reports |
| 8. Audit and report | 12 | Audit script, comparison tables, unit tests, documentation, report | This report |

> **Figure 2.1** Project plan (Gantt-style timeline). *(Draw from Table 2.2.)*

---

# CHAPTER 3

# 3. TECHNICAL SPECIFICATION

## 3.1 Requirements

**Functional requirements**

- FR1: Emulate a linear SDN topology with a configurable number of switches, two hosts and a bottleneck link, controlled by an OpenFlow 1.3 controller.
- FR2: Collect per-port counters from every switch at approximately one-second intervals and derive packet rates and throughput.
- FR3: Run an experiment with normal, fault and recovery phases, inject a link-down fault on a chosen candidate link, and record the exact phase timestamps.
- FR4: Record the runtime mapping between OpenFlow port numbers, interfaces and links so that candidate links can be identified without assumptions.
- FR5: Validate every run against predeclared rules and build a labelled candidate dataset with provenance hashes, recording every exclusion with its reason.
- FR6: Build per-timestamp graph snapshots of the network for the neural models.
- FR7: Train and evaluate five localization methods under grouped leave-one-experiment-out cross-validation and report Top-k, MRR, confidence intervals and chance levels.
- FR8: Generate a validated explanation report for every experiment and model.
- FR9: Recompute every reported metric independently from per-experiment artifacts.

**Non-functional requirements**

- NFR1 (Integrity): raw evidence is immutable; derived outputs are written only to new paths; existing outputs are never overwritten.
- NFR2 (Reproducibility): fixed seeds, deterministic algorithms, pinned dependency versions, SHA-256 hashes of every input recorded in every output.
- NFR3 (Safety): the runner fails closed; a run with missing evidence is marked invalid, never admitted.
- NFR4 (Portability): collection code runs on the VM's Python 3.8; analysis code runs on Windows Python 3.13 with CPU-only PyTorch.
- NFR5 (Testability): all offline components are covered by unit tests that run without the VM.

## 3.2 Feasibility Study

**Technical feasibility.** Mininet, Open vSwitch and Ryu are mature open-source tools that run on a single Ubuntu VM; OpenFlow port counters are available through `ovs-ofctl` without any switch modification. Random Forests (scikit-learn), GCNs (PyTorch Geometric) and LSTMs (PyTorch) run on a CPU at the data sizes involved (tens of thousands of rows, at most 26 experiments per topology). A full neural LOEO for one topology completes in roughly one to a few hours of CPU time, and the RF/ranker evaluation in under a minute. The project is therefore technically feasible on a student laptop.

**Economic feasibility.** All software is free and open source. The only hardware is a laptop and a VM with 1 vCPU and 2 GB RAM. No cloud resources or commercial licences were needed.

**Operational feasibility.** The main operational risk was the single-vCPU VM: host CPU contention and host sleep events caused iperf under-pacing and sender stalls, and one host suspend corrupted the guest's timekeeping. These were handled by admission rules that reject such runs, a batch runner that stops after three consecutive failures, a documented VM reboot and preflight procedure, and a host keep-awake during collection windows. After recovery the 12-switch batch produced 17 valid runs in 17 attempts, demonstrating that the procedure is operationally workable.

**Schedule feasibility.** The twelve-week plan in Table 2.2 was met; the scaling phase required an approved extension of the 12-switch ID registry to reach two experiments for every candidate link.

## 3.3 System Specification

### 3.3.1 Hardware Specification

**Table 3.1** Hardware specification

| Component | Specification |
|---|---|
| Host machine | Laptop running Windows 11 Home (build 10.0.26300); used for analysis, training, explanation and documentation |
| Guest VM | 1 vCPU, 2 GB RAM, Ubuntu 20.04; runs Mininet, Open vSwitch, Ryu and iperf2 |
| Network between host and VM | SSH over forwarded port 2222; evidence copied with `scp` and verified with SHA-256 sums |
| Accelerator | None; all training is CPU-only |

### 3.3.2 Software Specification

**Table 3.2** Software specification

| Layer | Software | Version |
|---|---|---|
| Emulation | Mininet | VM-packaged |
| Data plane | Open vSwitch | 2.13.1 |
| Control plane | Ryu SDN framework, SimpleSwitch application, OpenFlow 1.3 | VM-packaged |
| Traffic | iperf2 | 2.0.13 |
| VM language | Python | 3.8.5 |
| Host language | Python | 3.13.7 (venv) |
| Numerics | NumPy | 2.5.3 |
| Data frames | pandas | 3.0.6 |
| Classical ML | scikit-learn | 1.9.1 |
| Deep learning | PyTorch (CPU) | 2.14.0 |
| Graph learning | PyTorch Geometric | 2.8.0.post1 |
| Explanations | SHAP | 0.54.1 |
| Testing | Python `unittest` | standard library |
| Version control | Git | – |

---

# CHAPTER 4

# 4. DESIGN APPROACH AND DETAILS

## 4.1 System Architecture

The system has two halves: a collection half that runs inside the Ubuntu VM and produces immutable raw evidence, and an analysis half that runs on the Windows host and never modifies that evidence. Figure 4.1 shows the complete data flow.

> **Figure 4.1** End-to-end system architecture. *(Draw from the description below; a Mermaid source is in `docs/COMPLETE_PROJECT_KNOWLEDGE.md`, section 2.2.)*

**Collection (VM).**

1. `linear_topology.py` defines the N-switch topology, its N − 1 candidate links, the bottleneck link, and a per-topology registry of logical and physical experiment IDs with a balanced round-robin fault schedule.
2. `run_topology_batch.py` executes registered IDs sequentially and stops on stale bridges, busy processes or three consecutive failures.
3. `experiment_runner_recollection.py --switches N` performs, for one experiment: preflight checks; Mininet network creation; recording of the runtime OpenFlow-port-to-interface mapping with `ovs-ofctl show`; start of the telemetry collector; start of the iperf UDP server and client; the normal phase; fault injection; the fault phase; fault removal; the recovery phase; validation of iperf process outcomes and summaries; and cleanup. It writes six raw files per run: `telemetry.csv`, `phase_events.csv`, `runtime_port_mapping.csv`, `run_metadata.json`, `iperf_client.log`, `iperf_server.log`.
4. `telemetry.py` polls every switch roughly once per second with `ovs-ofctl dump-ports`, derives per-port rates and throughput from counter deltas, and appends rows through `telemetry_pipeline.py`.
5. The Ryu SimpleSwitch controller learns source MAC to in-port and installs priority-1 flows; it performs no topology discovery and does not react to link-down events, so after a fault traffic simply stops beyond the failed link, which is the symptom the models learn.

**Analysis (host).**

6. Run directories are archived, copied to `raw_evidence/topology_N_switches/` and verified against `SHA256SUMS.txt`.
7. `build_topology_candidate.py` admits or rejects each run, labels every telemetry row with its phase and fault location, and writes `candidate_dataset.csv`, an experiment manifest, the canonical link-port mapping, an exclusion report and `provenance.json` with the hash of every raw file.
8. `build_graph_multi.py --switches N` converts the candidate into per-timestamp graph snapshots (`graph_dataset.json`).
9. `evaluate_topology_loeo.py` runs the Random Forest and the topology ranker under grouped LOEO; `evaluate_graph_temporal_topology_loeo.py` runs GCN, LSTM and GCN+LSTM with three seeds on the identical folds, using the RF/ranker output as a same-fold reference.
10. `explain_rca.py` produces per-experiment explanations with validation checks; `build_topology_comparison.py` assembles the cross-topology tables and plot; `audit_topology_results.py` independently recomputes every reported number.

**Integrity design.** Every writer uses exclusive-create mode and refuses existing output directories. Every evaluation summary records the SHA-256 of its input candidate; the neural evaluator verifies that the graph file was built from that exact candidate; the explanation module verifies both. A frozen-artifact test pins the hashes of the four-switch dataset and release results so that later code changes cannot silently alter them.

## 4.2 Topology and Fault Model

Figure 4.2 shows the three topologies.

```
h1 - s1 - s2 - s3 - s4 - h2                         N = 4,  candidates s1-s2, s2-s3, s3-s4 ; bottleneck s2-s3
h1 - s1 - s2 - ... - s8 - h2                        N = 8,  7 candidates ; bottleneck s4-s5
h1 - s1 - s2 - ... - s12 - h2                       N = 12, 11 candidates ; bottleneck s6-s7
```

> **Figure 4.2** Linear topologies with 4, 8 and 12 switches and their candidate links.

- Hosts h1 (10.0.0.1) and h2 (10.0.0.2) are attached to s1 and sN. The bottleneck link is `candidate_links[(N−1)//2]` with `bw=10 Mbps, delay=5 ms`; all other links are unshaped.
- Because Mininet adds links in order, OpenFlow port 1 of every switch faces its left neighbour and port 2 its right neighbour. This mapping is recorded at runtime, not assumed, and the builder refuses to merge runs whose mappings disagree.
- Fault: `ip link set dev <intf> down` on both ends of one candidate link for 20 s, then `up`. Faults are assigned round-robin over candidate links so every prefix of the schedule is balanced; they are not restricted to the bottleneck.
- Traffic: iperf2 UDP at 6 Mbps for 60 s (reported by iperf2 as 6.29 Mbit/s), with phases normal / fault / recovery of 20 s each.
- Labelling: a row is `normal` before the fault event, `fault` before the recovery event, and `recovery` afterwards. The **fault window** used by every model is the first 10 s of fault-phase rows; this is the oracle assumption.

## 4.3 Dataset Design

**Table 4.1** Candidate dataset schema (17 columns)

| Column | Type | Meaning |
|---|---|---|
| timestamp | ISO datetime | Sample time (VM local clock) |
| switch | string | s1 … sN |
| port | string | LOCAL, 1 or 2 |
| rx_packets, rx_bytes, rx_dropped | int | Cumulative receive counters |
| tx_packets, tx_bytes, tx_dropped | int | Cumulative transmit counters |
| rx_packet_rate, tx_packet_rate | float | Packets per nominal second (counter delta) |
| rx_throughput_mbps, tx_throughput_mbps | float | Megabits per nominal second (byte delta × 8 / 10⁶) |
| experiment_id | int | Logical experiment identifier |
| phase | enum | normal / fault / recovery (label, never a feature) |
| fault_type | enum | none / link_failure (label) |
| fault_location | string | none or the failed link (label) |

**Admission rules.** A run is admitted only if: all six raw files exist and hash-match; the schema and switch coverage are complete; all numeric values are finite; there are no duplicate (timestamp, switch, port) keys; the runtime mapping covers every switch and every candidate link reciprocally; the normal, fault and recovery events are ordered and lie within the telemetry span; iperf client and server exited successfully with parseable, agreeing summaries; the sender duration is 60 ± 2 s; and the sender's reported rate is within ±10 % of 6 Mbps. Three otherwise-complete runs that paced only about 3 Mbps were excluded by the last rule. No run was removed after seeing model results.

**Features.** Only the four rate metrics (`rx_packet_rate`, `tx_packet_rate`, `rx_throughput_mbps`, `tx_throughput_mbps`) are model inputs; cumulative counters, drops, identifiers, phases and fault annotations are never features. Per training fold a metric is "active" only if it varies in the training-normal rows; all four were active in every 8- and 12-switch fold. The LOCAL port is excluded everywhere.

**Graph representation.** For the neural models each (experiment, timestamp) becomes one graph snapshot: nodes `[h1, s1, …, sN, h2]`, edges the N + 1 physical links made bidirectional, and each switch node's feature vector is the sum over its numbered ports of the four rate metrics (host nodes are zero because hosts are not instrumented). The model input for one experiment is the sequence of the 6–10 snapshots in the ten-second fault window (Figure 4.3).

> **Figure 4.3** Graph snapshot representation used by the neural models. *(Draw: chain graph with node feature vectors; a stack of snapshots over t = 0 … 10 s.)*

## 4.4 Model Design

All five models take the fault-window telemetry of one experiment and output one score per candidate link; the ranking is the descending order of scores with a lexical tie-break on the link name. Scores are used only for ordering.

**Table 4.2** Features per model

| Model | Input representation | Learned? |
|---|---|---|
| Random Forest | 4 statistics × N switches: mean anomaly, max anomaly, persistence, first-anomaly time | Yes (300 trees, depth 5, seed 42, balanced class weights) |
| Topology ranker | Per candidate link: link anomaly, endpoint imbalance, pair onset, propagation margin | No (fixed equal-weight rank aggregation) |
| GCN | Sequence of normalized graph snapshots | Yes |
| LSTM | Sequence of flattened node-feature matrices | Yes |
| GCN+LSTM | Sequence of GCN embeddings | Yes |

**Random Forest.** Per fold, training-normal rows are averaged to the switch level and a per-switch mean and standard deviation of each active metric is fitted. For the held-out experiment, each switch's fault-window samples receive an anomaly score z = |x − μ| / σ averaged over metrics; four statistics per switch (mean, max, fraction of samples above 1.0, time of first sample above 1.0) form a vector of width 4N. The classifier's `predict_proba` gives the link scores.

**Topology ranker.** Per fold, per-(switch, port) baselines and a threshold τ equal to the 95th percentile of training-normal anomaly scores are fitted. For each candidate link the two endpoint ports give `link_anomaly` (minimum of the two endpoint mean anomalies), `endpoint_imbalance` (their absolute difference), `pair_onset_seconds` (when both endpoints first exceed τ) and `propagation_margin_seconds` (earliest remote-switch crossing minus pair onset). Each component is rank-transformed to a utility (K + 1 − rank)/K and the four utilities are averaged with equal weight. The ranker uses no labels and is fully transparent.

**Neural models (Figure 4.4).** Per fold a feature policy (active features, means, standard deviations) is fitted on training experiments only and switch rows are standardised; host rows stay zero.

- *GCN (GraphOnly):* `GCNConv(F → 16)` → ReLU → `GCNConv(16 → 12)` → ReLU per snapshot; embeddings averaged over time; `Linear((N+2)·12 → K)`.
- *LSTM (TemporalOnly):* each snapshot flattened to (N + 2)·F; `LSTM(hidden = 24)`; last output → `Linear(24 → K)`. Uses no graph structure.
- *GCN+LSTM (GraphTemporal):* the GCN encoder per snapshot, then `LSTM((N+2)·12 → 24)`, last output → `Linear(24 → K)`.

Training uses Adam (lr 0.01, weight decay 10⁻³), cross-entropy, 100 epochs, one optimizer step per training experiment, deterministic algorithms and a single thread. Three seeds (17, 42, 2026) are fitted per fold and their softmax outputs averaged into the reported ranking; the seeds are repeated fits, not additional test cases.

> **Figure 4.4** GCN, LSTM and GCN+LSTM model architectures. *(Draw the three pipelines above.)*

---

# CHAPTER 5

# 5. METHODOLOGY AND TESTING

## 5.1 Module Description

| Module | File(s) | Responsibility |
|---|---|---|
| Topology specification | `linear_topology.py` | N-switch topology, candidate links, bottleneck, ID registries, balanced fault schedule |
| Telemetry collection | `telemetry.py`, `telemetry_pipeline.py` | Poll `ovs-ofctl`, derive rates, write schema-checked CSV rows |
| Experiment runner | `experiment_runner_recollection.py`, `run_topology_batch.py` | Preflight, network creation, runtime mapping, traffic, fault injection, phase events, validation, cleanup; sequential batch with fail-closed rules |
| Dataset builder | `build_topology_candidate.py`, `build_validated_candidate.py` | Admission rules, labelling, manifest, provenance, exclusion report |
| Graph builder | `build_graph_multi.py` | Per-timestamp graph snapshots with summed port features |
| RF and ranker evaluation | `evaluate_topology_loeo.py` | Grouped LOEO for Random Forest and topology ranker |
| Neural evaluation | `graph_temporal_topology.py`, `evaluate_graph_temporal_topology_loeo.py` | GCN / LSTM / GCN+LSTM, three seeds, same folds, checkpoints |
| Explainability | `explain_rca.py` | SHAP, integrated gradients, occlusion, component exposure, validation checks, Markdown/JSON reports |
| Comparison and audit | `build_topology_comparison.py`, `audit_topology_results.py` | Cross-topology tables and plot; independent recomputation and sign tests |
| Demonstration | `demo_rca_v3.py` | Hash-verified saved replay or fresh fold inference for one held-out experiment |
| Tests | `test_*.py` (115 tests) | Offline regression and unit tests |

## 5.2 Evaluation Methodology

**Grouped leave-one-experiment-out (Figure 5.1).** Each experiment contributes roughly 1,200–1,700 highly correlated rows from one fault; a random row split would place rows of the same fault in both training and test and let a model memorise the experiment. Therefore:

1. Sort the admitted experiment IDs.
2. For each ID e, the training set is every other experiment and the held-out set is {e}.
3. Fit everything that learns from data on the training set only: active-metric selection, switch and port baselines, the ranker threshold, the Random Forest, the neural feature policy and the neural weights.
4. Build the held-out experiment's features with the training-fitted statistics, rank the K candidates, and join the true label only after ranking.
5. Aggregate experiment-level outcomes over all folds.

> **Figure 5.1** Grouped leave-one-experiment-out evaluation procedure.

**Metrics.** Top-k is the fraction of experiments whose true link is among the first k ranked candidates; MRR is the mean of 1/rank of the true link. Wilson 95 % intervals use the experiment count as n. Chance for a uniform random ranking is Top-1 = 1/K (0.333, 0.143, 0.091) and MRR = H_K/K (0.611, 0.370, 0.275) for K = 3, 7, 11. Paired comparisons use an exact two-sided sign test on the discordant experiments (A right and B wrong versus the reverse), uncorrected for the ten pairs per topology.

**Independent audit.** `audit_topology_results.py` recomputes from the per-experiment rows that no held-out ID appears in any training list, that each training fold has n − 1 experiments, that each experiment is held out exactly once, that every ranking is a permutation of the K candidates, that Top-k and MRR match, that ensemble scores equal per-seed means, that RF and neural reference files agree, and that explanation rankings agree with evaluation rankings. It passes 49/49 checks on every topology.

## 5.3 Testing

**Unit and regression tests.** The offline suite has 115 tests, all passing on the final tree, executed with `python -m unittest discover -v`. Table 5.1 summarises them.

**Table 5.1** Unit test inventory

| Test file | Tests | What it validates |
|---|---:|---|
| `test_recollection_runner.py` | 42 | ID registry, isolated paths, phase ordering, runtime mapping, target reciprocity, mocked end-to-end run, iperf validation, offered-rate rule, cleanup failures cannot yield COMPLETE |
| `test_linear_topology.py` | 13 | Counts for 4/8/12, equality with the original 4-switch study, bottleneck, registries, balanced schedules, numeric link naming |
| `test_telemetry_pipeline.py` | 9 | Port parser, collector schema, overwrite refusal |
| `test_dataset_builder.py` | 8 | Four-switch builder rules and output isolation |
| `test_evaluate_topology_loeo.py` | 6 | Mapping, `summarize` for 7 candidates, no fold leakage, synthetic 8-switch run, **frozen regression reproducing the v3 release exactly** |
| `test_graph_temporal_grouped_loeo.py` | 5 | Splits, feature policy, metrics, writers |
| `test_graph_temporal_link_rca.py` | 4 | Labels absent from tensors, 10-s window, tie-break, Wilson intervals |
| `test_explain_rca.py` | 4 | IG completeness, occlusion coverage, shapes follow N, report schema |
| `test_online_fault_detection.py` | 4 | Causality of the negative-result detector |
| `test_frozen_artifacts.py` | 3 | Pinned SHA-256 of frozen datasets and results |
| `test_topology_candidate_builder.py` | 3 | Admission of valid runs; exclusion of eight kinds of invalid runs |
| `test_audit_topology_results.py` | 3 | Exact sign test; audit passes; audit detects a tampered leaky split |
| `test_graph_builder.py` | 3 | Port-sum aggregation, LOCAL exclusion, label consistency |
| `test_demo_rca_v3.py`, `test_demo_rca.py` | 5 | Replay and fresh inference, hash checks |
| others | 3 | Evaluator loading, ledger, pilot audit |

**Integration testing.** Unit tests mock Mininet, OVS and iperf and cannot prove the live path. Live confidence comes from `--verify-topology` runs (after the VM reboot: 11 links, 0 % ping loss, 0 kernel warnings, loopback iperf 6.29 Mbps), from the 24 + 26 admitted real runs, and from the four-switch regression in which the generalised code reproduced all 50 RF/ranker rankings and all 75 neural ensemble rankings of the frozen release with score differences of 0.0.

**Explanation validation tests.** Every explanation is checked: SHAP additivity (base + ΣSHAP equals the predicted score within 10⁻⁶), IG completeness (ΣIG equals f(x) − f(baseline) within 5 % relative), ranker score recomputation, and deletion tests in which neutralising the top attributed features must lower the score at least as much as neutralising random ones (20 draws). Failures are recorded per experiment, not hidden.

**Static checks.** `py_compile` on all modules, `pip check`, and `git diff --check` pass on the final tree.

---

# CHAPTER 6

# 6. PROJECT DEMONSTRATION

The demonstration is offline and needs no VM; it reads only preserved, hash-verified artifacts.

**Step 1 – Run the test suite.**

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

Expected: 115 tests OK.

**Step 2 – Replay a held-out experiment (Figure 6.1).**

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --experiment-id 20 --method rf_baseline
```

The script verifies the SHA-256 of the candidate dataset, the saved predictions, the split file, the feature policy and the summary, then prints the experiment's ten-second fault window, the measured feature means, the saved ranking and the retrospective label.

**Step 3 – Fresh grouped inference.**

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 20 --method rf_baseline
```

The fold is refitted on the other 24 experiments and the held-out experiment is ranked live, with descriptive telemetry deltas printed alongside.

> **Figure 6.1** Offline replay of a held-out experiment.

**Step 4 – Show the cross-topology comparison.** Open `results/comparison_4_8_12/comparison_table.md` and `comparison.png` (Figure 7.1).

**Step 5 – Show an explanation report (Figure 6.2).** Open `results/xai/topology_8_switches/experiments/experiment_104.md`. For experiment 104 (true link `s4-s5`):

- Random Forest ranked `s4-s5 (0.737) > s3-s4 (0.145) > s6-s7 (0.050) > …`; the main support was `s4_max_anomaly` (SHAP +0.055), `s4_mean_anomaly` (+0.050) and `s3_first_anomaly_seconds` (+0.041); additivity error 3.3 × 10⁻¹⁶; deletion drop 0.076 versus 0.059 for random features: pass.
- GCN ranked `s4-s5 (0.996)` first; top attributions on s6 and s5 receive metrics; completeness gap 5.1 × 10⁻⁴; zeroing s6 and s5 dropped the score by 0.928 versus 0.184 for random switches: pass.
- The topology ranker ranked `s7-s8` first and the true link third; the component exposure shows the deciding component was `endpoint_imbalance`, illustrating the failure mode discussed in Chapter 7.

> **Figure 6.2** Sample explanation report for an 8-switch experiment.

**Step 6 – Run the audit.**

```powershell
.\venv\Scripts\python.exe audit_topology_results.py
```

Expected: 49/49 checks pass per topology; output in `results/audit/methodology_audit.md`.

**Live run (optional, VM required).** The live path (collect → admit → graph → inference) was exercised once on the four-switch testbed (logical 41 / physical 45): the run was admitted and Random Forest trained on the historical experiments ranked the true link `s2-s3` first. One correct prediction is not an accuracy estimate.

---

# CHAPTER 7

# 7. RESULT AND DISCUSSION

## 7.1 Data Collected

**Table 7.1** Data collected per topology

| Property | 4 switches | 8 switches | 12 switches |
|---|---|---|---|
| Registry IDs attempted | – (frozen v3) | 30 | 44 |
| Runs admitted | 25 | 24 | 26 |
| Candidate links | 3 | 7 | 11 |
| Experiments per link | 8 / 9 / 8 | 3,4,3,4,4,4,2 | 2–3 each |
| Telemetry rows | 16,956 | 30,288 | 44,712 |
| Median sampling interval | ~1.08 s | 1.23 s | 1.35 s |
| Snapshots in the 10 s fault window | 9–10 | 7–9 | 6–8 |
| RX counters | zero in 17 historical runs, nonzero in 8 recollections | nonzero in all | nonzero in all |
| Link endpoint ports | setup-inferred static mapping | recorded runtime mapping | recorded runtime mapping |

Eighteen of the 44 twelve-switch attempts were rejected (14 sender-duration or stalled runs, 2 half-rate clients, 1 suspended run, 1 incomplete run); every rejection is recorded with its reason. The sampling interval grows with switch count because the collector polls every switch sequentially on one vCPU; all models normalise within a topology, so this does not mix topologies, but larger topologies have fewer snapshots per fault window.

Figure 7.2 shows the throughput, latency and packet loss across the three phases of a representative four-switch experiment, illustrating the symptom the models learn: throughput beyond the fault drops to zero during the fault phase and recovers afterwards.

> **Figure 7.2** Throughput, latency and packet loss across the normal / fault / recovery phases.

## 7.2 Localization Results

**Table 7.2** Five-model grouped LOEO results, 4 switches (n = 25, K = 3; chance Top-1 0.333, MRR 0.611)

| Model | Top-1 | Top-2 | MRR | Top-1 Wilson 95 % CI |
|---|---:|---:|---:|---|
| Random Forest | 20/25 (80 %) | 22/25 (88 %) | 0.880 | [60.9 %, 91.1 %] |
| Topology ranker | 13/25 (52 %) | 22/25 (88 %) | 0.740 | [33.5 %, 70.0 %] |
| GCN | 20/25 (80 %) | 23/25 (92 %) | 0.887 | [60.9 %, 91.1 %] |
| LSTM | 18/25 (72 %) | 21/25 (84 %) | 0.833 | [52.4 %, 85.7 %] |
| GCN+LSTM | 23/25 (92 %) | 23/25 (92 %) | 0.947 | [75.0 %, 97.8 %] |

**Table 7.3** Five-model grouped LOEO results, 8 switches (n = 24, K = 7; chance Top-1 0.143, MRR 0.370)

| Model | Top-1 | Top-2 | Top-3 | MRR | Top-1 Wilson 95 % CI |
|---|---:|---:|---:|---:|---|
| Random Forest | 20/24 (83 %) | 23/24 (96 %) | 24/24 | 0.910 | [64.1 %, 93.3 %] |
| Topology ranker | 1/24 (4 %) | 11/24 (46 %) | 20/24 | 0.412 | [0.7 %, 20.2 %] |
| GCN | 23/24 (96 %) | 23/24 (96 %) | 24/24 | 0.972 | [79.8 %, 99.3 %] |
| LSTM | 22/24 (92 %) | 23/24 (96 %) | 24/24 | 0.951 | [74.2 %, 97.7 %] |
| GCN+LSTM | 22/24 (92 %) | 22/24 (92 %) | 22/24 | 0.933 | [74.2 %, 97.7 %] |

**Table 7.4** Five-model grouped LOEO results, 12 switches (n = 26, K = 11; chance Top-1 0.091, MRR 0.275)

| Model | Top-1 | Top-2 | Top-3 | MRR | Top-1 Wilson 95 % CI | Per-seed Top-1 |
|---|---:|---:|---:|---:|---|---|
| Random Forest | 19/26 (73 %) | 21/26 (81 %) | 24/26 | 0.824 | [53.9 %, 86.3 %] | – |
| Topology ranker | 1/26 (4 %) | 2/26 (8 %) | 2/26 | 0.200 | [0.7 %, 18.9 %] | – |
| GCN | 25/26 (96 %) | 26/26 (100 %) | 26/26 | 0.981 | [81.1 %, 99.3 %] | 25 / 22 / 25 |
| LSTM | 22/26 (85 %) | 23/26 (88 %) | 24/26 | 0.896 | [66.5 %, 93.8 %] | 21 / 21 / 20 |
| GCN+LSTM | 20/26 (77 %) | 23/26 (88 %) | 23/26 | 0.849 | [57.9 %, 89.0 %] | 13 / 13 / 17 |

> **Figure 7.1** Top-1 accuracy and MRR of the five models across 4, 8 and 12 switches (`results/comparison_4_8_12/comparison.png`).

**Table 7.5** Paired experiment-level Top-1 comparisons (exact two-sided sign test on discordant pairs, uncorrected)

| Topology | Pair | A right, B wrong | B right, A wrong | p |
|---|---|---:|---:|---:|
| 4 | RF vs topology ranker | 8 | 1 | 0.039 |
| 4 | RF vs GCN+LSTM | 0 | 3 | 0.250 |
| 4 | LSTM vs GCN+LSTM | 0 | 5 | 0.062 |
| 4 | topology ranker vs GCN+LSTM | 0 | 10 | 0.002 |
| 8 | RF vs topology ranker | 20 | 1 | < 0.001 |
| 8 | RF vs GCN | 0 | 3 | 0.250 |
| 8 | topology ranker vs each neural model | 1 | 22–23 | < 0.001 |
| 12 | RF vs topology ranker | 18 | 0 | < 0.001 |
| 12 | RF vs GCN | 0 | 6 | 0.031 |
| 12 | RF vs LSTM | 0 | 3 | 0.250 |
| 12 | GCN vs GCN+LSTM | 5 | 0 | 0.062 |
| 12 | topology ranker vs each neural model | 0 | 19–24 | < 0.001 |

## 7.3 Discussion

**Learned models localize far above chance on every topology.** On 8 switches the learned models reach 20–23 of 24 Top-1 against a 1/7 chance level, and on 12 switches 19–25 of 26 against 1/11. Most Top-1 errors of every learned model are adjacent links (ranked second or third), which is consistent with the physics: the boundary between "still carrying traffic" and "dead" is one switch wide, and a one-position error moves the boundary by one switch.

**No learned model is shown to be superior.** The Wilson intervals of RF, GCN, LSTM and GCN+LSTM overlap heavily on every topology. The only learned-model pair below p = 0.05 is RF versus GCN on 12 switches (0 versus 6 discordant experiments, p = 0.031), which does not survive a correction for the ten comparisons per topology and is not replicated on 4 switches (3 versus 3). The ordering of the three neural models also changes with topology (GCN+LSTM led on 4 switches, GCN on 8 and 12), which is what sampling noise at n ≈ 25 looks like. GCN+LSTM's individual seeds reach only 13–17 of 26 on 12 switches while its ensemble reaches 20, so its fits are unstable at this sample size.

**The fixed topology heuristic does not transfer beyond 4 switches.** Its MRR falls to 0.412 on 8 switches (chance 0.370) and 0.200 on 12 (below chance 0.275). The mechanism was diagnosed in `results/audit/topology_ranker_8sw_investigation.md`: the training-normal 95th-percentile threshold (about 2.57) is never crossed by fault-window ports (anomaly about 1.1–1.2, because per-port normal standard deviations are of the same order as the mean rate), so the onset and propagation components are constants; with a link down every downstream link shares the same `link_anomaly`; and the true link, having one live and one dead endpoint, has a larger `endpoint_imbalance` than fully dead downstream links, so the imbalance component cancels its advantage and ties are decided by noise. The heuristic was deliberately not modified, because any change favouring the most upstream anomalous link would have been tuned to these outcomes. The same code reproduces the four-switch release exactly, so this is a property of the heuristic on a longer chain, not a code change.

**Random Forest remains a strong baseline.** It is the simplest and fastest method, reaches 20/24 on 8 switches, and its errors on 12 switches concentrate on the two links that have only two training experiments each (both `s2-s3` and both `s4-s5` were missed), showing that per-class recall swings between 0 and 1 when support is that small.

**Explainability.** Table 7.6 summarises the validation outcomes.

**Table 7.6** Explainability validation outcomes (experiments passing all checks)

| Model | Method | Checks | 4 switches | 8 switches | 12 switches |
|---|---|---|---|---|---|
| Random Forest | exact TreeSHAP on the refit fold model | additivity; top-3 positive-SHAP deletion vs random | 25/25 | 23/24 | 26/26 |
| Topology ranker | component exposure, leave-one-component-out | score recomputation; ranking agreement | 25/25 | 24/24 | 26/26 |
| GCN | integrated gradients (512 steps) through the 3-seed ensemble; node, edge and time-step occlusion | completeness; top-2 positive-IG switch deletion vs random | 24/25 | 22/24 | 24/26 |
| LSTM | same, no edge occlusion | same | 23/25 | 23/24 | 25/26 |
| GCN+LSTM | same | same | 22/25 | 23/24 | 25/26 |

All completeness and additivity checks pass; the failures are deletion checks, meaning that for those experiments the attributed inputs were not more deletable than random ones. They are listed per experiment in each `xai_summary.json`. With 64 integration steps the completeness gap reached 0.59 on these piecewise-linear ensembles; 512 steps closed it (worst 9.6 %). The two largest-|IG| switches coincide with the predicted link's endpoints in only 12–38 % of experiments: attributions spread along the chain where traffic disappears, so the models separate links by where the traffic boundary lies rather than by the two endpoint switches alone. The explanations describe each model's score function; they are not causal evidence, and the scores are not probabilities. GNNExplainer was not applied because it expects a single-graph forward pass whereas these models consume a sequence of graphs.

**Negative result: online detection.** A phase-blind q99 anomaly detector on the four-switch data detected 0 of 25 held-out fault windows and generated 21.7 false-alarm episodes per observed non-fault hour; it does not improve on an always-no-alarm comparator. Detecting *when* a fault starts therefore remains unsolved in this project, and all localization results depend on the oracle fault window.

**Runtime.** Table 7.7 lists measured costs.

**Table 7.7** Runtime and resource measurements

| Item | Measured |
|---|---|
| Live run | 84–100 s per run (60 s traffic plus setup and teardown) |
| Collector sweep (idle) | 0.20 s (8 switches), 0.31–0.37 s (12 switches) |
| RF / ranker LOEO | under 1 min per topology |
| Neural fold fit (CPU) | roughly 90–200 s per fold on 8 switches (GCN+LSTM mean 126 s) |
| XAI, 12 switches, 26 experiments, 5 models, 512 IG steps | 685 s |
| VM | 1 vCPU, 2 GB RAM, Ubuntu 20.04 |

## 7.4 Limitations and Threats to Validity

- One emulated linear topology family on a single-vCPU VM; one fault type; one traffic profile. Generalisation to real or non-linear networks is not established.
- Oracle fault windows: every model is told when the fault began. This is conditional localization, not online RCA.
- Small samples: n ≤ 26 per topology, with only 2–3 experiments per link on 12 switches, so intervals are wide and per-class recall is unstable.
- The sampling interval grows with switch count, so larger topologies have fewer snapshots per window.
- The four-switch data has an RX-counter acquisition shift (zero in 17 historical runs, nonzero in 8 recollections) of unknown cause; the 8- and 12-switch data do not.
- Scores are uncalibrated; attributions are not causal.
- The VM clock was not NTP-synchronised, so only within-run ordering is supportable.
- Neural hyper-parameters were inherited from the four-switch study without a recorded search; training is batch-size 1 and seeds show instability on 12 switches.

---

# CHAPTER 8

# 8. CONCLUSION

This project built an end-to-end, auditable pipeline for faulty-link localization in software-defined networks and evaluated it on real Mininet runs over 4-, 8- and 12-switch linear topologies. The pipeline collects OpenFlow port counters, injects link failures with recorded ground truth, admits runs under predeclared rules, and compares five localization methods under a grouped leave-one-experiment-out protocol in which nothing is fitted on the held-out experiment.

The evidence supports a modest but well-founded claim: learned models, whether a Random Forest on per-switch anomaly statistics or graph and temporal neural networks on graph-snapshot sequences, rank the failed link far above chance on all three topologies (Top-1 of 73–96 % against chance levels of 33 %, 14 % and 9 %), and their errors are almost always adjacent links. A hand-built topology-aware heuristic that was competitive on 4 switches collapses on longer chains, and the reason was diagnosed rather than patched. No learned model is shown to be superior to another; the differences are within sampling noise at these sample sizes, and the report says so.

Every ranking of every model comes with a validated explanation, and every reported number is recomputed by an independent audit script and protected by 115 passing tests and pinned artifact hashes. The project also records its negative result honestly: a phase-blind detector did not detect any fault window, so all localization results are conditional on a known fault time.

Future work should, in order: implement and validate an online detector using only training-fold choices and new held-out experiments; collect a larger repeatability cohort with normal-only controls and phase-resolved receiver intervals; extend the topology family beyond linear chains and to multiple fault types; study probability calibration of the ranking scores; and, only with intervention-backed ground truth, attempt causal rather than associative root-cause analysis.

---

# CHAPTER 9

# 9. REFERENCES

*(Harvard format. Entries marked ◊ should be verified against the publisher record before submission.)*

1. Breiman, L., 2001. Random forests. *Machine Learning*, 45(1), pp.5–32.
2. Fey, M. and Lenssen, J.E., 2019. Fast graph representation learning with PyTorch Geometric. *ICLR 2019 Workshop on Representation Learning on Graphs and Manifolds*, New Orleans.
3. Hochreiter, S. and Schmidhuber, J., 1997. Long short-term memory. *Neural Computation*, 9(8), pp.1735–1780.
4. Kipf, T.N. and Welling, M., 2017. Semi-supervised classification with graph convolutional networks. *Proceedings of the 5th International Conference on Learning Representations (ICLR)*, Toulon.
5. Kreutz, D., Ramos, F.M.V., Veríssimo, P.E., Rothenberg, C.E., Azodolmolky, S. and Uhlig, S., 2015. Software-defined networking: a comprehensive survey. *Proceedings of the IEEE*, 103(1), pp.14–76.
6. Lantz, B., Heller, B. and McKeown, N., 2010. A network in a laptop: rapid prototyping for software-defined networks. *Proceedings of the 9th ACM SIGCOMM Workshop on Hot Topics in Networks (HotNets-IX)*, Monterey, Article 19.
7. ◊ Li, Y., Wang, Z., Yao, J., Yin, X., Shi, X., Wu, J. and Zhang, H., 2019. Falcon: differential fault localization for SDN control plane. *Computer Networks*, 162, 106851. DOI 10.1016/j.comnet.2019.07.007.
8. Lundberg, S.M. and Lee, S.-I., 2017. A unified approach to interpreting model predictions. *Advances in Neural Information Processing Systems 30 (NIPS 2017)*, Long Beach, pp.4765–4774.
9. Lundberg, S.M., Erion, G., Chen, H., DeGrave, A., Prutkin, J.M., Nair, B., Katz, R., Himmelfarb, J., Bansal, N. and Lee, S.-I., 2020. From local explanations to global understanding with explainable AI for trees. *Nature Machine Intelligence*, 2(1), pp.56–67.
10. McKeown, N., Anderson, T., Balakrishnan, H., Parulkar, G., Peterson, L., Rexford, J., Shenker, S. and Turner, J., 2008. OpenFlow: enabling innovation in campus networks. *ACM SIGCOMM Computer Communication Review*, 38(2), pp.69–74.
11. Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M. and Duchesnay, É., 2011. Scikit-learn: machine learning in Python. *Journal of Machine Learning Research*, 12, pp.2825–2830.
12. Pfaff, B., Pettit, J., Koponen, T., Jackson, E., Zhou, A., Rajahalme, J., Gross, J., Wang, A., Stringer, J., Shelar, P., Amidon, K. and Casado, M., 2015. The design and implementation of Open vSwitch. *Proceedings of the 12th USENIX Symposium on Networked Systems Design and Implementation (NSDI '15)*, Oakland, pp.117–130.
13. Ryu Project Team, 2014. *Ryu SDN Framework*. Available at: https://ryu-sdn.org (Accessed: October 2026).
14. ◊ Scott, C., Wundsam, A., Whitlock, S., Or, A., Huang, E., Zarifis, K. and Shenker, S., 2012. *How did we get into this mess? Isolating fault-inducing inputs to SDN control software* / *What, where, and when: software fault localization for SDN*. Technical Report UCB/EECS-2012-178, EECS Department, University of California, Berkeley.
15. Soldani, J. and Brogi, A., 2022. Anomaly detection and failure root cause analysis in (micro)service-based cloud applications: a survey. *ACM Computing Surveys*, 55(3), Article 59, pp.1–39.
16. Sundararajan, M., Taly, A. and Yan, Q., 2017. Axiomatic attribution for deep networks. *Proceedings of the 34th International Conference on Machine Learning (ICML)*, Sydney, PMLR 70, pp.3319–3328.
17. Wilson, E.B., 1927. Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), pp.209–212.
18. Ying, R., Bourgeois, D., You, J., Zitnik, M. and Leskovec, J., 2019. GNNExplainer: generating explanations for graph neural networks. *Advances in Neural Information Processing Systems 32 (NeurIPS 2019)*, Vancouver, pp.9240–9251.

---

# APPENDIX A – SAMPLE CODE

**A.1 Linear topology specification (`linear_topology.py`, excerpt)**

```python
SUPPORTED_SWITCH_COUNTS = (4, 8, 12)
BOTTLENECK_PARAMS = {"bw": 10, "delay": "5ms"}
HOSTS = ("h1", "h2")
FAULT_TYPE = "link_failure"


class LinearTopology(object):
    def __init__(self, switch_count):
        count = int(switch_count)
        if count < 2:
            raise ValueError("A linear topology needs at least two switches")
        self.switch_count = count
        self.switches = tuple("s%d" % index for index in range(1, count + 1))
        self.hosts = HOSTS
        self.candidate_links = tuple(
            "%s-%s" % (self.switches[index], self.switches[index + 1])
            for index in range(count - 1)
        )
        self.bottleneck_link = self.candidate_links[(count - 1) // 2]
        definitions = [("h1", "s1", None)]
        for link in self.candidate_links:
            left, right = link.split("-")
            params = dict(BOTTLENECK_PARAMS) if link == self.bottleneck_link else None
            definitions.append((left, right, params))
        definitions.append((self.switches[-1], "h2", None))
        self.link_definitions = tuple(definitions)
        self.nodes = ("h1",) + self.switches + ("h2",)
        self.edges = [[left, right] for left, right, _params in self.link_definitions]

    @property
    def candidate_count(self):
        return len(self.candidate_links)

    def link_endpoints(self, link):
        if link not in self.candidate_links:
            raise ValueError("Not an inter-switch candidate link: %r" % (link,))
        left, right = link.split("-")
        return left, right

    def remote_switches(self, link):
        left, right = self.link_endpoints(link)
        return tuple(s for s in self.switches if s not in (left, right))
```

**A.2 Topology-aware heuristic ranker (`evaluate_topology_loeo.py`, excerpt)**

```python
def rank_topology(scores, exp_id, threshold, topology, link_ports):
    """Rank every candidate link; returns the evidence table with rank components exposed."""
    exp = scores[(scores["experiment_id"] == exp_id) & (scores["phase"] == "fault")].copy()
    start = exp["timestamp"].min()
    exp = exp[exp["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)].copy()
    evidence = {}
    for link in topology.candidate_links:
        endpoints = link_ports[link]
        endpoint_means, onset = [], []
        for switch, port in endpoints:
            rows = exp[(exp["switch"] == switch) & (exp["port"] == port)]
            endpoint_means.append(float(rows["anomaly_score"].mean()))
            crossed = rows[rows["anomaly_score"] > threshold]
            onset.append(float((crossed["timestamp"].min() - start).total_seconds())
                         if not crossed.empty else None)
        joint = min(endpoint_means)
        imbalance = abs(endpoint_means[0] - endpoint_means[1])
        pair_onset = max(onset) if all(x is not None for x in onset) else 999.0
        remote_onsets = []
        for switch in topology.remote_switches(link):
            rows = exp[exp["switch"] == switch]
            crossed = rows[rows["anomaly_score"] > threshold]
            remote_onsets.append(float((crossed["timestamp"].min() - start).total_seconds())
                                 if not crossed.empty else EARLY_SECONDS + 1.0)
        remote_onset = min(remote_onsets) if remote_onsets else EARLY_SECONDS + 1.0
        margin = remote_onset - pair_onset if pair_onset < 999.0 else -EARLY_SECONDS
        evidence[link] = {
            "link_anomaly": joint,
            "endpoint_imbalance": imbalance,
            "pair_onset_seconds": pair_onset,
            "propagation_margin_seconds": margin,
        }
    table = pd.DataFrame.from_dict(evidence, orient="index")
    utilities = []
    for metric, ascending in RANK_COMPONENTS:
        ranks = table[metric].rank(method="average", ascending=ascending)
        utility = (len(table) + 1.0 - ranks) / len(table)
        utilities.append(utility)
    table["rank_score"] = pd.concat(utilities, axis=1).mean(axis=1)
    return table.sort_values("rank_score", ascending=False, kind="mergesort")
```

**A.3 Neural models (`graph_temporal_topology.py`, excerpt)**

```python
class GraphEncoder(nn.Module):
    def __init__(self, input_dim, hidden=HIDDEN, embedding=EMBEDDING):
        super().__init__()
        self.conv1 = GCNConv(input_dim, hidden)
        self.conv2 = GCNConv(hidden, embedding)

    def forward(self, graph):
        x = torch.relu(self.conv1(graph["x"], graph["edge_index"]))
        x = torch.relu(self.conv2(x, graph["edge_index"]))
        return x.reshape(-1)


class GraphOnly(nn.Module):                      # GCN
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.head = nn.Linear(num_nodes * EMBEDDING, classes)

    def forward(self, sequence):
        representation = torch.stack([self.encoder(g) for g in sequence]).mean(dim=0)
        return self.head(representation)


class TemporalOnly(nn.Module):                   # LSTM
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.lstm = nn.LSTM(num_nodes * input_dim, LSTM_HIDDEN, batch_first=True)
        self.head = nn.Linear(LSTM_HIDDEN, classes)

    def forward(self, sequence):
        values = torch.stack([g["x"].reshape(-1) for g in sequence]).unsqueeze(0)
        output, _ = self.lstm(values)
        return self.head(output[:, -1, :]).squeeze(0)


class GraphTemporal(nn.Module):                  # GCN+LSTM
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.lstm = nn.LSTM(num_nodes * EMBEDDING, LSTM_HIDDEN, batch_first=True)
        self.head = nn.Linear(LSTM_HIDDEN, classes)

    def forward(self, sequence):
        embeddings = torch.stack([self.encoder(g) for g in sequence]).unsqueeze(0)
        output, _ = self.lstm(embeddings)
        return self.head(output[:, -1, :]).squeeze(0)


def score_ranking(scores, actual, links):
    ranked = sorted(range(len(links)), key=lambda idx: (-float(scores[idx]), links[idx]))
    return ranked, ranked.index(actual) + 1
```

**A.4 Grouped leave-one-experiment-out splits and Wilson interval (`evaluate_topology_loeo.py`, excerpt)**

```python
def ordered_grouped_splits(experiment_ids):
    ids = sorted(map(int, experiment_ids))
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("LOEO requires at least two unique experiment IDs")
    for held_out in ids:
        train = tuple(x for x in ids if x != held_out)
        if held_out in train or set(train) | {held_out} != set(ids):
            raise AssertionError("Experiment leakage in grouped split")
        yield held_out, train


def wilson_interval(successes, total, z=1.959963984540054):
    if total <= 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]
```
