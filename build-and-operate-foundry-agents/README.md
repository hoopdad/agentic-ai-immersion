# Build and Operate Foundry Agents

A dev-container-first, Bash/Python lab sequence for individual healthcare marketplace engineers (Healthcare Marketplace) on **Microsoft
Foundry Hosted Agents**: your agent code, built and run as a container by Foundry, with the platform's
identity, versioning, knowledge and evaluation around it. Prompt Agents (platform-managed) appear once, as a
stretch lab, so the room can say when each fits.

* Four core breakouts of 60 minutes (teach 10, demo 10, do 35, checkpoint 5), each building on the
  artifacts of the previous one. Two stretch breakouts for fast finishers and follow-up.
* One use case throughout: the **Healthcare Marketplace Concierge** (`USE-CASE.md`). Same synthetic
  data, same five agent roles, same compliance block, same three scenarios (S1 AEP shopper, S2 denied
  claim, S3 pre-Medicare across both LOBs) in every lab.
* Integrates with the base repo `github.com/dhangerkapil/agentic-ai-immersion` (fork `hoopdad/agentic-ai-immersion`)
  as a new folder. Reuses its dev container, `.env` variable names, pinned requirements, RBAC script and
  the prerequisites datasheet. Its hosted-agent samples (`hosted-agents/`, `AgentOps/`) are the patterns
  these labs extend.
* Learn alignment: "Develop AI agents on Azure" (AI-3026). Each lab README names the modules it maps to.

## Where things run

| Runtime | What runs there |
|---|---|
| **Learner workstation**: VS Code with the base repo dev container (Docker Desktop) or GitHub Codespaces | The `labN_walkthrough.ipynb` notebooks and `labN_*.py` driver scripts. The Jupyter kernel is the dev container's Python. They sign in with `az login`, call the Foundry project over HTTPS, build the knowledge base, start and kill `hosted/main.py` as a local process on port 8088, deploy with `azd`, call endpoints, evaluate, read results. Nothing customer-facing runs here. |
| **Microsoft Foundry (Azure)** | Hosted agents run as containers Foundry builds from the ZIP `azd` uploads, then runs, versions and scales. That code is plain `.py` (`main.py` + `requirements.txt` + vendored `common/` and `data/`), never a notebook. The same `main.py` runs locally for testing. Knowledge bases, evals, tracing and (in Stretch 5) prompt and workflow agents also live in the project. |

Rule of thumb the labs teach: **notebook = the learner's cockpit, `hosted/main.py` = the product.** Every
lab ships both. Conversation history lives outside the agent process: Lab 2 uses Azure Blob when configured or
local files. Lab 3 uses a file-backed session map for local restart continuity. Shared storage utilities retain
optional Redis/Cosmos backends for configurations that explicitly use them.

## Agenda

| # | Breakout | Agent type | Builds | Artifact for the next lab |
|---|---|---|---|---|
| 1 | Hosted agent basics | Hosted (Responses) | Agent Framework `Agent` + `FoundryChatClient` + three `@tool` functions over the systems of record, compliance block, `ResponsesHostServer`; run locally, `azd ai agent init` + `azd up`, invoke the deployed version through its agent-specific endpoint, read version status and logs | `artifacts/lab1/hosted.json` |
| 2 | Knowledge and session storage | Hosted + Foundry IQ | Foundry IQ knowledge base from the bounded-context docs (notebook), then v2 of the agent: knowledge over MCP with the container's identity, plan tools, and **session storage for resiliency** (optional Azure Blob history, local file fallback). Kill the process, restart, the third turn remembers. Verify shared history across replicas when Azure Blob is configured | `artifacts/lab2/knowledge.json`, `hosted.json` |
| 3 | Multi-agent triage with advisor handoff | Hosted, multi-agent | Workflow inside the container: intake classifies LOB, marketplace and accounts specialists in parallel, compliance reflection (revise once), strict JSON handoff packet. **Human approval across HTTP turns**: the packet returns `pending_advisor_approval`, the advisor's next turn approves, revises or declines; a file-backed session map supports local process restart, not cross-replica or version-roll continuity | `artifacts/lab3/handoff_packets/*.json` |
| 4 | Operate hosted agents | Hosted, operations | Tracing from the container to Application Insights; evaluation of the hosted endpoint over 18 golden questions (groundedness, relevance, custom no-recommendation and PII-leak checks); versions, promote, roll back with azd; `eval_gate.py` and a GitHub Actions pipeline: validate, gate, deploy dev, smoke, manual promote, rollback | `artifacts/lab4/eval_report.md`, `pipeline.md` |
| S5 | Prompt agents and workflow agents | Prompt (platform-managed) | Condensed tour: `healthcare-marketplace-concierge` prompt agent with function tools, specialists, the YAML workflow agent (preview); then the hosted agent gets a `run_triage_workflow` tool that calls it. Teach: platform-managed versus hosted, and when each fits | `artifacts/stretch5/agents.json` |
| S6 | Invocations protocol, Toolbox, Skills | Hosted (Invocations) | `healthcare-marketplace-claims-review-invocations`: structured request in, one review packet per denied claim out; the Responses concierge with a bundled Skill (`SKILL.md`) and an optional Foundry Toolbox (preview). Two-protocol comparison | `artifacts/stretch6/invocations.json` |

