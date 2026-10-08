# Foundry Agents Labs

One [Healthcare Marketplace use case](../USE-CASE.md), one synthetic data set,
one cumulative solution. Labs 1-10 progress from project/model setup to
operating hosted agents; optional Labs 11-14 compare platform-managed ownership
and additional protocols/tools.

Use the repository Python 3.14 dev container. Open the `.ipynb` listed below,
select `/usr/local/bin/python`, and run cells in order from that lab folder.
Read the adjacent README before each lab. **There is one learner run path:
the walkthrough notebook.**

Folders `lab1` through `lab14` each contain exactly one lab's notebook,
adjacent authoring source and README. Shared products and implementation helpers
live separately in [`../shared/`](../shared/README.md); a later lab reuses the
same product rather than carrying a duplicate.

## Where things run

The notebook authenticates, calls Azure, manages local Python subprocesses,
deploys prepared packages and inspects evidence. Microsoft Foundry builds and
runs the hosted Python product in a container. Local and deployed tests use the
same product code, but a local result is not evidence of deployed readiness.

Adjacent Python cell sources are internal authoring inputs, not alternate
terminal or interactive-cell learner entry points. Runtime files such as
`hosted/main.py` remain the code learners inspect and modify during exercises.

## Sequence and artifact chain

| # | Notebook | Prerequisite | Builds | Checkpoint |
|---|---|---|---|---|
| 1 | [Identity and project](lab1/lab1_walkthrough.ipynb) / [Guide](lab1/README.md) | Approved account and permissions | Project in an existing Foundry account | `artifacts/lab1/part_a.json` |
| 2 | [Models and verification](lab2/lab2_walkthrough.ipynb) / [Guide](lab2/README.md) | Lab 1 | Chat and embedding deployments | `artifacts/lab1/part_b.json`, `project.json` and verified settings persisted to the repository-root `.env` |
| 3 | [Tools and local testing](lab3/lab3_walkthrough.ipynb) / [Guide](lab3/README.md) | Lab 2; hosted-agent enablement | Typed-tool concierge over Responses and local tests | `artifacts/lab2/part_a.json` |
| 4 | [Deploy and invoke](lab4/lab4_walkthrough.ipynb) / [Guide](lab4/README.md) | Lab 3 | Hosted version and invocation | `artifacts/lab2/part_b.json`, `hosted.json`, `transcripts.md` |
| 5 | [Knowledge and retrieval](lab5/lab5_walkthrough.ipynb) / [Guide](lab5/README.md) | Lab 4; shared Search access | Search indexes, Foundry IQ knowledge and identity connection | `artifacts/lab3/part_a.json`, `knowledge.json` |
| 6 | [Sessions and resiliency](lab6/lab6_walkthrough.ipynb) / [Guide](lab6/README.md) | Lab 5 | External history and restart continuity | `artifacts/lab3/part_b.json`, `hosted.json`, `sessions/` |
| 7 | [Specialist orchestration](lab7/lab7_walkthrough.ipynb) / [Guide](lab7/README.md) | Lab 6 | Specialist workflow and bounded review | `artifacts/lab4/part_a.json` |
| 8 | [Advisor approval and recovery](lab8/lab8_walkthrough.ipynb) / [Guide](lab8/README.md) | Lab 7 | Advisor approval and pending-state recovery | `artifacts/lab4/part_b.json`, `handoff_packets/`, `hosted.json`, `sessions/` |
| 9 | [Tracing and evaluation](lab9/lab9_walkthrough.ipynb) / [Guide](lab9/README.md) | Lab 6; telemetry permissions | Tracing and measured evaluation baseline | `artifacts/lab5/part_a.json`, `eval_report.md`, `evaluation_bundle.json`, `pipeline.md` |
| 10 | [Release and rollback](lab10/lab10_walkthrough.ipynb) / [Guide](lab10/README.md) | Lab 9 | Release gate, promotion and rollback rehearsal | `artifacts/lab5/part_b.json`, `gate_result.json`, `release_plan.json` |
| 11 | [Prompt agents](lab11/lab11_walkthrough.ipynb) / [Guide](lab11/README.md) | Lab 6 | Platform prompt agents | `artifacts/stretch6/part_a.json` |
| 12 | [Workflows and delegation](lab12/lab12_walkthrough.ipynb) / [Guide](lab12/README.md) | Lab 11 | Platform workflows and hosted delegation | `artifacts/stretch6/part_b.json`, `agents.json`, `handoff_packets/S1.json` |
| 13 | [Invocations](lab13/lab13_walkthrough.ipynb) / [Guide](lab13/README.md) | Lab 2 | Structured denied-claim reviews | `artifacts/stretch7/part_a.json`, `invocations.json`, `claim_reviews/` |
| 14 | [Skills and Toolbox](lab14/lab14_walkthrough.ipynb) / [Guide](lab14/README.md) | Lab 13 | Skills and optional Toolbox | `artifacts/stretch7/part_b.json`, `skills_transcript.md` |

