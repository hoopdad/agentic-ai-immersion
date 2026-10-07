# Build and Operate Foundry Agents

A notebook-first workshop for healthcare marketplace engineers building the
**Healthcare Marketplace Concierge** on Microsoft Foundry. Five core labs build
one cumulative solution; two stretch labs compare platform-managed agents and
additional hosted capabilities. All participant data is synthetic.

Start with [SETUP.md](SETUP.md), read the [use case](USE-CASE.md), and follow the
[lab sequence](labs/README.md). Use the repository Python 3.14 dev container and
select `/usr/local/bin/python` as the notebook kernel.

## Where things run

| Runtime | Responsibility |
|---|---|
| Learner notebook in the repository dev container | Editable configuration, authentication, provisioning, local process lifecycle, deployment, invocation, evaluation and checkpoint inspection |
| Microsoft Foundry | Project, model deployments, knowledge connections, versioned agents and hosted containers |
| Deployed Python product code | `hosted/main.py` and its pinned runtime dependencies; the notebook starts the same code locally before deployment |

**Notebook = the learner's cockpit; hosted Python = the product.** Run only the
walkthrough notebooks as a learner. Their programmatic subprocess calls manage
local servers and deployment tools; Python source files are not an alternative
learner run path.

## Agenda

| # | Notebook | Outcome | Evidence passed onward |
|---|---|---|---|
| 1 | `labs/lab1-foundry-project-models/lab1_walkthrough.ipynb` | Create a project in an existing admin-supplied Foundry account, provision chat and embedding deployments, verify access, persist downstream settings | `artifacts/lab1/project.json` and project/model configuration in the repository-root `.env` |
| 2 | `labs/lab2-hosted-agent-basics/lab2_walkthrough.ipynb` | Build a typed-tool concierge with shared compliance instructions; test locally, deploy and inspect an immutable version | `artifacts/lab2/hosted.json`, transcripts |
| 3 | `labs/lab3-hosted-knowledge-sessions/lab3_walkthrough.ipynb` | Build governed Foundry IQ knowledge and prove conversation continuity after a local restart; distinguish files from shared Blob history | `artifacts/lab3/knowledge.json`, `hosted.json`, sessions |
| 4 | `labs/lab4-hosted-multi-agent-handoff/lab4_walkthrough.ipynb` | Fan out to specialists, bound compliance reflection, and pause for advisor approval across HTTP turns | `artifacts/lab4/handoff_packets/`, `hosted.json` |
| 5 | `labs/lab5-operate-hosted-agents/lab5_walkthrough.ipynb` | Trace, evaluate, gate, inspect promotion and rollback; review an opt-in cloud pipeline | `artifacts/lab5/eval_report.md`, `gate_result.json`, `pipeline.md` |
| S6 | `labs/stretch6-prompt-agents-and-workflows/stretch6_walkthrough.ipynb` | Compare platform-managed prompt/workflow ownership with hosted code and delegate from the concierge | `artifacts/stretch6/agents.json`, handoff packet |
| S7 | `labs/stretch7-invocations-toolbox-skills/stretch7_walkthrough.ipynb` | Contrast structured Invocations with Responses; load governed Skills and optionally attach Toolbox | `artifacts/stretch7/invocations.json`, claim reviews, skills transcript |

Each hosted breakout retains teach, demo, exercise and checkpoint sections.
Read its README first, then execute notebook cells in order, including each
**YOUR TURN** acceptance gate. Readiness, deployment and live evaluation are
explicit notebook actions, not dev-container bootstrap or offline CI actions.

## Technical progression

| Lab | Engineering decision |
|---|---|
| 1 | Account versus project scope, model capacity, Entra identity and reproducible configuration |
| 2 | `FoundryChatClient`, typed `@tool` functions, `ResponsesHostServer`, flat packaging and immutable versions |
| 3 | Search indexes, knowledge sources, MCP authentication, governed citations and external message history |
| 4 | `WorkflowBuilder`, fan-out/fan-in, structured packets, bounded reflection, deterministic routing and human approval |
| 5 | OpenTelemetry, model-judged quality, deterministic safety checks, fail-closed gates and release ownership |
| S6 | `PromptAgentDefinition`, client tool execution, declarative workflows and delegated ownership |
| S7 | `InvocationsHostServer`, deterministic facts with bounded model explanations, progressive-disclosure Skills and optional MCP Toolbox |

## State and guardrails

Hosted containers may restart or scale out. Lab 3 demonstrates local restart
continuity with files, or shared message history with an existing Azure Blob
account/container. Azurite is an optional local Blob emulator, never a deployed
endpoint. Lab 4's pending-packet session map is file-backed: it supports a local
restart, not cross-replica or version-roll continuity. Lab 5 must inspect the
actual backend before claiming rollback preserves conversation history.

Every agent carries the shared compliance block: no plan recommendation or
ranking, no medical advice, data minimization, grounded facts and citations,
and licensed-advisor handoff for judgment. Sample gates provide acceptance
evidence, not production compliance certification or cost-per-outcome results.

## Configuration and recovery

The administrator supplies account details, permissions, network access and
shared Search/telemetry resources. Edit Lab 1's notebook inputs instead of
copying `.env` templates or running helper scripts. The notebook writes the root
`.env` for downstream persistence; do not commit it or generated artifacts.
Keep one unique attendee resource suffix throughout the sequence.

If a prerequisite artifact is missing, reopen its producing notebook and rerun
the required checkpoint cells. Do not fabricate artifacts or treat their
existence alone as a passing outcome. Follow the notebook cleanup guidance with
the facilitator after reviewing attendee-owned resource names; shared resources
remain under administrator ownership.

Administrators provisioning a complete environment choose an independent
Terraform root through [`infra/README.md`](infra/README.md):
[`privatelink/`](infra/privatelink/README.md) retains private endpoints/DNS and
virtual networking; [`public-network/`](infra/public-network/README.md) uses
public Foundry/data-service endpoints with Entra/RBAC and IP-restricted Key Vault/ACR.
Keep each deployment's state separate; this provisioning is not a learner notebook action.

## Authoring and provenance

Adjacent Python cell sources and `tools/py_to_ipynb.py` are internal notebook
authoring tools, not learner entry points. Authors edit those sources and
regenerate notebooks while preserving exercise gates. Runtime `.py` files are
deployable product code and may be edited during notebook-guided exercises.
The root dependency lock supplies workstation packages; hosted subsets use
matching pins.

For authors and offline CI only, the existing validator checks notebook/source
alignment, package contracts and offline regression tests without deploying Azure.

This command runs the internal offline workshop validation from the repository root.

```bash
python build-and-operate-foundry-agents/tools/validate_workshop.py
```

The validator discovers the infrastructure-contract tests for both Terraform
variants without authenticating, planning or deploying Azure resources. To run
only those dependency-free checks:

```bash
python -m unittest discover -s build-and-operate-foundry-agents/tests -p test_infra_network_variants.py -v
```

Live readiness still requires running the notebooks against the approved Azure
account and network. Preview surfaces are labeled; no offline result establishes
that a live deployment, workflow, Toolbox or telemetry ingestion succeeded.