Full agenda rows, "What you'll learn" per lab, the one-line technical feature roll-up, the artifact chain,
facilitator notes and "what was cut and why": `labs/README.md`.

## Technical features taught, by lab

Each lab README has a "Technical features taught" table (feature, Foundry / SDK object, where in the code,
why it matters for Healthcare Marketplace). The short version:

| Lab | Features |
|---|---|
| 1 | `FoundryChatClient` with Entra identity; `Agent` with `@tool` typed functions; `ResponsesHostServer`; `default_options={"store": False}`; flat deployable folder with vendored `common/` and `data/`; `azd ai agent init --protocol responses --deploy-mode code --dep-resolution remote_build` + `azd up`; `POST /responses` locally; `get_openai_client(agent_name=...)` against the deployed version's endpoint; version status, logs, 424 `session_not_ready` |
| 2 | Azure AI Search index (vector + semantic, Entra embeddings), knowledge sources, Foundry IQ knowledge base, project connection with `ProjectManagedIdentity`; `MCPStreamableHTTPTool` with an `httpx.Auth` Entra bearer; `common.message_store` (Azure Blob/Azurite or file) as the agent's history provider; `common.session_store` map; kill/restart/resume demo; env-driven config via `azd env set` |
| 3 | `WorkflowBuilder` graph; custom `Executor` + `@handler`; fan-out with `ctx.send_message(target_id=...)` and a counting fan-in; `AgentExecutor` nodes; Pydantic `response_format`; bounded reflection with `guardrails.contains_recommendation`; `ctx.request_info` + `@response_handler` + `workflow.run(responses=...)`; agent middleware routing turns; pending packet in the session store |
| 4 | `APPLICATIONINSIGHTS_CONNECTION_STRING` + `configure_azure_monitor` in the container; OpenTelemetry spans around each eval question; `azure-ai-evaluation` Groundedness and Relevance with keyless model config; custom deterministic evaluators; hosted endpoint as the eval target; optional Foundry eval run; `eval_gate.py`; `azd` versions, promote, rollback; GitHub Actions with OIDC and Environments |
| S5 | `project.agents.create_version` + `PromptAgentDefinition`; `FunctionTool` from shared schemas; `MCPTool` with a project connection; client-side function-call loop; `WorkflowAgentDefinition` YAML (`InvokeAzureAgent`, `ConditionGroup`); streaming `workflow_action` events; hosted `@tool` delegating to a platform workflow |
| S6 | `InvocationsHostServer`; deterministic facts + bounded model output with `response_format`; KB text parsed into rules; `skills/<name>/SKILL.md` with progressive disclosure; Foundry Toolbox over MCP (preview); two protocols, one deploy path |

## Session storage for resiliency

Hosted agent containers are stateless by design: Foundry restarts them on every version roll and runs as
many replicas as load needs. Two things must therefore live outside the container, and the labs put both
in `common/`:

* `common/message_store.py`: conversation history the agent reads and appends each turn. Lab 2 uses optional
  Azure Blob Storage (or local Azurite), with files under `labs/artifacts/` as its fallback. The shared helper
  retains Redis support for configurations that explicitly use it.
* `common/session_store.py`: the session map, the one fact the client must never lose: session id to
  conversation, last response id, turn count, and in Lab 3 the pending handoff packet. The shared helper
  supports file, Redis or Cosmos DB backends; Lab 3 uses files.

Lab 2 proves local continuity (two turns, kill the process, restart, the third turn remembers); Azure Blob
supports continuity across deployed replicas and version rolls. Lab 3 proves local process-restart continuity
with its file-backed session map. Lab 4 shows rollback with sessions untouched.

## Folder map

