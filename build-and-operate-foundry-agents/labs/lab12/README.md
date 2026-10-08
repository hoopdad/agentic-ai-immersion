# Lab 12: Workflows and hosted delegation

Reuse existing prompt agents, create a workflow and delegate from the existing
concierge product. This folder contains only optional Lab 12.

## Prerequisites

Complete [Lab 11](../lab11/README.md) and retain its validated prompt references.
The selected Foundry workflow surface is preview; confirm availability, identity
access and deployment prerequisites with the administrator.

Open [Lab 12](lab12_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Prompt agents are not republished, and the Lab 6 product is reused.

## Notebook path and YOUR TURN

1. Create only the workflow over Lab 11's published agent names.
2. Run S1 and require the `triage -> marketplace -> compliance -> handoff`
   action trail, no accounts branch, and a strict safe packet.
3. Exercise an incorrect routing hint; explain unresolved marketplace questions
   rather than calling incorrect execution successful.
4. Copy the marked function/instruction from the
   [delegation snippet](../../shared/prompt-agents-and-workflows/hosted_tool_snippet.py)
   into the [shared concierge](../../shared/hosted-knowledge-sessions/hosted/main.py).
   Register `run_triage_workflow` in `FUNCTION_TOOLS`.
5. Run the registration/delegation acceptance gate, then explicitly deploy the
   edited shared package through this notebook.

The caller pre-fetches authoritative case facts for the workflow. Inspect route,
packet, safety and cleanup errors, not just streamed action events.
Do not create a duplicate hosted package or copy credentials/state into it.

## Checkpoint

`../artifacts/stretch6/part_b.json`, `agents.json`, `workflow.yaml` and the S1
handoff packet preserve the workflow reference and accepted delegation.
Existing prompt references and Lab 6's knowledge remain reusable.

[Lab 13](../lab13/README.md) is a separate optional branch that needs only Lab 2.

## Authoring

Edit `lab12_workflows_delegation.py` and regenerate `lab12_walkthrough.ipynb`.
