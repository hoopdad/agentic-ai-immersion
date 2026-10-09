# %% [markdown]
# # Lab 9: Tracing and evaluation evidence
#
# **Prerequisites:** Lab 6 (Lab 8 packets are optional).
# **Required learning/artifacts:** scoped `lab3/part_b.json`, exact knowledge concierge package/configuration and telemetry access.
# **Recommended route:** core Labs 1-10 in order; teach tracing here before optional Lab 12 cross-service correlation.
# **Primary delta / lineage (branch):** measure the unchanged Lab 6 concierge, not triage or an extension candidate.
# **Acceptance and recovery:** complete six measured scores plus a new trace observed in the intended Azure resource.
# The default target is local product behavior; its deployed reference is not a claim of cloud-version evaluation.
# Save exact runtime, knowledge, question-set and bundle hashes. Edits require fresh evaluation, not a recycled PASS.
# Restore Lab 6 for prerequisite failures; rerun Steps 9.2-9.4 for a changed candidate. Stop the owned evaluation process.
#
# Evaluate the knowledge-enabled agent, trace one question, and retain the measured baseline for release decisions.
# A trace ID proves local instrumentation/export, not Azure ingestion; verify the same ID in Application Insights.
# Lab 10 consumes these exact responses and scores without calling the model judges again.
# These cells call Azure models and judges and may incur charges.
#
# This cell loads evaluation and tracing definitions without executing the original notebook's operating exercises.
# %% Step 9.1 - Load evaluation helpers
from pathlib import Path
import json
import hashlib
import math
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/3-day-labs/lab09/lab09_tracing_evaluation.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/3-day-labs/lab09/lab09_tracing_evaluation.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "3-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("operate-hosted-agents/lab5_operate.py")

if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted = {}
    trace_passed = False

# %% [markdown]
# This cell evaluates six baseline questions and retains their original responses and model-judge scores for release gating.
# %% Step 9.2 - Measure the baseline
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("baseline", None)
    bundle = driver.build(target="local", enable_tracing=False)
    baseline_summary = driver.demo(bundle, limit=6, target_mode="local")
    results_path = lab_helpers.artifact_path("lab5", "eval_results.jsonl")
    baseline_results = results_path.read_text(encoding="utf-8")
    baseline_report = lab_helpers.artifact_path("lab5", "eval_report.md").read_text(encoding="utf-8")
    assert baseline_summary["questions"] == 6
    baseline_rows = [json.loads(line) for line in baseline_results.splitlines() if line.strip()]
    assert len(baseline_rows) == 6 and all(
        isinstance(row["scores"].get(metric), (int, float))
        and not isinstance(row["scores"][metric], bool)
        and math.isfinite(row["scores"][metric])
        for row in baseline_rows for metric in ("groundedness", "relevance")
    ), "Baseline judge results are incomplete; resolve the recorded judge errors before continuing."
    accepted["baseline"] = True

# %% [markdown]
# This cell traces one question, flushes the local exporter, and preserves its correlation evidence separately from the baseline.
# %% Step 9.3 - Trace one question end to end
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    accepted.pop("tracing", None)
    trace_passed = False
    lab_helpers.artifact_path("lab5", "trace_evidence.json").unlink(missing_ok=True)
    assert accepted.get("baseline"), "Complete the current baseline before tracing."
    trace_bundle = driver.build(skip_judges=True, target="local")
    assert trace_bundle["tracing"].get("enabled"), "Configure APPLICATIONINSIGHTS_CONNECTION_STRING first."
    try:
        trace_summary = driver.demo(trace_bundle, limit=1, target_mode="local")
        assert trace_summary["questions"] == 1 and len(trace_summary["trace_ids"]) == 1
        trace_rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        driver.foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "trace_evidence.json"), {
            "summary": trace_summary, "rows": trace_rows, "ingestion_verified": False,
        })
    finally:
        results_path.write_text(baseline_results, encoding="utf-8")
        lab_helpers.artifact_path("lab5", "eval_report.md").write_text(baseline_report, encoding="utf-8")
        driver.foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "operate.json"), bundle["info"])
    print("Use the saved trace_id in Application Insights > Logs; ingestion is not asserted by this cell.")
    trace_passed = True
    accepted["tracing"] = True

# %% [markdown]
# This cell saves the serializable operating bundle and checked evaluation artifacts for a fresh Lab 10 kernel.
# First find this run's trace in the intended Azure resource and enter its ID and resource ID;
# this is a learner-observed ingestion check, not an automatic Azure query.
# %% Step 9.4 - Save the evaluation handoff
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    assert accepted.get("baseline") and accepted.get("tracing") and trace_passed, "Complete every current Lab 9 gate."
    OBSERVED_TRACE_ID = ""  # Paste the operation_Id found in Azure Logs for this run.
    OBSERVED_RESOURCE_ID = ""  # Paste the intended Application Insights Azure resource ID.
    assert OBSERVED_TRACE_ID in trace_summary["trace_ids"], "Find this run's exact trace ID in Azure Logs."
    assert "/providers/microsoft.insights/components/" in OBSERVED_RESOURCE_ID.lower(), (
        "Record the intended Application Insights resource, not a local exporter."
    )
    trace_evidence_path = lab_helpers.artifact_path("lab5", "trace_evidence.json")
    trace_evidence = json.loads(trace_evidence_path.read_text(encoding="utf-8"))
    trace_evidence.update(ingestion_verified=True, observed_trace_id=OBSERVED_TRACE_ID,
                          observed_resource_id=OBSERVED_RESOURCE_ID, verification="learner-observed Azure Logs")
    driver.foundry_env.save_artifact(trace_evidence_path, trace_evidence)
    driver.validate_evaluated_target(bundle["info"]["evaluated_target"], bundle["hosted"], bundle["knowledge"])
    durable_bundle = {key: bundle[key] for key in ("info", "hosted", "knowledge")}
    durable_bundle["results_sha256"] = hashlib.sha256(results_path.read_bytes()).hexdigest()
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "evaluation_bundle.json"), durable_bundle)
    bundle_sha256 = hashlib.sha256(
        lab_helpers.artifact_path("lab5", "evaluation_bundle.json").read_bytes()).hexdigest()
    part_a = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV),
        state={"bundle": durable_bundle, "bundle_sha256": bundle_sha256,
               "summary": baseline_summary, "accepted": accepted},
        evidence=[
            results_path, lab_helpers.artifact_path("lab5", "eval_report.md"),
            lab_helpers.artifact_path("lab5", "evaluation_bundle.json"),
            lab_helpers.artifact_path("lab5", "trace_evidence.json"),
        ],
    )
