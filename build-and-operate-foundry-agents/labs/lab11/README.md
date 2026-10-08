# Lab 11: Platform-managed prompt agents

Compare prompt-definition ownership with hosted product ownership.
This folder contains only optional Lab 11; no workflow agent is created here.

## Prerequisites

Complete [Lab 6](../lab6/README.md) for the knowledge/hosted checkpoints and
verified configuration. Labs 7-10 are not required. Confirm permissions and
availability for the selected Foundry agent surface.

Open [Lab 11](lab11_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Publishing versions and executing turns are explicit paid Azure actions.

## Notebook path and YOUR TURN

1. Inspect shared function schemas, policy and project-connected MCP knowledge.
2. Publish only the six versioned prompt-agent definitions.
3. Run the concierge's client-side function-call loop; inspect requested tools,
   authoritative facts and the no-recommendation boundary.
4. Edit the concierge greeting in the portal for Evelyn and run the acceptance
   gate. Cleanup restores canonical instructions; retain the restored version ID.
5. Publish prompt names/IDs and current acceptance evidence.

The [shared implementation](../../shared/prompt-agents-and-workflows/stretch6_prompt_agents.py)
uses `PromptAgentDefinition`, `FunctionTool` and `MCPTool`. A client executes
Python function tools; a platform workflow cannot execute arbitrary caller code.
Choose ownership/lifecycle deliberately, not an assumed maturity or cost ladder.
Regulated instructions still need a human owner and review.

## Checkpoint

`../artifacts/stretch6/part_a.json`, `prompt_agents.json`, tool and portal evidence
bind the published references to the current scope.

[Lab 12](../lab12/README.md) reuses these agents without republishing them.
Failed retries cannot restore an old acceptance result.

## Authoring

Edit `lab11_prompt_agents.py` and regenerate `lab11_walkthrough.ipynb`.
