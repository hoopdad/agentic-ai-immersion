# Lab 5: Operate hosted agents

| | |
|---|---|
| Goal | Trace, evaluate, gate, inspect versions, promote and roll back with explicit release ownership |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab3/hosted.json`, `knowledge.json`; optional Lab 4 metadata |
| Notebook | `lab5_walkthrough.ipynb` |
| Produces | `artifacts/lab5/operate.json`, `eval_results.jsonl`, `eval_report.md`, `gate_result.json`, `pipeline.md`, `promotions.jsonl` |

Open this walkthrough with the dev-container `/usr/local/bin/python` kernel.
Use its editable evaluation inputs and run cells in order. The target is the
Lab 3 concierge product, started locally by the notebook or invoked as an active
Foundry version. Internal `lab5_operate.py`, `eval_gate.py` and `promote.py`
support the notebook/CI implementation, not alternate learner commands.

## Tracing prerequisites

Confirm **Monitoring Metrics Publisher** for the identity selected locally by
`DefaultAzureCredential` and for the deployed agent when tracing its container.
**Owner alone is insufficient**: ingestion requires the data-plane
`Microsoft.Insights/Telemetry/Write` action. The shared permission script does
not assign this role.

Use the complete approved connection string in notebook configuration. Ensure
Application Insights is connected to the project; private ingestion also
requires the approved network path, DNS and Azure Monitor Private Link Scope.
Do not open public ingestion to bypass a failure.

See [setup tracing prerequisites](../../SETUP.md#lab-5-tracing-prerequisites).

## What you'll learn and technical features

| Feature | Implementation | Engineering decision |
|---|---|---|
| Container tracing | `configure_azure_monitor` and Agent Framework instrumentation | Observe the product that ships, not a separate twin |
| Question spans | OpenTelemetry `marketplace.golden_question` | Correlate one question across notebook and product runtimes |
| Quality judges | Groundedness/Relevance with Entra model configuration | Use model scores as evidence with quota and grading uncertainty |
| Policy evaluators | NoRecommendation, PiiLeak and MustNot | Licensing/privacy sample checks are deterministic pass/fail |
| Fail-closed gate | `eval_gate.py` | Recompute safety from response text; reject malformed or incomplete evidence |
| Version operations | Notebook-managed azd and portal inspection | Promotion/rollback need explicit target and human approval |
| Optional cloud pipeline | Nested `.github/workflows/agent-ci.yml` | OIDC and protected environments, not an automatically active workflow |
| Generated runbook | YAML-derived `pipeline.md` | Compare operating instructions with their source |

## Teach (10 min)

Foundry manages runtime, identity and versions; engineers still own observation,
acceptance criteria and release discipline. Local evaluators can exercise the
actual HTTP product; optional platform evaluations provide portal-visible history
when the selected hosted target is supported.

The gate recomputes deterministic rules from responses instead of trusting
saved labels. One safety violation or malformed row fails closed. Model-judged
Groundedness/Relevance may warn or fail under stricter notebook settings.
PASS means these sample checks passed, not complete factual/privacy/regulatory safety.

Promotion uses the same reviewed product with explicit target settings.
Rollback must not be assumed to preserve history: Lab 3 requires accessible
shared Blob history for replica/version continuity. Container-local files
only establish local restart continuity.

Never enable sensitive prompt capture outside an approved development setting.
Recorded latency makes execution visible; this report does not calculate tokens,
dollar cost or cost per successful outcome. Missing usage/pricing is unknown,
not zero.

## Demo (10 min)

1. Run a small notebook evaluation and inspect model, citation and policy results.
2. Open `artifacts/lab5/eval_report.md`, including the lowest-quality rows and violations.
3. Run the notebook gate and inspect `gate_result.json`; review promotion output
   without approving a cloud action.
4. Find the newly printed operation ID in the correct Application Insights resource.
5. Compare the nested pipeline YAML with generated `pipeline.md` and identify
   the points where a reviewer or failed gate can stop release.

## Do (35 min)

1. Run the small deterministic evaluation cells. Require zero recommendation,
   PII and forbidden-phrase violations and inspect the citation evidence.
2. Run all 18 golden questions with judges. Compare low scores with their
   source facts and state one improvement against the unchanged acceptance gate.
3. Run the release-gate cells. Inspect target-specific promotion settings and
   approval requirements before executing any deployment action.
4. **YOUR TURN: stricter gate.** Run its notebook gate to prove a forbidden phrase
   fails and a safe answer passes.
5. **YOUR TURN: break it.** Temporarily add a recommendation instruction to Lab 3
   `hosted/main.py`, run the local failure gate, then revert and retest.
6. **YOUR TURN: trace one question.** Run the tracing cell, inspect its trace ID,
   allow ingestion delay and locate the slowest child span in Azure.
7. Optional: evaluate an active deployed version through the notebook after
   applying the telemetry configuration through its deployment action.
8. Optional: run the notebook's platform evaluation if the target/preview is available.

## Checkpoint (5 min)

Share the evaluation summary and gate line. Keep `eval_report.md` and
`gate_result.json` as the accepted baseline. Retain changed instructions,
knowledge or workflows only after passing the required checks. Stretch 6 does
not depend on the report, but promotion requires a passing gate.

## Finding the current trace

Open **Azure Portal > the Application Insights resource matching the configured
connection string > Logs**. Allow 2–5 minutes and select KQL mode.

This query finds recent evaluation-question dependency spans.

```kusto
dependencies
| where timestamp > ago(1h)
| where name == "marketplace.golden_question"
| project timestamp, name, operation_Id, duration, customDimensions
| order by timestamp desc
```

Match the printed operation ID, also saved as `trace_id` in `eval_results.jsonl`.
The notebook prints a run-specific query; replace the placeholder below with
that exact value when inspecting related spans.

This query correlates requests and dependencies belonging to the selected trace.

```kusto
union requests, dependencies
| where timestamp > ago(1h)
| where operation_Id == "<printed-trace-id>"
| project timestamp, name, duration, id, operation_ParentId, customDimensions
| order by timestamp asc
```

The question span lives in `dependencies`, not `traces`. A local run is not a
deployed invocation: remove deployed-agent filters. Setting a connection string
does not itself connect Application Insights to Foundry's Tracing view.
Restart the kernel after telemetry configuration changes because providers
are process-wide.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No new trace | Confirm destination/time range and inspect notebook exporter messages plus `artifacts/lab3/hosted_local.log` |
| Old records but exporter 403 | Verify current local/deployed publisher role, then authentication/network rules; restart and rerun after propagation |
| Local spans only | Pass the complete telemetry setting through notebook deployment and inspect the active version |
| DNS/live-metrics failure | Use the full resource connection string and approved DNS/network path, not invented hostnames |
| Flush timeout | Evaluation evidence may exist, but tracing did not pass; inspect authorization/network errors |
| Judge 401/403 | Check model endpoint, calling identity and Cognitive Services OpenAI User access |
| Judge score missing | Check deployment name/quota and inspect the saved error rather than interpreting it as zero |
| Product startup failure | Revisit Lab 3's preparation/authentication cells and read its local log |
| Gate failure or malformed row | Repair the behavior/evidence and rerun notebook evaluation and gate cells; do not promote partial results |
| Promotion placeholders | Supply approved target-specific values in the notebook; never deploy the example configuration |
| Pipeline OIDC failure | Administrator verifies federated credential subject and protected environment |

## Internal CI and release administration

The root offline workflow checks notebook/source alignment and regressions,
without deploying Azure. The nested cloud workflow here is an opt-in template:
an authorized release administrator reviews it, configures OIDC/protected
environments and explicitly installs it at repository scope. Cloud evaluations
remain manual dispatch.

Promotion implementation rechecks the gate, validates target settings, deploys,
smoke-tests and only then tags success. Target values are explicit subprocess
inputs; root/workshop `.env` files are not overwritten. This is internal
release tooling, not an additional learner command route. See
[`infra/README.md`](infra/README.md) for release-administrator context.

## References

- [Azure agent learning path](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/)
- [Agent Framework observability](https://learn.microsoft.com/agent-framework/user-guide/observability)
- [Azure AI Evaluation](https://learn.microsoft.com/python/api/azure-ai-evaluation/)
