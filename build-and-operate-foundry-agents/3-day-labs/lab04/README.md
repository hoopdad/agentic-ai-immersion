# Lab 4: Deploy and invoke the hosted concierge

Deploy Lab 3's tested product and invoke an explicitly inspected active version.
This folder contains only Lab 4.

## Prerequisites

Complete [Lab 3](../lab03/README.md). Keep its local metadata, transcripts and
unchanged tested product. The approved network path and separate deployment/
invocation roles must be effective.

Open [Lab 4](lab04_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Its prerequisite cells restore state, not Lab 3's demos.

## Notebook path

1. Validate the scoped local checkpoint and tested source in Step 4.2.
2. Review the shared product and deployment target in Step 4.3.
3. Explicitly upload/deploy the pinned package in Step 4.4.
4. Inspect Foundry version status, wait for `active`, and enter the actual
   `DEPLOYED_VERSION` for Step 4.5. Pin 100% of traffic to that version in
   Foundry's version selector; the notebook reads and validates the selector.
5. Require Northwind/$3,600 from the retained sponsor tool via deployed Responses,
   then publish in Step 4.6; nonempty model prose alone is not acceptance.

Foundry builds the same
[shared product](../../shared/hosted-agent-basics/hosted/main.py) tested locally;
there is no duplicate product in this folder. Version creation incurs charges.
Foundry Project Manager deploys; Agent Consumer or Foundry User invokes.

For 401/403, distinguish identity/RBAC from network isolation. For
`424 session_not_ready`, inspect startup/version logs before redeploying.
Remote inference uses bounded timeouts/retries. A single-turn `store=False`
pass does not prove multi-turn response storage.

## Checkpoint

`../artifacts/lab2/part_b.json` and the `deployed` block of `hosted.json` record
active-version inference acceptance. A queued build is not a deployed PASS.
Failed retries cannot publish old successful evidence.

Continue with [Lab 5](../lab05/README.md).

## Learning contract and recovery

- **Required:** scoped Lab 3 local acceptance/transcripts and unchanged tested source.
- **Recommended route:** core Labs 1-10 in order; next Lab 5.
- **Primary delta / lineage (continue):** same accepted sponsor/policy product, now deployed.
- **Acceptance:** actual inference with fixed-version routing, not a queued build or metadata alone.
- **Recovery:** source changes require Lab 3 acceptance; startup failures require log review,
  then Steps 4.4-4.6. Optional [Lab 11](../lab11/README.md) and
  [Lab 13](../lab13/README.md) branch here after the core guided route.
  Branches share port 8088, quota and source: run one notebook at a time, stop only owned processes,
  and review attendee-scoped resource cleanup.

See the current [version-selector contract](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent).
The stable name endpoint is not inherently pinned; creating a new version under
latest-version routing must not silently change the accepted target.

## Authoring

Edit `lab04_deploy_invoke.py` and regenerate `lab04_walkthrough.ipynb`.
