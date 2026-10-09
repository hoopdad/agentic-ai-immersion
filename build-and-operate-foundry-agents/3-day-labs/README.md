# Foundry Agents Labs

One [Healthcare Marketplace use case](../USE-CASE.md), one synthetic data set,
one hosted-first curriculum. Core Labs 1-10 progress from project/model setup to
operating related hosted products; optional Labs 11-14 offer a short prompt comparison,
hosted-to-hosted delegation, and additional protocols/Skills.

Use the repository Python 3.14 dev container. Open the `.ipynb` listed below,
select `/usr/local/bin/python`, and run cells in order from that lab folder.
Read the adjacent README before each lab. **There is one learner run path:
the walkthrough notebook.**

Folders `lab01` through `lab14` each contain exactly one lab's notebook,
adjacent authoring source and README. Shared products and implementation helpers
live separately in [`../shared/`](../shared/README.md). Each boundary states
whether it continues, extends or branches from an accepted product.

Learner folders and filenames always use two digits (`lab01`, `lab02`, ...,
`lab14`) so alphabetical sorting matches progress. Displayed lab numbers and
the internal artifact namespaces below are not padded.

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
| 1 | [Identity and project](lab01/lab01_walkthrough.ipynb) / [Guide](lab01/README.md) | Approved account and permissions | Project in an existing Foundry account | `artifacts/lab1/part_a.json` |
| 2 | [Models and verification](lab02/lab02_walkthrough.ipynb) / [Guide](lab02/README.md) | Lab 1 | Chat and embedding deployments | `artifacts/lab1/part_b.json`, `project.json` and verified settings persisted to the repository-root `.env` |
| 3 | [Tools and local testing](lab03/lab03_walkthrough.ipynb) / [Guide](lab03/README.md) | Lab 2; hosted-agent enablement | Typed-tool concierge over Responses and local tests | `artifacts/lab2/part_a.json` |
| 4 | [Deploy and invoke](lab04/lab04_walkthrough.ipynb) / [Guide](lab04/README.md) | Lab 3 | Hosted version and invocation | `artifacts/lab2/part_b.json`, `hosted.json`, `transcripts.md` |
| 5 | [Knowledge and retrieval](lab05/lab05_walkthrough.ipynb) / [Guide](lab05/README.md) | Lab 4; shared Search access | Search indexes, Foundry IQ knowledge and identity connection | `artifacts/lab3/part_a.json`, `knowledge.json` |
| 6 | [Sessions and resiliency](lab06/lab06_walkthrough.ipynb) / [Guide](lab06/README.md) | Lab 5 | External history and restart continuity | `artifacts/lab3/part_b.json`, `hosted.json`, `sessions/` |
| 7 | [Specialist orchestration](lab07/lab07_walkthrough.ipynb) / [Guide](lab07/README.md) | Lab 6 | Specialist workflow and bounded review | `artifacts/lab4/part_a.json` |
| 8 | [Advisor approval and recovery](lab08/lab08_walkthrough.ipynb) / [Guide](lab08/README.md) | Lab 7 | Explicit advisor approval, local file-backed pending-state recovery and deployed triage acceptance | `artifacts/lab4/part_b.json`, `handoff_packets/`, `hosted.json`, `sessions/` |
| 9 | [Tracing and evaluation](lab09/lab09_walkthrough.ipynb) / [Guide](lab09/README.md) | Lab 6; telemetry permissions | Tracing and measured evaluation baseline | `artifacts/lab5/part_a.json`, `eval_report.md`, `evaluation_bundle.json`, `pipeline.md` |
| 10 | [Release and rollback](lab10/lab10_walkthrough.ipynb) / [Guide](lab10/README.md) | Lab 9 | Release gate, promotion and rollback rehearsal | `artifacts/lab5/part_b.json`, `gate_result.json`, `release_plan.json` |
| 11 | [Prompt versus hosted](lab11/lab11_walkthrough.ipynb) / [Guide](lab11/README.md) | Lab 4 | Short optional terminal comparison: one prompt version and invocation; no consumers | `artifacts/stretch6/part_a.json`, `prompt_agents.json`, `prompt_turn.json` |
| 12 | [Hosted-to-hosted delegation](lab12/lab12_walkthrough.ipynb) / [Guide](lab12/README.md) | **Lab 8 and Lab 9** | Isolated concierge extension calls the pinned hosted triage service; bounded failures and correlated evidence | `artifacts/hosted_delegation/part_a.json` |
| 13 | [Invocations](lab13/lab13_walkthrough.ipynb) / [Guide](lab13/README.md) | Lab 4 | Separate stateless structured denied-claim review product | `artifacts/stretch7/part_a.json`, `invocations.json`, `claim_reviews/` |
| 14 | [Skills and Toolbox](lab14/lab14_walkthrough.ipynb) / [Guide](lab14/README.md) | Lab 13 | Distinct Responses Skills service and optional preview Toolbox | `artifacts/stretch7/part_b.json`, `skills_transcript.md` |

### Guided route versus required dependencies

**Teach Labs 1-10 in order, then choose extensions.** Required prerequisites
below describe accepted inputs and prior concepts, not a suggested skip order.
Core completion includes Labs 8 and 10. Lab 11 is a short 10-15 minute
comparison; no other lab consumes its prompt. Lab 10 is recommended release
background before Lab 12, not a required checkpoint.

