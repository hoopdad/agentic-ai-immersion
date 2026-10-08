# Lab 4: Deploy and invoke the hosted concierge

Deploy Lab 3's tested product and invoke an explicitly inspected active version.
This folder contains only Lab 4.

## Prerequisites

Complete [Lab 3](../lab3/README.md). Keep its local metadata, transcripts and
unchanged tested product. The approved network path and separate deployment/
invocation roles must be effective.

Open [Lab 4](lab4_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Its prerequisite cells restore state, not Lab 3's demos.

## Notebook path

1. Validate the scoped local checkpoint and tested source in Step 4.2.
2. Review the shared product and deployment target in Step 4.3.
3. Explicitly upload/deploy the pinned package in Step 4.4.
4. Inspect Foundry version status, wait for `active`, and enter the actual
   `DEPLOYED_VERSION` for Step 4.5.
5. Require successful Responses inference, then publish in Step 4.6.

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

Continue with [Lab 5](../lab5/README.md).

## Authoring

Edit `lab4_deploy_invoke.py` and regenerate `lab4_walkthrough.ipynb`.
