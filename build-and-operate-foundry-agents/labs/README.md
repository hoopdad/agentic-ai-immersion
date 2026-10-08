# Foundry Agents Labs

One [Healthcare Marketplace use case](../USE-CASE.md), one synthetic data set,
one cumulative solution. Five core labs progress from project/model setup to
operating hosted agents; two stretch labs compare platform-managed ownership
and additional protocols/tools.

Use the repository Python 3.14 dev container. Open the `.ipynb` listed below,
select `/usr/local/bin/python`, and run cells in order from that lab folder.
Read the adjacent README before each lab. **There is one learner run path:
the walkthrough notebook.**

## Where things run

The notebook authenticates, calls Azure, manages local Python subprocesses,
deploys prepared packages and inspects evidence. Microsoft Foundry builds and
runs the hosted Python product in a container. Local and deployed tests use the
same product code, but a local result is not evidence of deployed readiness.

Adjacent Python cell sources are internal authoring inputs, not alternate
terminal or interactive-cell learner entry points. Runtime files such as
`hosted/main.py` remain the code learners inspect and modify during exercises.

## Sequence and artifact chain

| # | Notebook | Builds | Checkpoint |
|---|---|---|---|
| 1A | [Identity and project](lab1-foundry-project-models/lab1a_walkthrough.ipynb) | Project in an existing Foundry account | `artifacts/lab1/part_a.json` |
| 1B | [Models and verification](lab1-foundry-project-models/lab1b_walkthrough.ipynb) | Chat and embedding deployments | `artifacts/lab1/part_b.json`, `project.json` and verified settings persisted to the repository-root `.env` |
| 2A | [Tools and local testing](lab2-hosted-agent-basics/lab2a_walkthrough.ipynb) | Typed-tool concierge over Responses and local tests | `artifacts/lab2/part_a.json` |
| 2B | [Deploy and invoke](lab2-hosted-agent-basics/lab2b_walkthrough.ipynb) | Hosted version and invocation | `artifacts/lab2/part_b.json`, `hosted.json`, `transcripts.md` |
| 3A | [Knowledge and retrieval](lab3-hosted-knowledge-sessions/lab3a_walkthrough.ipynb) | Search indexes, Foundry IQ knowledge and identity connection | `artifacts/lab3/part_a.json`, `knowledge.json` |
| 3B | [Sessions and resiliency](lab3-hosted-knowledge-sessions/lab3b_walkthrough.ipynb) | External history and restart continuity | `artifacts/lab3/part_b.json`, `hosted.json`, `sessions/` |
| 4A | [Specialist orchestration](lab4-hosted-multi-agent-handoff/lab4a_walkthrough.ipynb) | Specialist workflow and bounded review | `artifacts/lab4/part_a.json` |
| 4B | [Advisor approval and recovery](lab4-hosted-multi-agent-handoff/lab4b_walkthrough.ipynb) | Advisor approval and pending-state recovery | `artifacts/lab4/part_b.json`, `handoff_packets/`, `hosted.json`, `sessions/` |
| 5A | [Tracing and evaluation](lab5-operate-hosted-agents/lab5a_walkthrough.ipynb) | Tracing, evaluation and release gate | `artifacts/lab5/part_a.json`, `eval_report.md`, `gate_result.json` |
| 5B | [Release and rollback](lab5-operate-hosted-agents/lab5b_walkthrough.ipynb) | Operating runbook, promotion and rollback | `artifacts/lab5/part_b.json`, `pipeline.md` |
| S6A | [Prompt agents](stretch6-prompt-agents-and-workflows/stretch6a_walkthrough.ipynb) | Platform prompt agents | `artifacts/stretch6/part_a.json` |
| S6B | [Workflows and delegation](stretch6-prompt-agents-and-workflows/stretch6b_walkthrough.ipynb) | Platform workflows and hosted delegation | `artifacts/stretch6/part_b.json`, `agents.json`, `handoff_packets/S1.json` |
| S7A | [Invocations](stretch7-invocations-toolbox-skills/stretch7a_walkthrough.ipynb) | Structured denied-claim reviews | `artifacts/stretch7/part_a.json`, `invocations.json`, `claim_reviews/` |
| S7B | [Skills and Toolbox](stretch7-invocations-toolbox-skills/stretch7b_walkthrough.ipynb) | Skills and optional Toolbox | `artifacts/stretch7/part_b.json`, `skills_transcript.md` |

