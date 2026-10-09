# Lab 13: Structured Invocations

Review denied claims with deterministic facts and bounded model explanations.
This folder contains only optional Lab 13; no Skills host is prepared here.

## Prerequisites

Complete [Lab 4](../lab04/README.md), including accepted `lab2/part_b.json`
deployed inference and hosting/protocol concepts. Labs 5-12 are not required.
Recommend core Labs 1-10 first. Deterministic fact checks alone need no model.
Live actions still need the approved project identity, network and hosted setup.

Open [Lab 13](lab13_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.

## Notebook path and YOUR TURN

1. Compare stateless `POST /invocations` with conversational `POST /responses`.
2. Prepare only the shared
   [Invocations product](../../shared/invocations-toolbox-skills/hosted-invocations/).
3. Run offline exact-fact checks, including CLM-9003's accepted-document list.
4. Use `nightly_denial_ids()` for the model-backed nightly-denial exercise.
   Require exactly the denied claims, preserved facts and cited explanations.
   YOUR TURN: inspect `FACT_FIELDS` and predict which values must not change
   when the model adds its explanations.
5. Explicitly deploy only the tested batch protocol and retain the handoff.

Invocations accepts `{"message": "<JSON string>"}` and returns text containing
`ClaimReviewBatch` JSON. Facts come from the governed
[claim reviewer](../../shared/invocations-toolbox-skills/hosted-invocations/claims_review.py);
the model supplies bounded explanation fields only.
Malformed/empty responses and safety failures fail acceptance.
The review does not authorize payment, claim resubmission or coverage decisions.
This new stateless product does not inherit concierge retrieval/history or
MAF approval state. Local helpers stop only their owned server processes.

## Checkpoint

`../artifacts/stretch7/part_a.json`, `invocations.json`, exact-fact/nightly evidence
and `claim_reviews/` retain the original batch. Label live endpoint checks
separately; offline facts are not deployed readiness.
Deployment-command completion is also not a live batch endpoint check.
Missing hosting evidence requires Lab 4; changed batch evidence requires Lab 13.
Use the workshop cleanup dry run for reviewed attendee-owned resources.

[Lab 14](../lab14/README.md) retains this record without rebuilding, invoking
or redeploying the batch host.

## Authoring

Edit `lab13_invocations.py` and regenerate `lab13_walkthrough.ipynb`.
