# Lab 4: Build, test, deploy, and invoke

## Prerequisites

Lab 1 verified chat-only setup; local acceptance is included here.

Open [lab04_walkthrough.ipynb](lab04_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel. Run the described cells in order.
The notebook contains the actual inputs, YOUR TURN edits, and acceptance gates.

## One-day scope and continuity

Local tool/policy exercises and their genuine acceptance are folded into this lab before deployment. No separate Lab 3 is needed. Edit only the isolated `../products/hosted-agent-basics/hosted/main.py`, never the three-day product.

Artifacts live in `../artifacts/`; use a distinct attendee suffix for a separate workshop run. Configuration remains in the repository-root `.env`, so tracks are not simultaneous environments.

## Checkpoint

`artifacts/lab2/part_a.json` records real local acceptance inside Lab 4; `part_b.json` records the actual deployed invocation for capstone Lab 7.

## Recovery and synchronization

Rerun the producing notebook's failed gates; do not invent checkpoints or replay unrelated provisioning. Only notebook-owned processes are stopped. Deployment/model calls incur charges; local and deployed evidence are distinct. Use reviewed attendee-scoped cleanup.

This guide, notebook, source, and starting product are generated. Edit canonical material or the explicit adapter in `tools/sync_one_day_labs.py`; run sync before delivery, never over a learner's in-progress exercises.

[Canonical detailed guide](../../3-day-labs/lab04/README.md) describes the full workshop; its additional prerequisites and next labs are not one-day requirements. For this adapted capstone, follow this guide and notebook.
