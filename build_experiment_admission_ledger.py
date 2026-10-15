"""Create an exclusive forensic ledger from candidate provenance and manifest."""

import argparse
import csv
import json
from pathlib import Path


FIELDS = (
    "logical_experiment_id", "physical_run_id", "raw_status", "derived_audit_status",
    "candidate_decision", "candidate_member", "evidence_path", "raw_artifact_sha256_json",
    "reason_or_uncertainty",
)


def build(candidate_dir, source_path, manifest_path, output_path):
    candidate_dir, source_path, manifest_path, output_path = map(
        Path, (candidate_dir, source_path, manifest_path, output_path)
    )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite ledger: {output_path}")
    provenance = json.loads((candidate_dir / "provenance.json").read_text(encoding="utf-8"))
    exclusions = {}
    with (candidate_dir / "exclusion_report.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            exclusions[int(row["experiment_id"])] = row
    manifest = {}
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            manifest[int(row["experiment_id"])] = row
    source_ids = set(map(int, provenance["input_candidate"]["ids"]))
    new_runs = provenance["recollected_runs"]
    included_ids = set(map(int, provenance["included_logical_experiments"]))
    rows = []
    for logical_id in sorted(set(range(1, 20))):
        if logical_id in source_ids:
            rows.append({
                "logical_experiment_id": logical_id, "physical_run_id": "",
                "raw_status": "not separately recorded in source candidate",
                "derived_audit_status": "VALID per historical audit manifest",
                "candidate_decision": "INCLUDED", "candidate_member": "true",
                "evidence_path": str(source_path), "raw_artifact_sha256_json": "",
                "reason_or_uncertainty": "Historical source rows retained; raw per-run artifacts are not included in this ledger input.",
            })
        else:
            reason = manifest.get(logical_id, {}).get("decision_reason", "Historical source excluded")
            rows.append({
                "logical_experiment_id": logical_id, "physical_run_id": "",
                "raw_status": "historical source excluded",
                "derived_audit_status": "INVALID historical evidence",
                "candidate_decision": "EXCLUDED", "candidate_member": "false",
                "evidence_path": str(manifest_path), "raw_artifact_sha256_json": "",
                "reason_or_uncertainty": reason,
            })
    for audit in new_runs:
        physical_id = int(audit["source_physical_run_id"])
        logical_id = int(audit["logical_experiment_id"])
        rows.append({
            "logical_experiment_id": logical_id, "physical_run_id": physical_id,
            "raw_status": audit["original_metadata_status"],
            "derived_audit_status": audit["admission_status"],
            "candidate_decision": "INCLUDED", "candidate_member": "true",
            "evidence_path": f"recollection_runs/physical_{physical_id}_logical_{logical_id}",
            "raw_artifact_sha256_json": json.dumps(audit["raw_artifact_sha256"], sort_keys=True),
            "reason_or_uncertainty": audit.get("forensic_reaudit", "") + "; " + audit.get("admission_basis", ""),
        })
    for physical_id, logical_id, status, audit_status, reason in (
        (20, 3, "FAILED_INVALID", "INVALID", "Invalid normal/sample timestamp ordering; excluded."),
        (22, 3, "COMPLETE", "PROVISIONAL / UNVERIFIED", "Metadata says COMPLETE, but trustworthy process-completion evidence is unavailable; excluded."),
    ):
        rows.append({
            "logical_experiment_id": logical_id, "physical_run_id": physical_id,
            "raw_status": status, "derived_audit_status": audit_status,
            "candidate_decision": "EXCLUDED", "candidate_member": "false",
            "evidence_path": "prior preserved run audit; physical-20 raw copy is not present in this Windows workspace" if physical_id == 20 else "run22_milestone_20261014T182846Z/inputs/physical_22_logical_3",
            "raw_artifact_sha256_json": json.dumps({
                "iperf_server.log": "7c59950ba12d8d606d7fed8e11f4eebfb4dee7b3e0ebe830852a3fb99fa86832",
                "iperf_client.log": "b623f65121a1d998cababa7e3255e7c2a8b7fdeebcf8e3a9a185517258c9ceff",
                "phase_events.csv": "3916e1f584a652068197113340a89bdf9b915053d828113291eb5861836dc45b",
                "run_metadata.json": "7557bf522da2bfb5fcaac2f4fb9a2ea61fa74609ec74efea8da41ff58698040f",
                "telemetry.csv": "9db74ae55dc1bbb52ced7a020227a82c14347a4fa1eddaa4536c57664fef4657",
                "runtime_port_mapping.csv": "ebfb86680cb1ac992cb4c45dceb70b6b7a9ea1222328991c5fb00e83d8a61dae",
            } if physical_id == 20 else {
                "iperf_server.log": "27a7bfe3bb806eea8117cefd988245c21cb346cf2c959401b783d9a78cf16597",
                "iperf_client.log": "83261df41a207b9f7b72f2d137c485c6bbae848ab95b8654470a1ff72d84a17c",
                "phase_events.csv": "b0fc142bb7a649c4de91083f7fad74f303e3e269f11be9a37cb346d130f4d8fd",
                "run_metadata.json": "78c1ab1fcdd752831e0c4b90e06cfd9a401e08ace5356d82f919a0d601005216",
                "telemetry.csv": "ff4961070701316ae476542a6d8424e8cf8cf145e192dfec68debe34c0bb497c",
                "runtime_port_mapping.csv": "ebfb86680cb1ac992cb4c45dceb70b6b7a9ea1222328991c5fb00e83d8a61dae",
            }, sort_keys=True),
            "reason_or_uncertainty": reason,
        })
    expected_members = {int(value) for value in provenance["included_logical_experiments"]}
    observed_members = {int(row["logical_experiment_id"]) for row in rows if row["candidate_member"] == "true"}
    if expected_members != observed_members or len(rows) != len({(r["logical_experiment_id"], r["physical_run_id"]) for r in rows}):
        raise ValueError("Ledger membership or evidence identity validation failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "candidate_member_logical_ids": sorted(observed_members), "path": str(output_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.candidate_dir, args.source, args.manifest, args.output), indent=2))


if __name__ == "__main__":
    main()
