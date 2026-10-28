"""Offline tests for the dashboard backend.

Run from the repository root:
    .\\venv\\Scripts\\python.exe -m unittest discover -s dashboard\\backend\\tests -v

No test contacts the VM: SSH is replaced by fakes. Tests that read saved
artifacts use the repository's real result files.
"""

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "dashboard" / "backend"
for path in (str(ROOT), str(BACKEND)):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi import HTTPException  # noqa: E402

from sdn_dashboard import api, config, inference, runs, saved_results, vm  # noqa: E402
from sdn_dashboard.telemetry_parse import parse_phase_events, parse_telemetry  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


class TelemetryParsingTests(unittest.TestCase):
    def test_parses_real_run_and_phases(self):
        run_dir = ROOT / "raw_evidence" / "topology_12_switches" / "physical_1244_logical_244"
        events, fault_link = parse_phase_events((run_dir / "phase_events.csv").read_text(encoding="utf-8"))
        self.assertEqual(set(events), {"normal", "fault", "recovery"})
        self.assertEqual(fault_link, "s11-s12")
        parsed = parse_telemetry((run_dir / "telemetry.csv").read_text(encoding="utf-8"), events)
        self.assertTrue(parsed["schema_ok"])
        self.assertEqual(parsed["skipped"], 0)
        self.assertEqual(parsed["rows"], 1728)
        self.assertEqual(parsed["switches"], ["s%d" % i for i in range(1, 13)])
        phases = {entry["phase"] for entry in parsed["series"]}
        self.assertEqual(phases, {"normal", "fault", "recovery"})
        self.assertNotIn("s1.LOCAL", json.dumps(parsed["series"][0]))

    def test_partial_last_line_and_bad_values_are_skipped_not_invented(self):
        run_dir = ROOT / "raw_evidence" / "topology_12_switches" / "physical_1244_logical_244"
        lines = (run_dir / "telemetry.csv").read_text(encoding="utf-8").splitlines()
        text = "\n".join(lines[:40]) + "\n" + lines[40][: len(lines[40]) // 2]  # torn write
        parsed = parse_telemetry(text, {})
        self.assertEqual(parsed["rows"] + parsed["skipped"], 40)
        self.assertGreaterEqual(parsed["skipped"], 1)
        text = "\n".join(lines[:3]) + "\n" + lines[3].replace(",0.0,0.0,0.0,0.0,", ",nan,x,0.0,0.0,")
        parsed = parse_telemetry(text, {})
        self.assertEqual(parsed["skipped"], 1)

    def test_empty_and_wrong_schema(self):
        self.assertEqual(parse_telemetry(None)["rows"], 0)
        parsed = parse_telemetry("a,b,c\n1,2,3\n")
        self.assertFalse(parsed["schema_ok"])
        self.assertEqual(parsed["rows"], 0)


class ValidationTests(unittest.TestCase):
    def test_registered_pairs_only(self):
        entry = runs.validate_ids(12, 248, 1248)
        self.assertEqual(entry["fault_link"], "s4-s5")
        with self.assertRaises(ValueError):
            runs.validate_ids(12, 248, 1249)
        with self.assertRaises(ValueError):
            runs.validate_ids(12, 999, 1999)
        with self.assertRaises(ValueError):
            runs.validate_ids(4, 1, 1)  # exhausted four-switch registry
        with self.assertRaises(ValueError):
            runs.validate_ids(6, 1, 1)

    def test_api_rejects_bad_inputs(self):
        with self.assertRaises(HTTPException) as ctx:
            api.topology(switches=5)
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            api.run_status(12, 248, 9999, False, False)
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            api.run_inference(12, 248, 1248, api.InferenceRequest(methods=["not_a_model"]))
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            api.xai_experiment(12, 104)  # 8-switch example must not be served as a 12-switch one
        self.assertEqual(ctx.exception.status_code, 404)

    def test_remote_paths_are_built_from_integers_only(self):
        self.assertTrue(vm.remote_run_dir(12, 248, 1248).endswith("/topology_12_switches/physical_1248_logical_248"))
        with self.assertRaises(ValueError):
            vm.remote_run_dir(12, "248; rm -rf /", 1248)
        with self.assertRaises(ValueError):
            vm.read_log("/etc/passwd")


class ControlSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._active = runs._ACTIVE_PATH
        runs._ACTIVE_PATH = Path(self.tmp.name) / "active_run.json"
        self._state_dir = config.STATE_DIR
        config.STATE_DIR = Path(self.tmp.name)
        vm.invalidate_cache()

    def tearDown(self):
        runs._ACTIVE_PATH = self._active
        config.STATE_DIR = self._state_dir
        self.tmp.cleanup()

    def test_preflight_never_passes_run_flag(self):
        commands = []

        def fake_run_remote(command, timeout=None, binary=False):
            commands.append(command)
            if "--logical-id" in command:
                return FakeCompleted(stdout=json.dumps({"fault_link": "s5-s6", "output_dir": "/x"}) + "\nPreflight only: no files created\n")
            return FakeCompleted(stdout="__HOST__ vm\n__SUDO__ ok\n__CTRL__ 0.0.0.0:6633\n__OVS__ \n__OVSRC__ ok\n__MN__ ok\n__IPERF__ ok\n__BUSY__ 0\n__RUNNER__ abc\n__NTP__ no\n__DATE__ now\n")

        with mock.patch.object(vm, "run_remote", fake_run_remote), mock.patch.object(vm, "key_available", return_value=True):
            result = runs.preflight(12, 249, 1249)
        self.assertTrue(result["ready"], result["blockers"])
        self.assertFalse(result["mutates_environment"])
        runner_commands = [c for c in commands if "--logical-id" in c]
        self.assertEqual(len(runner_commands), 1)
        self.assertNotIn("--run", runner_commands[0])
        self.assertNotIn("nohup", runner_commands[0])
        self.assertNotIn("--verify-topology", runner_commands[0])

    def test_start_requires_confirmation(self):
        with self.assertRaises(ValueError):
            runs.start(12, 249, 1249, confirmed=False)
        with self.assertRaises(HTTPException) as ctx:
            api.start(api.RunRequest(switches=12, logical_id=249, physical_id=1249, confirm=False))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_conflicting_start_is_rejected(self):
        runs._save_active({"name": "physical_1249_logical_249", "switch_count": 12})
        with mock.patch.object(vm, "run_remote") as remote:
            with self.assertRaises(runs.RunConflict):
                runs.start(12, 250, 1250, confirmed=True)
            remote.assert_not_called()
        with self.assertRaises(HTTPException) as ctx:
            api.start(api.RunRequest(switches=12, logical_id=250, physical_id=1250, confirm=True))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_start_is_blocked_by_preflight_blockers(self):
        def fake_run_remote(command, timeout=None, binary=False):
            if "--logical-id" in command:
                return FakeCompleted(stdout="", stderr="FileExistsError: Refusing to reuse run directory", returncode=1)
            return FakeCompleted(stdout="__HOST__ vm\n__SUDO__ ok\n__CTRL__ 0.0.0.0:6633\n__OVS__ s1 s2\n__BUSY__ 1\n__RUNNER__ abc\n")

        with mock.patch.object(vm, "run_remote", fake_run_remote), mock.patch.object(vm, "key_available", return_value=True):
            with self.assertRaises(runs.RunConflict) as ctx:
                runs.start(12, 248, 1248, confirmed=True)
        message = str(ctx.exception)
        self.assertIn("Refusing to reuse run directory", message)
        self.assertIn("OVS bridges already exist", message)
        self.assertIsNone(runs.active_run())

    def test_launch_command_backgrounds_only_the_runner(self):
        """Regression: 'a && b && runner &' backgrounds the whole list as a subshell
        that keeps the SSH channel open until the run ends (observed on 249/1249)."""
        commands = []

        def fake_run_remote(command, timeout=None, binary=False):
            commands.append(command)
            return FakeCompleted(stdout="__PID__ 4242\n")

        with mock.patch.object(vm, "run_remote", fake_run_remote), mock.patch.object(vm, "key_available", return_value=True):
            launched = vm.start_run(12, 250, 1250)
        self.assertEqual(launched["remote_pid"], 4242)
        command = commands[0]
        background_segment = command.split(" & echo __PID__")[0].rsplit(";", 1)[-1].strip()
        self.assertTrue(background_segment.startswith("sudo -n nohup python3 -B experiment_runner_recollection.py"), background_segment)
        self.assertNotIn("&&", command.split("sudo -n nohup")[0].rsplit(";", 1)[-1])
        self.assertIn("--run > ", command)
        self.assertIn("2>&1 < /dev/null &", command)

    def test_control_token_enforced_when_configured(self):
        with mock.patch.object(config, "CONTROL_TOKEN", "secret"):
            with self.assertRaises(HTTPException) as ctx:
                api.require_token(x_dashboard_token=None)
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertTrue(api.require_token(x_dashboard_token="secret"))


class FailureStateTests(unittest.TestCase):
    def setUp(self):
        vm.invalidate_cache()

    def test_ssh_failure_surfaces_as_vm_error_and_health_disconnected(self):
        def refused(*args, **kwargs):
            return FakeCompleted(stdout="", stderr="ssh: connect to host 127.0.0.1 port 2222: Connection refused", returncode=255)

        with mock.patch.object(subprocess, "run", refused), mock.patch.object(vm, "key_available", return_value=True):
            with self.assertRaises(vm.VMError):
                vm.probe()
            health = api.health()
        self.assertEqual(health["ssh"]["status"], "Disconnected")
        self.assertEqual(health["controller"]["status"], "Not Tested")
        self.assertEqual(health["mininet_ovs"]["status"], "Not Tested")

    def test_missing_controller_reported_as_disconnected(self):
        def fake_run_remote(command, timeout=None, binary=False):
            return FakeCompleted(stdout="__HOST__ vm\n__PY__ Python 3.8.5\n__SUDO__ ok\n__CTRL__ \n__RYU__ \n__OVS__ \n__OVSRC__ ok\n__MN__ ok\n__IPERF__ ok\n__BUSY__ 0\n__RUNNER__ abc\n__NTP__ no\n__DATE__ t\n")

        with mock.patch.object(vm, "run_remote", fake_run_remote), mock.patch.object(vm, "key_available", return_value=True):
            health = api.health()
            probe = vm.probe()
        self.assertFalse(probe["controller_listening"])
        self.assertEqual(health["controller"]["status"], "Disconnected")
        self.assertEqual(health["ssh"]["status"], "Connected")

    def test_timeout_is_a_vm_error(self):
        def slow(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="ssh", timeout=1)

        with mock.patch.object(subprocess, "run", slow), mock.patch.object(vm, "key_available", return_value=True):
            with self.assertRaises(vm.VMError):
                vm.run_remote("true", timeout=1)

    def test_status_for_missing_run_dir_is_not_started(self):
        with mock.patch.object(vm, "read_run_files", return_value={"_exists": False, "_now": None, "_pids": []}):
            status = runs.status(12, 249, 1249)
        self.assertEqual(status["state"], "not_started")
        self.assertFalse(status["run_dir_exists"])


class SshSerialisationTests(unittest.TestCase):
    def test_remote_commands_never_overlap(self):
        """Concurrent ssh sessions stalled on this host; run_remote must serialise them."""
        import threading
        active, peak = [0], [0]
        guard = threading.Lock()

        def fake_run(*args, **kwargs):
            with guard:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            import time as _t
            _t.sleep(0.05)
            with guard:
                active[0] -= 1
            return FakeCompleted(stdout="ok")

        with mock.patch.object(subprocess, "run", fake_run), mock.patch.object(vm, "key_available", return_value=True):
            threads = [threading.Thread(target=vm.run_remote, args=("true",)) for _ in range(8)]
            [t.start() for t in threads]
            [t.join() for t in threads]
        self.assertEqual(peak[0], 1)

    def test_probe_is_cached_briefly_and_invalidated(self):
        calls = []

        def fake_run_remote(command, timeout=None, binary=False):
            calls.append(command)
            return FakeCompleted(stdout="__HOST__ vm\n__SUDO__ ok\n__CTRL__ x\n")

        vm.invalidate_cache()
        with mock.patch.object(vm, "run_remote", fake_run_remote), mock.patch.object(vm, "key_available", return_value=True):
            vm.probe(); vm.probe()
            self.assertEqual(len(calls), 1)
            vm.invalidate_cache()
            vm.probe()
            self.assertEqual(len(calls), 2)
        vm.invalidate_cache()


class SavedResultTests(unittest.TestCase):
    def test_comparison_matches_source_csv(self):
        rows = saved_results.comparison()["rows"]
        with (config.COMPARISON_DIR / "comparison_table.csv").open(encoding="utf-8-sig", newline="") as stream:
            source = list(csv.DictReader(stream))
        self.assertEqual(len(rows), len(source))
        self.assertEqual(len(rows), 15)
        by_key = {(r["switch_count"], r["method"]): r for r in rows}
        expected_counts = {(4, "graph_only"): (20, 23, 25), (8, "graph_only"): (23, 23, 24), (12, "graph_only"): (25, 26, 26),
                           (12, "rf_baseline"): (19, 21, 26), (8, "topology_link_ranker"): (1, 11, 24)}
        for key, (top1, top2, n) in expected_counts.items():
            self.assertEqual((by_key[key]["top1_count"], by_key[key]["top2_count"], by_key[key]["valid_experiments"]), (top1, top2, n))
        self.assertAlmostEqual(by_key[(12, "graph_only")]["mrr"], 0.9808, places=4)
        self.assertAlmostEqual(by_key[(12, "graph_only")]["chance_top1"], 1 / 11, places=3)

    def test_evaluation_counts_agree_with_comparison(self):
        comparison = {(r["switch_count"], r["method"]): r for r in saved_results.comparison()["rows"]}
        for switches in (4, 8, 12):
            evaluation = saved_results.evaluation(switches)
            for method, block in evaluation["methods"].items():
                self.assertEqual(block["top1_count"], comparison[(switches, method)]["top1_count"], (switches, method))
                self.assertEqual(block["support"], comparison[(switches, method)]["valid_experiments"])
            per_experiment = {e["experiment_id"]: e for e in evaluation["per_experiment"]}
            for exp, entry in per_experiment.items():
                for method, rec in entry["methods"].items():
                    self.assertEqual(sorted(rec["ranking"]), sorted(evaluation["candidate_links"]))
                    self.assertEqual(rec["top1_hit"], rec["ranking"][0] == entry["actual_link"])
                    if "train_experiment_ids" in rec:
                        self.assertNotIn(exp, rec["train_experiment_ids"])

    def test_xai_example_104_is_an_8_switch_report(self):
        report = saved_results.xai_experiment(8, 104)
        self.assertEqual(report["switch_count"], 8)
        rf = report["methods"]["rf_baseline"]
        self.assertEqual(rf["ground_truth"], "s4-s5")
        self.assertEqual(rf["ranking"][0], "s4-s5")
        self.assertEqual(len(rf["ranking"]), 7)
        self.assertNotIn(104, rf["fold"]["train_experiment_ids"])
        self.assertIn("experiment_104", report["source_json"])
        with self.assertRaises(FileNotFoundError):
            saved_results.xai_experiment(12, 104)
        index = {t["switch_count"]: t for t in saved_results.xai_index()}
        self.assertIn(104, index[8]["experiments"])
        self.assertNotIn(104, index[12]["experiments"])
        self.assertEqual(index[12]["validation"]["rf_baseline"]["validation_pass_count"], 26)

    def test_history_lists_saved_experiments(self):
        history = {h["switch_count"]: h for h in saved_results.history()}
        self.assertEqual(len(history[12]["experiments"]), 26)
        self.assertEqual(len(history[8]["experiments"]), 24)
        self.assertEqual(len(history[4]["experiments"]), 25)
        self.assertEqual(len(history[12]["excluded"]), 18)


class InferencePathTests(unittest.TestCase):
    def test_checkpoint_ensemble_reproduces_saved_heldout_score(self):
        """The saved fold-1 checkpoints must reproduce the saved mean-seed score of
        their own held-out experiment; this validates the live neural path."""
        import numpy as np
        import torch
        import graph_temporal_topology as neural
        from linear_topology import LinearTopology

        saved = config.SAVED_RESULTS[12]
        topology = LinearTopology(12)
        checkpoint_dir, fold, summary = inference._checkpoint_fold(12)
        self.assertEqual(fold, 1)
        examples, feature_names, payload = neural.prepare_examples(saved["graph"], topology)
        with (Path(saved["neural_eval_dir"]) / "mean_seed_ensemble_predictions.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = {(r["method"], int(r["experiment_id"])): r for r in csv.DictReader(stream)}
        for method in saved_results.NEURAL_METHODS:
            models, policy = [], None
            for seed in neural.SEEDS:
                path = next(checkpoint_dir.glob("%s_fold01_heldout*_seed%d.pt" % (method, seed)))
                model, ckpt = neural.load_checkpoint(path, topology)
                models.append(model)
                policy = ckpt
            held_out = int(policy["test_experiment_ids"][0])
            sequence = neural.normalize_sequence(examples[held_out]["sequence"], policy["input_features"],
                                                 np.asarray(policy["feature_means"], dtype=np.float32),
                                                 np.asarray(policy["feature_stds"], dtype=np.float32), topology)
            with torch.no_grad():
                scores = torch.stack([torch.softmax(m(sequence), dim=0) for m in models]).mean(dim=0).numpy()
            saved_scores = np.asarray(json.loads(rows[(method, held_out)]["mean_seed_scores_json"]))
            self.assertTrue(np.allclose(scores, saved_scores, atol=1e-5), (method, scores, saved_scores))

    def test_rf_refit_uses_only_saved_candidate_and_never_the_label(self):
        """RF features for the new run are built without its label: fold_inputs gets
        None for the held-out label and the training set is exactly the saved candidate."""
        import pandas as pd
        import evaluate_topology_loeo as rf_eval
        from linear_topology import LinearTopology

        topology, frame, labels, link_ports, basis, train_hash, dataset = inference._training_frame(12)
        self.assertEqual(len(labels), 26)
        provenance = json.loads((Path(config.SAVED_RESULTS[12]["candidate_dir"]) / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(train_hash, provenance["dataset_sha256"])
        # Synthetic held-out: relabel a copy of experiment 201 as 9001 with its label removed.
        new = frame[frame["experiment_id"] == 201].copy()
        new["experiment_id"] = 9001
        combined = pd.concat([frame, new], ignore_index=True)
        inputs = rf_eval.fold_inputs(combined, {**labels, 9001: None}, 9001, sorted(labels), topology, link_ports)
        self.assertEqual(inputs["train_ids"], sorted(labels))
        self.assertNotIn(9001, inputs["train_ids"])
        self.assertEqual(inputs["x_train"].shape, (26, 48))


class HistoricalDataGuardTests(unittest.TestCase):
    def test_saved_candidates_match_their_provenance_hashes(self):
        for switches in (8, 12):
            candidate_dir = Path(config.SAVED_RESULTS[switches]["candidate_dir"])
            provenance = json.loads((candidate_dir / "provenance.json").read_text(encoding="utf-8"))
            digest = hashlib.sha256((candidate_dir / "candidate_dataset.csv").read_bytes()).hexdigest()
            self.assertEqual(digest, provenance["dataset_sha256"], switches)
        v3 = config.FOUR_SWITCH_CANDIDATE / "candidate_dataset.csv"
        self.assertEqual(hashlib.sha256(v3.read_bytes()).hexdigest(),
                         "b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a")

    def test_dashboard_runs_are_outside_raw_evidence(self):
        self.assertFalse(str(config.DASHBOARD_RUNS_DIR).startswith(str(config.RAW_EVIDENCE_DIR)))
        self.assertEqual(config.DASHBOARD_RUNS_DIR.name, "dashboard_runs")
        self.assertTrue(str(runs.local_copy_path(12, 248, 1248)).startswith(str(config.DASHBOARD_RUNS_DIR)))


if __name__ == "__main__":
    unittest.main()
