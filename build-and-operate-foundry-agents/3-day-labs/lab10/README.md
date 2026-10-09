# Lab 10: Release gates and rollback rehearsal

Gate Lab 9's measured baseline, block a regression and rehearse release ownership.
This folder contains only Lab 10.

## Prerequisites

Complete [Lab 9](../lab09/README.md). Keep the original measured files unchanged.
Actual cloud releases additionally require administrator-managed target settings,
OIDC and protected environments; they are not performed by this notebook.

Open [Lab 10](lab10_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
It loads the durable evaluation bundle without replaying model evaluation.

## Notebook path and YOUR TURN

1. Recompute deterministic safety and apply strict saved-score thresholds.
2. Corrupt an in-memory response copy with a recommendation; require blocked
   promotion while preserving the measured baseline files.
3. Restore the exact original rows and gate them without new judge calls.
4. Enter an approved proposed target and non-placeholder release tag. Prepare
   a gated **dry-run** promotion, not a deployment.
5. Inspect actual active/known-good version references and retain a reviewed
   rollback plan as a rehearsal.

One safety violation, missing score or malformed evidence fails closed. A sample
gate PASS is not complete factual/privacy/compliance certification.
Rollback must not be assumed to preserve history: Lab 6 needs the same accessible
shared Blob backend and compatible session configuration, not container files.

## Checkpoint

`../artifacts/lab5/part_b.json`, `operate.json`, `gate_result.json`,
`release_plan.json` and promotion/rollback records distinguish measured acceptance
from rehearsed cloud actions. Publication requires current recovered evidence.

The [release template](../../shared/operate-hosted-agents/.github/workflows/agent-ci.yml)
and [infrastructure contract](../../shared/operate-hosted-agents/infra/README.md)
are internal administrator tooling, not an extra learner command route or an
automatically enabled workflow. Real promotion rechecks the gate, validates the
target, deploys and smoke-tests before recording success.

Optional [Lab 11](../lab11/README.md) needs Lab 4, not this report.

## Learning contract and recovery

- **Required:** scoped Lab 9 acceptance and exact bundle/responses/scores/target fingerprints.
- **Recommended route:** complete core Labs 1-10 before selected optional Labs 11-14.
- **Primary delta / lineage (continue evidence):** gate the measured candidate, not a modified product;
  no new judge calls. Default promotion/rollback remain rehearsals.
- **Acceptance:** unsafe copied response fails, exact baseline passes again. Gate and promotion records
  bind bundle/results SHA256, and source changes fail closed even when an old gate says PASS.
  A local evaluated product does not become deployed evaluation evidence by adding a version label.
- **Recovery:** changed candidate/question set/evidence requires Lab 9 and Steps 10.1-10.6 again;
  never rerun just a deterministic gate to claim new measured quality. Extensions keep separate candidates.
  No server starts here. Retain rollback inputs and review cleanup without deleting core release evidence.

## Authoring

Edit `lab10_release_rollback.py` and regenerate `lab10_walkthrough.ipynb`.
