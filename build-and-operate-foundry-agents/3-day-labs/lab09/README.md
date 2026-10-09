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

## Learning contract and recovery

- **Required:** Lab 6 scoped knowledge-concierge acceptance, prepared package and telemetry/model-judge access.
- **Recommended route:** core Labs 1-10 in order; next Lab 10. Lab 8 is not a runtime prerequisite.
- **Primary delta / lineage (branch):** measure the unchanged concierge, not triage or an extension.
  The default local evaluation pins actual runtime files, knowledge, questions, scope and model.
  Its deployed version reference does not mean that cloud version was evaluated.
- **Acceptance:** six complete measured scores and an exact new trace observed in the intended Azure
  resource. Step 9.4 requires `OBSERVED_TRACE_ID` and `OBSERVED_RESOURCE_ID` from Azure Logs;
  ingestion evidence is explicitly learner-observed, not an automatic query.
- **Handoff/recovery:** bundle/result fingerprints prevent mutation of measured evidence.
  Changed candidate requires Steps 9.2-9.4 again; missing predecessor requires Lab 6 restoration.
  Extensions use isolated candidate names/versions and retain core evidence. Busy port 8088 fails
  rather than adopting an unidentified process; stop only owned processes and review attendee cleanup.

## Authoring

Edit `lab09_tracing_evaluation.py` and regenerate `lab09_walkthrough.ipynb`.
