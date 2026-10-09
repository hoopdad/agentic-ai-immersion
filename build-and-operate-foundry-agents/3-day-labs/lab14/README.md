# Lab 14: Governed Skills and optional Toolbox

Add progressive-disclosure Skills to a Responses product while preserving the
completed batch evidence. This folder contains only optional Lab 14.
The distinct `healthcare-skills-responses-{suffix}` product does not inherit
concierge knowledge/history, batch state or MAF approval merely by sharing facts.

## Prerequisites

Complete [Lab 13](../lab13/README.md). Keep its current batch evidence and scope.
Recommend core Labs 1-10 first, then Labs 13-14.
Optional Toolbox is an administrator-provided preview endpoint; confirm region,
identity access and token audience rather than assuming model access grants it.

Open [Lab 14](lab14_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Only the Responses Skills package is prepared/invoked/deployed.

## Notebook path and YOUR TURN

1. Restore Lab 13's handoff without replaying Invocations.
2. Configure both Toolbox name and HTTPS MCP endpoint, or leave both blank.
   Partial/credential-bearing configuration fails explicitly.
3. Prepare the shared [Skills product](../../shared/invocations-toolbox-skills/hosted-responses-skills/)
   and require a governed answer plus an actual `read_skill` log.
4. Create [`skills/debit-card-faq/SKILL.md`](../../shared/invocations-toolbox-skills/skills/)
   in that shared skill collection, using
   [`data/knowledge/debit-card-faq.md`](../../data/knowledge/debit-card-faq.md).
   Set `name: debit-card-faq`, `source_doc: KB-ACC-002`; cover declined, blocked
   and lost cards and prohibit reading/requesting/recording the full card number.
5. Rebuild the Skills package; require `[KB-ACC-002]` and
   `read_skill name=debit-card-faq` in the acceptance gate.
6. Deploy only the Responses package with reviewed configuration.

Blank `SKILL_NAMES` includes every local workshop skill, including the new one.
The index is loaded first and governed procedures on demand; provenance does
not automatically refresh rules. Only public information may reach web search,
never participant data. Instruction boundaries are not complete egress proof.
Do not silently disable Toolbox after authentication failures.

## Checkpoint

`../artifacts/stretch7/part_b.json`, `skills_transcript.md` and cumulative
`invocations.json` preserve Skills evidence without replacing the earlier batch.
Toolbox configuration is not verified tool invocation. Explicitly label skipped
preview/live checks rather than claiming success.
Deployment-command completion is not a deployed Skill turn. Skills preparation
asserts that the original batch reference and nightly evidence are unchanged.
Missing/changed Skills evidence requires only Lab 14; do not replay the batch.
Acceptance helpers stop only their own servers; use reviewed workshop cleanup.

## Authoring

Edit `lab14_skills_toolbox.py` and regenerate `lab14_walkthrough.ipynb`.
