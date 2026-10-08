# Lab 8: Advisor approval and recovery

Resume Lab 7's original cases, verify advisor revision/restart recovery and
deploy the reviewed triage product. This folder contains only Lab 8.

## Prerequisites

Complete [Lab 7](../lab7/README.md). Preserve its immutable snapshots, durable
pending sessions and unchanged source fingerprints. Do not restart intake.
Cloud deployment requires the approved enablement, roles and network.

Open [Lab 8](lab8_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
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
advisor decision. These packets are optional context for [Lab 9](../lab9/README.md),
not required inputs to its concierge evaluation.

## Authoring

Edit `lab8_advisor_recovery.py` and regenerate `lab8_walkthrough.ipynb`.
