# Labs 13-14: Invocations protocol, Foundry Toolbox and Skills

| | |
|---|---|
| Goal | Keep denied-claim facts deterministic and model explanation bounded; add reusable Skills and optional Toolbox to a Responses product |
| Time | 45–60 min; complete Invocations first |
| Starts from | Lab 2's verified project/model configuration; Lab 14 requires Lab 13; Labs 3-12 are not required |
| Notebooks | [Lab 13](lab13_walkthrough.ipynb), then [Lab 14](lab14_walkthrough.ipynb) in a fresh kernel |
| Produces | `artifacts/stretch7/invocations.json`, `claim_reviews/CLM-*.json`, `skills_transcript.md` |
| Cloud requirement | Deterministic notebook checks need no model; model-backed local demos and deployment require Azure |

Open these notebooks with `/usr/local/bin/python` in the repository dev container.
Run their deterministic, model-backed and deployment cells in order, using editable
inputs for optional Toolbox. Internal `stretch7_invocations.py` is a reusable helper,
not a terminal learner route.

## Two focused labs

| Lab | Scope | Durable checkpoint |
|---|---|---|
| 13 (25–30 min) | Prepare only Invocations, offline fact checks, model-assisted nightly scenario, batch-only deployment | `artifacts/stretch7/part_a.json`, offline/nightly evidence and original claim reviews |
| 14 (25–30 min) | Read Lab 13, prepare only Responses Skills, prove first/second skill use, validate optional Toolbox configuration, Responses-only deployment | `artifacts/stretch7/part_b.json`, Skills evidence/transcript and cumulative `invocations.json` |

Lab 14 never replays the batch or rebuilds/deploys its host. Missing, changed, or differently scoped Lab 13 evidence blocks Lab 14.
Rerunning a Lab 13 action invalidates both completion checkpoints; rerunning Lab 14 invalidates its checkpoint until success.
Each risky cell clears its acceptance outcome before execution, and publication requires every intended current gate.
Blank `SKILL_NAMES` automatically includes every local workshop skill, including the newly authored second skill.
Toolbox configuration is not a passing invocation check; unavailable/skipped preview behavior stays explicitly unverified.
Author notebooks in `lab13_invocations.py` and `lab14_skills_toolbox.py`; the original driver preserves its cumulative API.

## Protocol contract

| Dimension | Invocations | Responses |
|---|---|---|
| Route | `POST /invocations` | `POST /responses` |
| Body | `{"message": "{\"claim_ids\":[\"CLM-9003\"]}"}` | `{"input": "...", "stream": false}` |
| Local response | Text containing `ClaimReviewBatch` JSON | OpenAI Responses envelope |
| State | One structured request; no learner-managed chat history | Multi-turn response/session flow |
| Best fit | Scheduled reviews, batch jobs, pipelines | Participant conversations and research |

The notebook uses the pinned host's route/response contract. Facts come from
`claims_review.py` over systems of record and KB-ACC-001; the model contributes
only a plain-language explanation inside the bounded schema.

## Teach and deterministic evidence

Run the notebook's deterministic review cells. Every fact field must match the
governed claim review, including CLM-9003's complete accepted-document list.
Malformed/empty responses or safety failures fail acceptance. This validates
the fact contract; it does not authorize payment, claim resubmission or coverage decisions.

Run model-backed local cells only after Labs 1-2's verified configuration is
available. Inspect `artifacts/stretch7/hosted-invocations_local.log`; notebook
lifecycle controls stop the child product on success or failure.

## Product packaging

Lab 13 prepares `hosted-invocations`; Lab 14 separately prepares
`hosted-responses-skills`. Shared code/data and bundled Skills are vendored and
hashed. Stale copies, missing imports, credentials, deployment state and caches
must not enter the upload. Generated vendored copies are not hand-editable
source; rerun notebook preparation after product edits.

This packaging implementation is shared internal tooling, not an extra manual
learner execution route. Foundry builds the same reviewed Python product
tested by the notebook.

## YOUR TURN: nightly denials

Change the notebook's batch input to use `nightly_denial_ids()` and run the cell
below the exercise. The acceptance gate discovers all denied claims through
the fact tools, invokes exactly that set, checks deterministic fields and stops
its server. This request shape fits a scheduled pipeline or optional preview Routine.

## Skills

Run the bundled HRA Skill cells. Inspect startup skill names and the `read_skill`
log containing the selected source document. Progressive disclosure exposes an
index first and loads a governed procedure only when needed.

The versioned procedure is reusable intelligence, distinct from the human skill
of specifying/reviewing agent work. Provenance metadata does not automatically
refresh rules or prove their continued accuracy.

### YOUR TURN: a second skill

In the exercise, author `skills/debit-card-faq/SKILL.md` from the reviewed
`data/knowledge/debit-card-faq.md`, with `name: debit-card-faq` and
`source_doc: KB-ACC-002`. Include declined, blocked and lost-card procedures and
the full-card-number safety rule. This is a learner product exercise, not an
additional file required to run the existing walkthrough.

Run the notebook gate. It validates the source, rebuilds the package, asks the
pharmacy-decline question and requires both a `[KB-ACC-002]` citation and a
`read_skill name=debit-card-faq` log entry before cleanup.

## Optional Foundry Toolbox preview

Enter both Toolbox name and HTTPS MCP endpoint in the notebook's optional
configuration, or leave both absent. Partial configuration fails explicitly.
Verify its token audience and dedicated agent-identity access with the
administrator. Authentication/401/403 errors must not silently disable the tool.

Only public information may go to web search, never participant data.
The instruction boundary is not proof of complete runtime egress enforcement
or production compliance. If the region/preview is unavailable, skip Toolbox
without claiming it passed.

## Deploy and inspect

Use explicit notebook deployment actions for the two prepared packages and
review their distinct protocols/target names. Wait for active versions, record
real references and invoke each through the notebook. Remaining live checks
include endpoint compatibility, identity access and optional Toolbox behavior;
offline validation cannot establish these outcomes.

## Checkpoint and troubleshooting

Share a schema-valid denied-claim review with its source facts, the selected
Skill/source log and the two-protocol comparison. Clearly label any skipped
cloud/preview checks.

| Symptom | Fix |
|---|---|
| Invocations 404 | Inspect product readiness and the notebook's `/invocations` route |
| Unparseable response | Inspect HTTP body; reject unknown or empty envelopes |
| Stale package | Rerun notebook preparation; do not edit vendored copies |
| No Skills loaded | Inspect source Skill frontmatter and rerun Responses packaging |
| Toolbox configuration error | Supply both optional inputs or remove both |
| Toolbox authentication failure | Check signed-in identity locally, hosted agent identity, audience, RBAC and propagation |
| Preview unavailable | Complete Invocations/Skills and explicitly skip Toolbox |