```
build-and-operate-foundry-agents/
  README.md                this file
  USE-CASE.md              use case spec, scenarios S1-S3, agent roles
  SETUP.md                 environment: where things run, env vars, models, connections, RBAC, verification, proctor checklist
  common/                  marketplace_data (systems of record over JSON), foundry_env, guardrails, session_store, message_store
  data/                    synthetic participants, sponsors, plans, HRA accounts, 9 knowledge docs, golden questions, call transcripts
  tools/py_to_ipynb.py     stdlib converter: `# %%` script -> notebook (how every labN_walkthrough.ipynb is produced)
  labs/
    README.md              sequence overview, agenda, what you'll learn, features by lab, artifact chain, facilitator notes
    lab1-hosted-agent-basics/          lab1_hosted_basics.py, lab1_walkthrough.ipynb, hosted/ (main.py, prepare.py, test_local.py, requirements.txt)
    lab2-hosted-knowledge-sessions/    lab2_hosted_knowledge.py, knowledge_base.py, lab2_walkthrough.ipynb, hosted/
    lab3-hosted-multi-agent-handoff/   lab3_hosted_multi_agent.py, lab3_walkthrough.ipynb, hosted/ (main.py, marketplace_specialists.py, marketplace_workflow.py, ...)
    lab4-operate-hosted-agents/        lab4_operate.py, eval_gate.py, promote.py, .github/workflows/agent-ci.yml, envs/, infra/
    stretch5-prompt-agents-and-workflows/  stretch5_prompt_agents.py, marketplace_triage_workflow.yaml, hosted_tool_snippet.py
    stretch6-invocations-toolbox-skills/   stretch6_invocations.py, hosted-invocations/, hosted-responses-skills/, skills/
    artifacts/             what each lab writes and the next lab reads
    catch_up.py            `python catch_up.py --through N` rebuilds artifacts so anyone can start lab N+1 fresh
```

## Running a lab

1. Complete `SETUP.md`: models deployed, AI Search and Application Insights connections, roles assigned
   (Foundry Project Manager to deploy hosted agents, Foundry User or Agent Consumer to invoke), `azd` with
   the `azure.ai.agents` extension, `.env` filled. Set `MARKETPLACE_TODAY=2026-10-06` so enrollment-window
   answers are the same across the room. The optional Redis setting is for generic shared-store configurations;
   Labs 2 and 3 and Stretch 6 do not use it.
2. Open the lab folder in VS Code. Read the README's Teach section while the facilitator presents.
3. Run `labN_walkthrough.ipynb` cell by cell, or the `.py` driver top to bottom. Do the "YOUR TURN" items
   in the time boxes. Every `hosted/` folder also runs standalone: `python hosted/main.py` on port 8088.
4. Confirm the checkpoint artifact exists. Paste the requested output into the room chat. Behind?
   `python labs/catch_up.py --through N`.

## Guardrails every agent carries

The same compliance block (`common/guardrails.py`) is appended to every agent's instructions: not a
licensed advisor, never recommend or rank plans, offer the advisor handoff, data minimization (no full
SSN, MBI or card numbers), tools and knowledge only, cite knowledge doc ids, plain language, no medical
advice. Lab 4 turns it into a pass/fail evaluator and a release gate.

## Before delivery

Nothing here ran against a live Foundry project (no SDKs in the authoring environment). Run the
five-minute verification and the proctor smoke test in `SETUP.md` the day before. Preview surfaces
(workflow agents, Toolbox, Skills registration) are labeled preview, and every SDK call whose signature
was not confirmed against current docs carries a `# VERIFY` comment; the two writer-notes files list them.
All customer-facing data in `data/` is synthetic.


## Start here

Follow [SETUP.md](SETUP.md), then open the [lab sequence](labs/README.md).
The repository dev container supplies Python 3.14, Bash, PowerShell for shared RBAC setup,
Azure CLI, azd, Jupyter, Redis and Azurite companion services. No separate workshop virtual environment
is required. Use the root `.env` and dependency lock.

Run offline validation from the repository root:

```bash
python build-and-operate-foundry-agents/tools/validate_workshop.py
```

Azure deployment and live evaluations are explicit actions, not part of bootstrap or offline CI.
Lab 4's nested workflow is a template; see its README before installing it.

## Authoring and provenance

The six walkthrough notebooks are generated from their adjacent `# %%` Python scripts.
Preserve the executable learner gates when editing; regenerate with `tools/py_to_ipynb.py`.
Run `azd ai agent init` in an individual prepared hosted folder rather than at the workshop root.
Presentation decks and slide-build plans are not part of this lab repository.
Live service claims still require the lab's preflight and Azure checks.
Every attendee sets `MARKETPLACE_RESOURCE_SUFFIX` once in the root `.env`; every resource the labs
create uses that suffix. After the workshop, use the dry-run-first cleanup commands in
[`SETUP.md`](SETUP.md#10-clean-up-workshop-resources) to remove one attendee's resources or all
workshop resources without deleting shared infrastructure.
