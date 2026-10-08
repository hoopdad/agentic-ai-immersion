# Lab 7: Specialist orchestration

Build fan-out/fan-in, bounded compliance reflection and structured pending
advisor packets. This folder contains only Lab 7.

## Prerequisites

Complete [Lab 6](../lab6/README.md) and retain its hosted/knowledge checkpoint.
Model calls require the existing approved identity, deployments and network.

Open [Lab 7](lab7_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
This lab stops at `pending_advisor_approval`; it does not send advisor decisions.

## Product to inspect and edit

Use the shared [workflow](../../shared/hosted-multi-agent-handoff/hosted/marketplace_workflow.py),
[specialists](../../shared/hosted-multi-agent-handoff/hosted/marketplace_specialists.py)
and [host](../../shared/hosted-multi-agent-handoff/hosted/main.py).
Only the advisor coordinator emits final workflow output; specialist streaming
updates are intermediate, not completed packets.

## Notebook path and YOUR TURN

1. Run S1-S3 through intake, specialist fan-out, merge and compliance to pending approval.
2. Inspect marketplace/accounts/both routing and strict Pydantic packet fields.
3. Temporarily introduce a recommendation instruction. Require rejection and
   at most one revision; restore the safe instruction afterward.
4. Keep deterministic classification as fallback, add structured model
   classification and require accounts routing for the ambiguous card/drug case.
5. Save current intermediate evidence in Step 7.5.

More model calls do not establish lower cost or higher quality. Schema validity
does not prove factual accuracy. Unresolved compliance flags must remain visible
to the advisor rather than being relabeled as acceptance.

## Checkpoint

`../artifacts/lab4/part_a.json`, immutable pending-case/session snapshots,
classification/compliance evidence and `orchestration_sources.json` bind the
actually tested product/shared sources. Keep pending sessions for
[Lab 8](../lab8/README.md); do not repeat intake to restore state.

## Authoring

Edit `lab7_specialist_orchestration.py` and regenerate `lab7_walkthrough.ipynb`.