Each numbered lab can start in a fresh kernel. Its prerequisite cells validate
the producing lab's project/model scope, attendee suffix and evidence before
restoring required variables. Reuse checkpoints, cloud resources and the
products in `shared/`; do not rerun provisioning or evaluation merely to
restore kernel state. Changed inputs or source require fresh acceptance evidence.

Labs 9 and 11 reuse Lab 6's concierge and knowledge rather than requiring Lab 8.
Lab 8's packet metadata is optional evaluation context, not required input.
Lab 13 depends only on Lab 2's verified configuration; it does not require the
operations report or platform workflow.

Artifact directories `lab1` through `lab5`, `stretch6` and `stretch7` retain the
seven original topic namespaces. Their `part_a.json` and `part_b.json` files
are internal handoff names, **not learner lab numbers**. For example, Lab 5
publishes knowledge under `artifacts/lab3`, which Lab 6 reuses without rebuilding.
The cumulative final checkpoint contracts remain unchanged.

Missing a checkpoint? Reopen its producing notebook and rerun the required
cells. Check acceptance output as well as artifact existence; do not fabricate
files to bypass prerequisite gates.

## What you'll learn

### Labs 1-2: Foundry project and models

- Distinguish an administrator-owned account from a learner project.
- Choose supported chat/embedding deployment names, versions and capacity.
- Authenticate, provision, verify and persist configuration through editable notebook inputs.
- Explain separate management/data-plane permissions and quota constraints.

### Labs 3-4: Hosted basics

- Build an `Agent` on `FoundryChatClient` with typed `@tool` functions and shared compliance instructions.
- Serve Responses locally and invoke the deployed agent-specific OpenAI endpoint.
- Prepare a flat, pinned product package; explain Foundry's remote build, identity and immutable versions.
- Distinguish deploy and invoke roles and diagnose failed startup versus `session_not_ready`.

### Labs 5-6: Knowledge and session continuity

- Create Search indexes, knowledge sources, a Foundry IQ knowledge base and a managed-identity connection.
- Attach `MCPStreamableHTTPTool` using Entra authentication and verify grounded citations.
- Separate message history from session mapping and prove local restart continuity.
- Require shared Azure Blob history before claiming deployed replica/version continuity.

### Labs 7-8: Multi-agent handoff

- Build explicit fan-out/fan-in with `WorkflowBuilder`, custom executors and agent nodes.
- Bound compliance reflection to one revision and produce strict Pydantic handoff packets.
- Pause with `ctx.request_info` and accept an advisor decision on the next HTTP turn.
- Recover a pending packet after a local restart without claiming file-backed replica continuity.

### Labs 9-10: Operate

- Correlate notebook/hosted OpenTelemetry spans in Application Insights.
- Combine Groundedness/Relevance judges with deterministic policy evaluators.
- Fail closed on malformed evidence or a safety violation before promotion.
- Inspect version promotion, rollback and an opt-in OIDC cloud pipeline with protected environments.

### Labs 11-12: Platform-managed agents

- Create versioned `PromptAgentDefinition` and declarative workflow definitions.
- Explain why client-side function tools need a caller, while platform workflows need pre-fetched facts.
- Inspect workflow-action routing and delegate from the hosted concierge.
- Choose by ownership and lifecycle, not an assumed maturity or cost advantage.

### Labs 13-14: Invocations, Skills and Toolbox

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
Confirm identity permissions and propagation before the relevant lab. Lab 6's
restart demo should show two process IDs and the actual history backend.
Lab 9 must match a newly generated trace ID, not an old portal record.

Internal author tooling regenerates notebooks from the adjacent sources and
offline CI checks source alignment, contracts and regression tests. It is not
a learner execution route and does not deploy Azure. See [SETUP.md](../SETUP.md)
for administrator prerequisites, tracing permissions, cleanup ownership and
the fourteen source/notebook authoring pairs.