```text
Administrator prerequisites and dev container
`-- 01 Identity and project
    `-- 02 Models and verification
        `-- 03 Tools and local Responses testing
            `-- 04 Deploy and invoke hosted concierge
                +-- 05 Knowledge and retrieval
                |   `-- 06 Sessions and resiliency
                |       +-- 07 Hosted specialist orchestration
                |       |   `-- 08 Advisor approval and recovery --+
                |       `-- 09 Tracing and evaluation ------------+-- 12 Hosted-to-hosted
                |           `-- 10 Release and rollback                delegation [optional]
                +-- 11 Prompt versus hosted [optional, terminal]
                `-- 13 Stateless batch Invocations [optional]
                    `-- 14 Responses Skills / preview Toolbox [optional]
```

Lab 12 joins **both 8 and 9** and has no Lab 11 dependency.
Dependency-independent branches are learning choices, not parallel same-workspace
runtime instructions. Local hosts share port 8088, editable sources, deployment
targets and model quota. Stop the notebook-owned process before starting another
host; do not silently reuse a busy port or overwrite an evaluated candidate.

Each numbered lab can start in a fresh kernel. Its prerequisite cells validate
the producing lab's project/model scope, attendee suffix and evidence before
restoring required variables. Reuse checkpoints, cloud resources and the
products in `shared/`; do not rerun provisioning or evaluation merely to
restore kernel state. Changed inputs or source require fresh acceptance evidence.

Lab 9 reuses Lab 6's concierge and knowledge rather than requiring Lab 8.
Lab 8's packet metadata is optional evaluation context, not required input.
Labs 11 and 13 require Lab 4's deployed-hosting learning/evidence, not knowledge,
operations or MAF artifacts. Lab 12 restores Lab 6 transitively through Lab 8
and requires Lab 9's telemetry/evaluation context.

Artifact directories `lab1` through `lab5`, `stretch6` and `stretch7` retain the
original topic namespaces. Their `part_a.json` and `part_b.json` files
are internal handoff names, **not learner lab numbers**. For example, Lab 5
publishes knowledge under `artifacts/lab3`, which Lab 6 reuses without rebuilding.
Other topic mappings remain unchanged. Lab 12 publishes a new independent
`hosted_delegation/part_a.json`; old `stretch6/part_b.json` represents the
retired prompt-backed exercise and must be rejected, not upgraded or reused.

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
- Branch into the triage service, then pin its deployed version for optional Lab 12.
- Require an explicit simulated advisor decision; no agent may invent approval.

### Labs 9-10: Operate

- Correlate notebook/hosted OpenTelemetry spans in Application Insights.
- Combine Groundedness/Relevance judges with deterministic policy evaluators.
- Fail closed on malformed evidence or a safety violation before promotion.
- Inspect version promotion, rollback and an opt-in OIDC cloud pipeline with protected environments.

### Lab 11: Short prompt-versus-hosted comparison

- Compare one minimal versioned Prompt Agent and invocation with Lab 4's hosted Responses product.
- Explain platform-managed prompt ownership versus learner-owned Python/tools.
- Finish the comparison here: no prompt ensemble, graph or downstream consumers.

### Lab 12: Hosted-to-hosted delegation

- Reuse the Labs 7-8 triage service, not another specialist graph.
- Extend accepted concierge behavior in an isolated `shared/hosted-delegation/`
  candidate while preserving the exact Lab 9-10 measured core target.
- Inspect caller/callee identity and invocation access separately from model access.
- Bind case/session/participant identifiers in the application envelope; the
  delegation tool accepts no model arguments and disables automatic remote retries.
- Demonstrate bounded failure, explicit remote errors, case/session correlation
  and a deployed pending-case call with caller/callee trace evidence.
- Do not automatically relay advisor decisions, blindly retry state-changing
  calls, or claim distributed pending-state recovery.

### Labs 13-14: Invocations, Skills and Toolbox

- Contrast structured stateless Invocations with multi-turn Responses.
- Keep claim facts deterministic and bound the model to explanation fields.
- Branch from Lab 4's hosting concepts into the batch product; Lab 14 keeps
  its accepted evidence but introduces a separate Responses Skills service.
- Load a governed Skill's index first and body on demand.
- Attach optional preview Toolbox over MCP while keeping participant data out of web search.

## Teaching and evidence

Per-lab time boxes require rehearsal; the short Lab 11 comparison is not a
second full development track. Treat reasoning
capacity as Token Capital directed by people: connect each engineering decision
to Cost, Quality, Governance and Human-Agent Collaboration.

The exercises provide quality/control evidence, not cost-per-success results.
A schema-valid packet does not prove factual correctness; a citation does not
prove freshness; a local telemetry PASS does not prove ingestion; a release
gate PASS is not a production compliance certification.
Offline validation checks contracts and local behavior, not Azure readiness,
ingestion or preview availability. Label skipped live checks explicitly.

Labs 3-4 continue the same concierge. Labs 5-6 extend it with knowledge/history
and verify retained tool/policy behavior. Labs 7-8 branch into the triage product.
Labs 9-10 operate on the pinned Lab 6 concierge. Lab 12 branches into an isolated
extension candidate and needs fresh evaluation before a release claim.

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
