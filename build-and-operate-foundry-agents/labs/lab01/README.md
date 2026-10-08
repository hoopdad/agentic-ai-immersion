# Lab 1: Identity and your Foundry project

Create one attendee-owned project inside an approved existing Foundry account.
This folder contains only Lab 1.

## Prerequisites

Your facilitator supplies a project-enabled `AIServices` account, approved
subscription/tenant, resource group, network path, model quota and management
permissions. Account infrastructure, hosted-agent enablement and role assignments
remain administrator responsibilities.

Open [Lab 1](lab01_walkthrough.ipynb) in the repository Python 3.14 dev container
with `/usr/local/bin/python`. Run cells individually, not Run All.

## Notebook path

1. Import helpers and enter approved context in Steps 1.1-1.2.
2. Discover identity/accounts in Step 1.3 without switching subscriptions.
3. Review account and project ownership in Step 1.4.
4. Approve only the displayed attendee project and publish its handoff in Step 1.5.

Keep the same unique attendee suffix throughout the workshop. Stop on an
unexpected identity, scope, permission or network failure; do not enable public
access or broaden permissions to bypass it.

## Checkpoint

`../artifacts/lab1/part_a.json` contains the explicit project/context handoff,
not credentials. Models and the root `.env` are not created in this lab.
Rerunning setup invalidates dependent evidence, not cloud resources.

Continue with [Lab 2](../lab02/README.md) in a fresh kernel.

## Authoring

Edit `lab01_identity_project.py` and regenerate `lab01_walkthrough.ipynb`.
Reusable provisioning helpers are in
[`shared/foundry-project-models`](../../shared/foundry-project-models/).
