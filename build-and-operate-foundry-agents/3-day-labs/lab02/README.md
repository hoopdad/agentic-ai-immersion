# Lab 2: Models and verified configuration

Reuse Lab 1's project, provision compatible chat/embedding deployments, verify
inference and persist settings for later labs. This folder contains only Lab 2.

## Prerequisites

Complete [Lab 1](../lab01/README.md). Retain its approved subscription, tenant,
attendee suffix and handoff. The facilitator must approve model availability,
quota, management/inference permissions and networking.

Open [Lab 2](lab02_walkthrough.ipynb) with a fresh Python 3.14 dev-container
kernel. It rechecks project ownership without creating or updating the project.

## Notebook path

1. Reenter approved context and optional downstream inputs in Step 2.2.
2. Read the handoff and inspect the live model inventory in Step 2.3.
3. Select advertised model versions, SKUs and capacity; review costs in Step 2.4.
4. Explicitly approve compatible deployments in Step 2.5.
5. Require hello-world chat and a 3072-dimensional embedding in Step 2.6.
6. Publish verified configuration in Step 2.7.

Use `text-embedding-3-large` with 3072 dimensions for the later Search schema.
Compatible deployments are reused; incompatible ones are not overwritten.
Quota changes and roles can require propagation. Retry-header handling is
bounded; persistent throttling needs administrator review.

Search, optional Blob and telemetry inputs are administrator-supplied existing
resources, not discovered or provisioned here. Blank optional inputs preserve
existing values. Rerun inputs/publication after receiving a missing value.

## Checkpoint

`../artifacts/lab1/project.json`, `part_b.json` and the repository-root `.env`
record verified project/model settings. Publication requires fresh smoke
evidence for the exact project, endpoints and deployment plan. No tokens, raw
responses or embedding vectors are persisted.

This does not certify hosted-agent infrastructure or Search/Blob/telemetry
readiness. Continue with [Lab 3](../lab03/README.md).
Optional protocol branches require Lab 4's hosting concepts and accepted deployment.

## Learning contract and recovery

- **Required:** Lab 1's scoped `lab1/part_a.json`, ownership and approved model quota/access.
- **Recommended route:** core Labs 1-10 in order; next Lab 3.
- **Primary delta / lineage (continue):** retain the same project and add verified model configuration.
- **Acceptance:** chat plus 3072-dimensional embeddings for the exact selected deployments;
  reject changed ownership or incompatible existing deployments.
- **Recovery:** restore Lab 1's handoff or rerun Steps 2.3-2.7; never reuse stale smoke evidence.
  No local server remains. Use reviewed attendee cleanup, not shared-account deletion.

## Authoring

Edit `lab02_models_verify.py` and regenerate `lab02_walkthrough.ipynb`.
The shared [project setup helper](../../shared/foundry-project-models/project_setup.py)
preserves the original artifact and environment contracts.
