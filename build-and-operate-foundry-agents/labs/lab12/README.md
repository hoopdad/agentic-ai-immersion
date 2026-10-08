# Lab 12: Microsoft Agent Framework workflows and hosted delegation

Build a readable Python graph over Lab 11's existing prompt agents, then run
that same graph inside the Lab 6 concierge. This folder contains only optional Lab 12.

## Prerequisites

Complete [Lab 11](../lab11/README.md) and retain its validated prompt names and
versions. The root dependency lock already includes MAF; no extra installation,
model deployment, YAML workflow or Foundry workflow-agent enablement is needed.
Keep the existing project/knowledge access. The hosted concierge's identity
needs Azure AI User on the project to invoke the prompt agents.

Open [Lab 12](lab12_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Graph construction is local; prompt-agent turns and hosted deployment call
Azure and may incur charges.

## Notebook path and YOUR TURN

1. Restore Lab 11's references without publishing any agent version.
2. Inspect `TriageCase`, the `@executor` steps and conditional `WorkflowBuilder`
   edges in [triage_workflow.py](../../shared/prompt-agents-and-workflows/triage_workflow.py).
   `ctx.send_message` forwards work; only handoff uses `ctx.yield_output`.
3. Run S1 and require `triage -> marketplace -> compliance -> handoff`, no
   accounts branch, and one validated advisor packet. An accounts case takes
   the accounts branch; a both-area case visits marketplace then accounts
   sequentially. Labs 7-8 already teach parallel fan-out/fan-in.
4. Send an intentionally wrong routing hint. Explain why a valid packet with
   unresolved marketplace questions is still a failed business outcome.
5. Paste the marked async tool and handoff instruction from the
   [delegation snippet](../../shared/prompt-agents-and-workflows/hosted_tool_snippet.py)
   into the [shared concierge](../../shared/hosted-knowledge-sessions/hosted/main.py).
   Register `run_triage_workflow` in `FUNCTION_TOOLS`.
6. Package and test the actual saved tool, then explicitly deploy the existing
   concierge package. Do not create another hosted service.

MAF owns orchestration in the notebook, then inside the concierge container.
`FoundryAgent` pins each Lab 11 version: Foundry still owns its instructions,
model and knowledge tool. Matching Python function implementations run locally
through MAF if requested; pre-fetched case facts avoid unnecessary calls.
Cases are one-shot with `store=False`; this lab does not teach workflow resume
or durable workflow checkpoints. Advisor approval/recovery remains in Lab 8.

## Checkpoint

`../artifacts/stretch6/part_b.json`, `agents.json`, `source_evidence.json` and the
S1 handoff packet preserve the prompt references and accepted graph/delegation.
The packaged `triage_workflow.py` and `triage_agents.json` are generated copies,
not new source files to edit or commit. After source changes, restart the kernel
and repeat the Lab 12 gates; after prompt changes, repeat Labs 11-12.
Legacy `workflow.yaml` and workflow-agent references are no longer used.

A local tool PASS and completed deployment commands do not establish deployed
end-to-end readiness; inspect the deployed concierge's invocation and identity
access before claiming that outcome. [Lab 13](../lab13/README.md) remains a
separate optional branch that needs only Lab 2.

## References and authoring

[MAF workflow concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/?pivots=programming-language-python),
[executors](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/executors?pivots=programming-language-python),
[builder and execution](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/builder-and-execution?pivots=programming-language-python),
and [FoundryAgent](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/foundry?pivots=programming-language-python).

Edit `lab12_workflows_delegation.py` and regenerate `lab12_walkthrough.ipynb`.
The authoring source uses notebook top-level `await`; it is not a terminal driver.