Each A/B pair runs in order but does not share kernel state: B reads A's validated
`part_a.json` in a fresh kernel, restores required locals, and writes
`part_b.json`. Do not run A from B or rerun provisioning/evaluation solely to
restore variables. The original cumulative final checkpoints remain unchanged.

Lab 1 supplies configuration for every later notebook. Lab 2 supplies the
concierge baseline for Lab 3. Lab 3's hosted and knowledge checkpoints feed Lab 4,
Lab 5 and Stretch 6. Lab 5 evaluates the Lab 3 concierge; Lab 4's packet metadata
is optional, not required evaluation input. Stretch 7 shares the setup and
packaging conventions rather than depending on Lab 5's report.

Missing a checkpoint? Reopen its producing notebook and rerun the required
cells. Check acceptance output as well as artifact existence; do not fabricate
files to bypass prerequisite gates.

## What you'll learn

### Lab 1: Foundry project and models

- Distinguish an administrator-owned account from a learner project.
- Choose supported chat/embedding deployment names, versions and capacity.
- Authenticate, provision, verify and persist configuration through editable notebook inputs.
- Explain separate management/data-plane permissions and quota constraints.

### Lab 2: Hosted basics

- Build an `Agent` on `FoundryChatClient` with typed `@tool` functions and shared compliance instructions.
- Serve Responses locally and invoke the deployed agent-specific OpenAI endpoint.
- Prepare a flat, pinned product package; explain Foundry's remote build, identity and immutable versions.
- Distinguish deploy and invoke roles and diagnose failed startup versus `session_not_ready`.

### Lab 3: Knowledge and session continuity

- Create Search indexes, knowledge sources, a Foundry IQ knowledge base and a managed-identity connection.
- Attach `MCPStreamableHTTPTool` using Entra authentication and verify grounded citations.
- Separate message history from session mapping and prove local restart continuity.
- Require shared Azure Blob history before claiming deployed replica/version continuity.

### Lab 4: Multi-agent handoff

- Build explicit fan-out/fan-in with `WorkflowBuilder`, custom executors and agent nodes.
- Bound compliance reflection to one revision and produce strict Pydantic handoff packets.
- Pause with `ctx.request_info` and accept an advisor decision on the next HTTP turn.
- Recover a pending packet after a local restart without claiming file-backed replica continuity.

### Lab 5: Operate

- Correlate notebook/hosted OpenTelemetry spans in Application Insights.
- Combine Groundedness/Relevance judges with deterministic policy evaluators.
- Fail closed on malformed evidence or a safety violation before promotion.
- Inspect version promotion, rollback and an opt-in OIDC cloud pipeline with protected environments.

### Stretch 6: Platform-managed agents

- Create versioned `PromptAgentDefinition` and declarative workflow definitions.
- Explain why client-side function tools need a caller, while platform workflows need pre-fetched facts.
- Inspect workflow-action routing and delegate from the hosted concierge.
- Choose by ownership and lifecycle, not an assumed maturity or cost advantage.

### Stretch 7: Invocations, Skills and Toolbox

- Contrast structured stateless Invocations with multi-turn Responses.
- Keep claim facts deterministic and bound the model to explanation fields.
- Load a governed Skill's index first and body on demand.
- Attach optional preview Toolbox over MCP while keeping participant data out of web search.

## Teaching and evidence

Hosted breakouts retain teach 10, demo 10, do 35 and checkpoint 5 minute time
boxes; follow-up exercises may exceed a single breakout. Treat reasoning
capacity as Token Capital directed by people: connect each engineering decision
to Cost, Quality, Governance and Human-Agent Collaboration.

The exercises provide quality/control evidence, not cost-per-success results.
A schema-valid packet does not prove factual correctness; a citation does not
prove freshness; a local telemetry PASS does not prove ingestion; a release
gate PASS is not a production compliance certification.

## Facilitator and author guidance

Rehearse the same notebook path on the approved Azure account and network.
Confirm identity permissions and propagation before the relevant lab. Lab 3's
restart demo should show two process IDs and the actual history backend.
Lab 5 must match a newly generated trace ID, not an old portal record.

Internal author tooling regenerates notebooks from the adjacent sources and
offline CI checks source alignment, contracts and regression tests. It is not
a learner execution route and does not deploy Azure. See [SETUP.md](../SETUP.md)
for administrator prerequisites, tracing permissions, cleanup ownership and
the fourteen source/notebook authoring pairs.
