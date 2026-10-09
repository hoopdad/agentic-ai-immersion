# Lab 8: Advisor approval and recovery

Resume Lab 7's original cases, verify advisor revision/restart recovery and
deploy the reviewed triage product. This folder contains only Lab 8.

## Prerequisites

Complete [Lab 7](../lab07/README.md). Preserve its immutable snapshots, durable
pending sessions and unchanged source fingerprints. Do not restart intake.
Cloud deployment requires the approved enablement, roles and network.

Open [Lab 8](lab08_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Original definitions are imported; Lab 7's notebook is not executed.

## Notebook path and YOUR TURN

1. Validate scope, snapshots, pending status and tested source before decisions.
2. Revise S3 with the IEP question; require two attempts, the retained question,
   a safe packet and final approval.
3. Restart before approving S2. Require `resume_path=session_store` and
   matching persisted recovery provenance.
4. Review and deploy the shared
   [triage product](../../shared/hosted-multi-agent-handoff/hosted/main.py).
5. Inspect an active version, enter `DEPLOYED_VERSION` and require a deployed
   case to reach final approval before publication.

Already-approved retries are accepted only for the matching original case and
verified recovery evidence. A different deployed replica cannot read the
file-backed session map: local recovery is not cross-replica continuity.
This simulates an advisor; production must authenticate an authorized person
before accepting a decision.

## Checkpoint

`../artifacts/lab4/part_b.json`, `hosted.json`, handoff packets and sessions retain
the approval/recovery outcome. Share S3's open questions, compliance flags and
advisor decision. These packets are optional context for [Lab 9](../lab09/README.md),
not required inputs to its concierge evaluation.

## Learning contract and recovery

- **Required:** scoped Lab 7 checkpoint, unchanged sources and original pending sessions/snapshots.
- **Recommended route:** core Labs 1-10 in order; next Lab 9, whose technical input is Lab 6.
- **Primary delta / lineage (continue):** simulated advisor approval/revision and local restart recovery,
  then deployment of the same triage product; never recreate cases to manufacture recovery.
- **Acceptance:** original identities and `resume_path=session_store`, explicit decisions and
  deployed final approval. Pin 100% routing to `DEPLOYED_VERSION` before the cloud invocation.
- **Handoff:** `lab4/part_b.json` includes `triage_reference` with exact name/version/project/protocol
  endpoint, observed capabilities and `recovery_backend="single-instance files"`.
  Optional [Lab 12](../lab12/README.md) joins this evidence with Lab 9; it must not
  claim distributed resume or forward an advisor decision automatically.
- **Recovery:** restore Lab 7 only for changed/missing pending evidence; matching already-approved
  original sessions are recoverable. Rerun Steps 8.2-8.5 after failures. Preserve sessions,
  stop owned processes and review attendee cleanup. File state is not replica/version-roll continuity.

The service also accepts a bounded `operation="pending_case"` envelope for the
optional delegation branch, preserving case/session/participant/traceparent,
returning the platform `FOUNDRY_AGENT_VERSION`, and stopping at pending approval.
Duplicate intake and advisor fields are rejected; no state-changing request is
automatically replayed. This still uses the same MAF graph and file-state limitation.

## Authoring

Edit `lab08_advisor_recovery.py` and regenerate `lab08_walkthrough.ipynb`.
