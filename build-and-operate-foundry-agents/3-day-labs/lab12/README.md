# Lab 12: Hosted-to-hosted delegation

Add ONE authenticated network boundary, not another graph. A separate knowledge
concierge candidate calls the deployed Lab 8 triage service and relays pending
advisor approval. There are no Prompt Agents or manufactured advisor decisions.

## Prerequisites

BOTH [Lab 8](../lab08/README.md) and [Lab 9](../lab09/README.md) are required:
`lab4/part_b.json` supplies the deployed `triage_reference`;
`lab5/part_a.json` supplies immutable evaluation and tracing evidence.
Recommend finishing [Lab 10](../lab10/README.md) first.
Lab 11 is not required. Missing predecessors fail before cloud actions.
Open [lab12_walkthrough.ipynb](lab12_walkthrough.ipynb) in a fresh Python 3.14
dev-container kernel.

An administrator reviews caller managed-identity model/knowledge/history access
and Foundry Agent Consumer (or Azure AI User) on the callee project/agent.
Model permission alone is not agent invocation permission.
Pin the callee's stable endpoint to the accepted Lab 8 version before calling;
the client checks the fixed 100% selector read-only and validates the returned
runtime version. See [official routing and authorization](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent).
No speculative `agent-version` query is used.

## Product lineage and notebook path

1. Restore BOTH predecessors and validate the original measured source bundle.
2. Reject an unsafe advisor-decision envelope before a remote request.
3. YOUR TURN: choose a bounded timeout, predict failure behavior and inspect
   original [delegation.py](../../shared/hosted-delegation/delegation.py).
4. Prepare the separate [candidate](../../shared/hosted-delegation/hosted/).
   Its bootstrap reuses the accepted Lab 6 implementation and sponsor-tool/
   handoff-policy module. Tools, compliance, knowledge and history survive.
   `prepare.vendor()` copies originals into this candidate only; never edit
   prepared `core_product.py` or overwrite the Labs 9-10 source/version.
5. Explicitly deploy `healthcare-concierge-delegation-{suffix}` with its own
   history container/session directory and reviewed identity access, then pin
   its endpoint to the inspected candidate version.
6. Invoke one correlated pending case through the DEPLOYED caller. Require
   exact case/session/participant IDs, pending status, no advisor decision,
   and exact callee/caller runtime versions.
7. Inspect Azure caller/callee spans sharing the trace ID and explicit case/
   session attributes, then publish the independent checkpoint.

The supported async SDK `get_openai_client(agent_name=...)` authenticates through
`DefaultAzureCredential`. Responses input carries the pending-case envelope;
`extra_headers` carries W3C trace context. The caller injects its span context,
the callee extracts it around the existing workflow. Configuration/IDs alone
are not evidence that Azure ingested the spans.

## Safety and retry boundary

The turn is bounded to at most 120 seconds. Authentication, transport, timeout,
malformed JSON, changed versions and non-pending statuses fail visibly.
Automatic transport retries are disabled.
The delegation tool accepts no model-generated arguments: a request-scoped
application binding supplies the original IDs/message. Calls without an explicit
pending-case envelope fail before networking. The endpoint selectors are checked
both before and after the turn, in addition to returned runtime versions.
A timeout may have created pending state: inspect its case/session and service logs before deliberately making
another case. Duplicate rejection is not distributed idempotency.
Never forward an advisor decision or claim cross-service, replica-safe or
version-roll resume. Pending files remain single-instance only.
The envelope's `session_id` is explicit application correlation, not proof of
platform sandbox continuity or a shared distributed workflow-state store.
The candidate is not promoted and gains no inherited evaluation PASS.

## Checkpoint

`../artifacts/hosted_delegation/part_a.json` stores `triage_reference`,
`caller_name`, `caller_version`, `evaluated_target`, `tested_sources`,
`accepted` and `one_shot_pending_only`. Evidence: `target.json`,
`source_evidence.json`, `failure_evidence.json`, `delegation_evidence.json`,
`trace_evidence.json`.
Old prompt-backed `stretch6/part_b.json` is rejected with a new Lab 12 rerun
instruction; Lab 11 evidence is not reinterpreted or modified.

## Recovery and cleanup

Rerun the producing Lab 8/9 for changed predecessor evidence and affected
Lab 12 gates for changed candidate sources or versions. No local server remains.
Use reviewed cleanup only for this candidate; preserve core release evidence.
Edit `lab12_workflows_delegation.py` and regenerate the notebook.
