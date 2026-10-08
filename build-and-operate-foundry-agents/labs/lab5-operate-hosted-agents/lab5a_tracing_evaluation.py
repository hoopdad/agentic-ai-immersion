# %% [markdown]
# # Lab 5A: Tracing and evaluation evidence
#
# Evaluate the knowledge-enabled agent, trace one question, and retain the measured baseline for release decisions.
# A trace ID proves local instrumentation/export, not Azure ingestion; verify the same ID in Application Insights.
# Lab 5B consumes these exact responses and scores without calling the model judges again.
# These cells call Azure models and judges and may incur charges.
#
# This cell loads evaluation and tracing definitions without executing the original notebook's operating exercises.
# %% Step 5.1 - Load evaluation helpers
from pathlib import Path
import json
import math
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab5-operate-hosted-agents/lab5a_tracing_evaluation.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab5-operate-hosted-agents/lab5a_tracing_evaluation.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("lab5-operate-hosted-agents/lab5_operate.py")

if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)

# %% [markdown]
# This cell evaluates six baseline questions and retains their original responses and model-judge scores for release gating.
# %% Step 5.2 - Measure the baseline
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
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

# %% [markdown]
# This cell traces one question, flushes the local exporter, and preserves its correlation evidence separately from the baseline.
# %% Step 5.3 - Trace one question end to end
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
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

# %% [markdown]
# This cell saves the serializable operating bundle and checked evaluation artifacts for a fresh Lab 5B kernel.
# %% Step 5.4 - Save the evaluation handoff
if "__file__" not in globals():
    lab_helpers.artifact_path("lab5", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("lab5", "part_b.json").unlink(missing_ok=True)
    durable_bundle = {key: bundle[key] for key in ("info", "hosted", "knowledge")}
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("lab5", "evaluation_bundle.json"), durable_bundle)
    part_a = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("lab5", "part_a.json"), lab="lab5", part="a", context=notebook_parts.scope(driver.ENV),
        state={"bundle": durable_bundle, "summary": baseline_summary},
        evidence=[
            results_path, lab_helpers.artifact_path("lab5", "eval_report.md"),
            lab_helpers.artifact_path("lab5", "evaluation_bundle.json"),
            lab_helpers.artifact_path("lab5", "trace_evidence.json"),
        ],
    )
