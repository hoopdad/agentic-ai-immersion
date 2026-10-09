# Lab 6: Durable sessions and resiliency

Reuse existing knowledge, prove restart behavior and deploy the session-enabled
concierge. This folder contains only Lab 6.

## Prerequisites

Complete [Lab 5](../lab05/README.md); retain its prepared shared package, knowledge
and current acceptance evidence. Optional shared history needs an existing
administrator-supplied Blob account/container and identity/network access.

Open [Lab 6](lab06_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
No Search/index/connection creation is replayed.

## Notebook path and YOUR TURN

1. Restore scoped knowledge and verify the unchanged tested product.
2. Run a conversation across two different local process IDs; require retained
   `atorvastatin` context under the same conversation identity.
3. Restart deliberately with an empty store and explain lost context.
4. Test two replicas against shared Blob/Azurite when configured. SKIPPED means
   shared continuity is unproven, not passed.
5. Review the target, deploy the already-built
   [shared product](../../shared/hosted-knowledge-sessions/hosted/main.py),
   wait for `active`, enter the real version and verify its citation.
6. Publish the distinct continuity and deployed results.

Files prove local restart continuity only. Existing accessible shared Blob
history is required for deployed replica/version continuity. Azurite is a local
emulator and must never be deployed. This lab does not create cloud storage.
Idle expiry is logical; physical blob cleanup remains administrator-owned.

## Checkpoint

`../artifacts/lab3/part_b.json`, `knowledge.json`, `hosted.json`, sessions and
transcripts preserve the backend actually exercised. Keep two process IDs and
one governed citation as evidence. Failed gates cannot reuse old success flags.

Continue with [Lab 7](../lab07/README.md), or branch to
[Lab 9](../lab09/README.md). The optional Lab 11 comparison requires Lab 4.

## Learning contract and recovery

- **Required:** scoped Lab 5 knowledge checkpoint, transfer fingerprint and prepared package.
- **Recommended route:** core Labs 1-10 in order; next Lab 7, then 8, then operations 9-10.
- **Primary delta / lineage (continue):** retain the knowledge/tools/enrollment policy,
  prove the declared history backend, then deploy it. Pending workflow state remains separate.
- **Acceptance:** same session across two PIDs, empty-store loss, and a governed deployed citation;
  pin 100% traffic to the inspected version before invocation. Optional shared-scale SKIPPED
  remains explicitly unproven; Azurite is never deployed.
- **Recovery:** restore Lab 5 after package/evidence changes, then Steps 6.4-6.9.
  Preserve sessions and checkpoint inputs; stop owned processes, not other notebooks.
  Ports, quota and sources are shared across branches; cleanup is reviewed and attendee-scoped.

## Authoring

Edit `lab06_sessions_resiliency.py` and regenerate `lab06_walkthrough.ipynb`.
