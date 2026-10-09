# Lab 7: Build and host a multi-agent team

## Prerequisites

Lab 4's accepted deployed Responses checkpoint; no Lab 6 requirement.

Open [lab07_walkthrough.ipynb](lab07_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel. Run the described cells in order.
The notebook contains the actual inputs, YOUR TURN edits, and acceptance gates.

## One-day scope and continuity

Inspect the scaffolded MAF graph, watch S1-S3 route to specialists and pause for review, add a tool-free structured classifier, and prove the ambiguous card issue routes to accounts. Then explicitly approve a mixed-case packet and deploy the same edited workflow in Foundry. Review and explicitly approve its hosted packet.

MAF provides fan-out/fan-in, structured merge and the human request boundary; Foundry provides the versioned hosted Responses endpoint. Specialists are code-defined inside one container, not Prompt Agents. Synthetic local knowledge replaces Search. Compliance review remains in the graph; forced unsafe drafts, restart recovery, external history, delegation and production authorization are outside this short capstone. If you stop before the local decision cell, run `team_server.stop()` before leaving the notebook.

Artifacts live in `../artifacts/`; use a distinct attendee suffix for a separate workshop run. Configuration remains in the repository-root `.env`, so tracks are not simultaneous environments.

## Checkpoint

`artifacts/lab4/part_a.json` is explicitly marked `one-day-team`; it records local classifier/approval and actual fixed-version hosted approval. It is not the three-day Lab 7/8 recovery contract. No downstream lab consumes this capstone.

## Recovery and synchronization

Rerun the producing notebook's failed gates; do not invent checkpoints or replay unrelated provisioning. Only notebook-owned processes are stopped. Deployment/model calls incur charges; local and deployed evidence are distinct. Use reviewed attendee-scoped cleanup.

This guide, notebook, source, and starting product are generated. Edit canonical material or the explicit adapter in `tools/sync_one_day_labs.py`; run sync before delivery, never over a learner's in-progress exercises.

[Canonical detailed guide](../../3-day-labs/lab07/README.md) describes the full workshop; its additional prerequisites and next labs are not one-day requirements. For this adapted capstone, follow this guide and notebook.
