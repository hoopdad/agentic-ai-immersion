# Lab 9: Tracing and evaluation

Measure the existing concierge once and preserve its responses/scores for release
gating. This folder contains only Lab 9.

## Prerequisites

Complete [Lab 6](../lab06/README.md). Lab 8 packets are optional metadata, not
evaluation input. Use the approved model-judge configuration and telemetry
resource; model calls and judges consume quota and incur charges.

Open [Lab 9](lab09_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
The target is Lab 6's shared concierge, not the multi-agent triage product.

## Tracing prerequisites

The local/deployed publisher selected by `DefaultAzureCredential` needs
**Monitoring Metrics Publisher**. Owner alone does not grant
`Microsoft.Insights/Telemetry/Write`. Confirm the complete connection string,
project connection and approved private DNS/network/AMPLS path.
See [setup tracing prerequisites](../../SETUP.md#lab-9-tracing-prerequisites).

## Notebook path and YOUR TURN

1. Inspect the shared [operating implementation](../../shared/operate-hosted-agents/lab5_operate.py).
2. Measure the six-question baseline with model-judged quality and deterministic
   recommendation/PII/forbidden-phrase checks.
3. Trace one question separately, flush the exporter and retain correlation
   evidence without replacing the original baseline.
4. Locate the newly printed trace ID in the matching Application Insights
   resource, inspect the slowest child span and publish the handoff.

In Application Insights Logs, use the notebook's run-specific query. Question
spans are `dependencies` named `marketplace.golden_question`; correlate requests
and dependencies by the exact `operation_Id`. Allow ingestion delay, and do not
apply deployed-agent filters to a local run. Restart the kernel after telemetry
configuration changes because providers are process-wide.

## Checkpoint

`../artifacts/lab5/part_a.json`, `evaluation_bundle.json`, `eval_results.jsonl`,
`eval_report.md`, `trace_evidence.json` and `pipeline.md` retain measured evidence.
A local tracing PASS does not prove Azure ingestion. Judge scores are uncertain
evidence, not regulatory certification or measured cost per successful outcome.

[Lab 10](../lab10/README.md) consumes these exact responses/scores without
calling the judges again.

## Authoring

Edit `lab09_tracing_evaluation.py` and regenerate `lab09_walkthrough.ipynb`.
