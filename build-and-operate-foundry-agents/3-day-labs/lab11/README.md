# Lab 11: Prompt versus hosted

An optional, terminal 10-15 minute comparison: one `PromptAgentDefinition`,
one version, one invocation. Foundry owns the instruction definition; Lab 4's
hosted product owns Python, tools, packaging and runtime. This is not a second
agent-development track, MAF ensemble, knowledge exercise or portal edit/restore.

## Prerequisites and route

Complete [Lab 4](../lab04/README.md), including `lab2/part_b.json` and
deployed inference. Use a fresh Python 3.14 dev-container kernel in
[lab11_walkthrough.ipynb](lab11_walkthrough.ipynb).
Recommend core Labs 1-10 first. No Labs 5-10 artifact is required.
The explicit publishing/invocation action uses reviewed identity/network access
and may incur charges.

## Notebook path and YOUR TURN

1. Restore the scoped Lab 4 handoff without redeployment.
2. Inspect the single bounded prompt and shared compliance block.
3. Predict ownership and edit the one question to ask about choosing a plan.
4. Publish one version, explicitly pin only this comparison name endpoint to it,
   and invoke it once; require an advisor
   handoff, no recommendation and no PII. This choice question tests the boundary,
   not participant-specific knowledge or regulatory certification.
5. Publish the terminal comparison.

The [shared helper](../../shared/prompt-agents-and-workflows/stretch6_prompt_agents.py)
has no cloud side effects on import. It creates no function tools or workflow.
The endpoint pin uses the documented fixed-version selector and affects only this
terminal comparison resource, never core hosted traffic.

## Checkpoint

`../artifacts/stretch6/part_a.json` stores `prompt_comparison` and `terminal=True`;
`prompt_agents.json` identifies the ONE named/versioned agent and
`prompt_turn.json` records the observed turn. No downstream lab consumes these.

## Recovery and cleanup

Failed/changed evidence requires Lab 11 again, not portal restoration.
No local server starts. Review attendee-owned resources through the workshop
cleanup dry run; do not delete shared infrastructure.

Choose [Lab 12](../lab12/README.md) after BOTH Labs 8 and 9, or
[Lab 13](../lab13/README.md) after Lab 4; neither depends on this comparison.
Edit `lab11_prompt_agents.py` and regenerate the notebook with the converter.
