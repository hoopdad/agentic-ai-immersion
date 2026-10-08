# Stretch 6: Prompt agents and a declarative workflow

| | |
|---|---|
| Goal | Build platform-managed concierge/specialist prompt agents and a declarative triage workflow, then delegate to it from the hosted concierge |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab3/knowledge.json` and Lab 1 configuration |
| Notebooks | [Stretch 6A](stretch6a_walkthrough.ipynb), then [Stretch 6B](stretch6b_walkthrough.ipynb) in a fresh kernel |
| Produces | `artifacts/stretch6/agents.json`, `workflow.yaml`, `handoff_packets/S1.json` |

Open these notebooks with the repository dev-container `/usr/local/bin/python`
kernel and run cells in order. It creates and invokes platform-managed agents.
`hosted_tool_snippet.py` is product integration code for Lab 3's container;
`stretch6_prompt_agents.py` is internal notebook source, not a learner driver.

## Two independently runnable halves

| Half | Scope | Durable checkpoint |
|---|---|---|
| 6A (25 min) | Publish prompt agents only, client-side function tools, portal instruction exercise and restoration | `artifacts/stretch6/part_a.json`, `prompt_agents.json`, tool/portal evidence |
| 6B (35 min) | Reuse A's prompt names/IDs, create only the workflow, test routing and hosted delegation, deploy the edited Lab 3 package | `artifacts/stretch6/part_b.json` and original `agents.json`/`workflow.yaml`/handoff packet |

B imports definitions without rerunning A and refuses missing, modified, or differently scoped evidence.
Rerunning an A action invalidates both completion checkpoints; rerunning B invalidates its checkpoint until success.
Each risky cell clears its acceptance outcome before execution, and publication requires every intended current gate.
It never republishes A's prompt agents. The original `build()` remains the internal cumulative publishing API.
The adjacent paired cell sources are `stretch6a_prompt_agents.py` and `stretch6b_workflows_delegation.py`.

## What you'll learn

- Create versioned `PromptAgentDefinition` agents with shared function schemas
  and knowledge through a project-connected `MCPTool`.
- Run the notebook's client-side function-call loop and explain why a platform
  workflow needs facts fetched by its caller.
- Inspect a preview `WorkflowAgentDefinition`, YAML routing and streamed actions.
- Choose platform-managed versus hosted by ownership/lifecycle, not an assumed
  maturity ladder or cost advantage.
- Register one hosted tool that calls the platform workflow.

## Technical features taught

| Feature | Implementation | Ownership lesson |
|---|---|---|
| Versioned prompt definitions | `project.agents.create_version`, `PromptAgentDefinition` | Instructions can change without rebuilding a container |
| Shared function tools | `marketplace_data.TOOL_SCHEMAS`, `FunctionTool` | One fact schema for hosted and platform agents |
| Governed MCP knowledge | `MCPTool` with project connection | The same reviewed KB serves both implementations |
| Client tool execution | Notebook Responses function-call loop | The client runs Python; the platform cannot run arbitrary client tools |
| Declarative workflow | YAML `InvokeAzureAgent`, `ConditionGroup` | Routing and responsible agents are inspectable |
| Streaming actions | `workflow_action` events | Execution trail must be checked against the intended route |
| Hosted delegation | `@tool run_triage_workflow` and `agent_reference` | Hosted code owns the conversation; platform workflow owns its delegated path |

## Teach (10 min)

A prompt agent is a versioned definition; a hosted agent is your Python product.
Business-owned regulated wording may fit platform management, while custom
state, middleware, dependencies or Invocations fit hosted code. Both need
acceptance evidence.

A workflow cannot satisfy a client-side function call without a caller.
The notebook/hosted tool pre-fetches a `TRIAGE CASE` fact envelope, then specialists
use it with knowledge. The definition makes ownership reusable and visible,
but does not itself establish correct execution or lower reasoning cost.

Workflow YAML is preview: keep it small and verify the selected service surface
before the session. Regulated instructions still require a human owner and review.

## Demo (10 min)

1. Run notebook agent/workflow creation cells and inspect recorded versions.
2. Run the concierge tool-loop cell: distinguish platform requests from locally
   executed fact tools.
3. Run S1 and inspect the required `triage -> marketplace -> compliance -> handoff`
   action trail; the accounts branch must not run.
4. Inspect the saved packet and the graph in Foundry. A version change in the
   portal does not require rebuilding the hosted container.
5. Read the hosted integration snippet and identify its single delegated call.

## Do (35 min)

1. Build agents/workflow through notebook cells and inspect `agents.json`.
2. Run concierge and S1 cells; require enrollment facts, no recommendation, the
   correct branch and a valid safe packet.
3. Inspect facts/sources, neutral options and advisor process steps. Workflow
   errors, action-order errors or invalid packets must not be presented as success.
4. **YOUR TURN: portal instruction edit.** Run the greeting gate for Evelyn;
   it checks safety and restores canonical instructions during cleanup.
5. **YOUR TURN: broken router.** Run the temporary accounts-route gate, explain
   unanswered marketplace questions and confirm canonical routing is restored.
6. **YOUR TURN: hosted delegation.** Integrate `hosted_tool_snippet.py` in Lab 3
   `hosted/main.py`, register `run_triage_workflow` in `FUNCTION_TOOLS` and add its
   instruction. Run the notebook gate before redeploying Lab 3 through its notebook.
   Require completed status and packet validation; temporary conversations are cleaned up.
7. After redeployment, ask as P-1005 for an ACA plan recommendation and inspect
   the advisor handoff. Use the Lab 3 concierge, not Lab 4's triage product.

Configure the workflow reference through the notebook inputs/product integration.
Do not create a separate hosted package or copy generated credentials/state into
the package to make delegation work.

## Checkpoint (5 min)

Share S1's action trail and LOB result. Execution events alone are not outcome
acceptance: route, packet and safety checks determine success.
`artifacts/stretch6/agents.json` records the workflow reference used by delegation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Creation 401/403 | Check notebook authentication, tenant/project permissions and propagation |
| Missing KB endpoint/connection | Return to Lab 3's knowledge/connection cells and verify its checkpoint |
| YAML creation failure | Inspect the preview field/Power Fx helper against the selected service version |
| Unanswered function call | Ensure the caller supplies case facts rather than assigning client tools to a workflow specialist |
| Packet problems | Inspect strict field/types/source/safety validation; tighten instructions and rerun |
| Hosted delegation unavailable | Supply the recorded workflow name/reference through notebook configuration and rebuild the product |
| Delegation failed | Inspect invocation, packet and cleanup errors; do not relabel failure as a handoff |

## Follow-up and author validation

Explore a bounded YAML revise branch after compliance and rerun S1 with a
deliberately unsafe specialist instruction. Internal offline regression tests
cover workflow rendering, packet validation and action order; they are not a
second learner execution path or live Azure proof.

- [Azure agent learning path](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/)
- [Foundry workflows](https://learn.microsoft.com/azure/foundry/agents/how-to/workflows)
