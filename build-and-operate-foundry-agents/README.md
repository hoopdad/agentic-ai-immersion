# Build and Operate Foundry Agents

A notebook-first workshop for healthcare marketplace engineers building the
**Healthcare Marketplace Concierge** on Microsoft Foundry. Labs 1-10 build
one cumulative solution; optional Labs 11-14 compare platform-managed agents and
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
| 1 | [Identity and project](labs/lab01/lab01_walkthrough.ipynb) | Create a project in an existing admin-supplied Foundry account | `artifacts/lab1/part_a.json` |
| 2 | [Models and verification](labs/lab02/lab02_walkthrough.ipynb) | Provision chat and embedding deployments, verify access, persist downstream settings | `artifacts/lab1/part_b.json`, `project.json` and project/model configuration in the repository-root `.env` |
| 3 | [Tools and local testing](labs/lab03/lab03_walkthrough.ipynb) | Build a typed-tool concierge with shared compliance instructions and test locally | `artifacts/lab2/part_a.json` |
| 4 | [Deploy and invoke](labs/lab04/lab04_walkthrough.ipynb) | Deploy and inspect an immutable version | `artifacts/lab2/part_b.json`, `hosted.json`, transcripts |
| 5 | [Knowledge and retrieval](labs/lab05/lab05_walkthrough.ipynb) | Build governed Foundry IQ knowledge | `artifacts/lab3/part_a.json`, `knowledge.json` |
| 6 | [Sessions and resiliency](labs/lab06/lab06_walkthrough.ipynb) | Prove conversation continuity after a local restart; distinguish files from shared Blob history | `artifacts/lab3/part_b.json`, `hosted.json`, sessions |
| 7 | [Specialist orchestration](labs/lab07/lab07_walkthrough.ipynb) | Fan out to specialists and bound compliance reflection | `artifacts/lab4/part_a.json` |
| 8 | [Advisor approval and recovery](labs/lab08/lab08_walkthrough.ipynb) | Pause for advisor approval across HTTP turns and recover pending state | `artifacts/lab4/part_b.json`, `handoff_packets/`, `hosted.json` |
| 9 | [Tracing and evaluation](labs/lab09/lab09_walkthrough.ipynb) | Trace and evaluate once, preserving measured results | `artifacts/lab5/part_a.json`, `eval_report.md`, `evaluation_bundle.json`, `pipeline.md` |
| 10 | [Release and rollback](labs/lab10/lab10_walkthrough.ipynb) | Gate the measured results; rehearse promotion and rollback without deployment | `artifacts/lab5/part_b.json`, `gate_result.json`, `release_plan.json` |
| 11 | [Prompt agents](labs/lab11/lab11_walkthrough.ipynb) | Compare platform-managed prompt ownership with hosted code | `artifacts/stretch6/part_a.json` |
| 12 | [Workflows and delegation](labs/lab12/lab12_walkthrough.ipynb) | Compare workflow ownership and delegate from the concierge | `artifacts/stretch6/part_b.json`, `agents.json`, handoff packet |
| 13 | [Invocations](labs/lab13/lab13_walkthrough.ipynb) | Contrast structured Invocations with Responses | `artifacts/stretch7/part_a.json`, `invocations.json`, claim reviews |
| 14 | [Skills and Toolbox](labs/lab14/lab14_walkthrough.ipynb) | Load governed Skills and optionally attach Toolbox | `artifacts/stretch7/part_b.json`, skills transcript |

Follow Labs 1-14 using the [prerequisite table](labs/README.md#sequence-and-artifact-chain).
Labs 9 and 11 branch from Lab 6; Lab 13 needs only Lab 2, so optional topics need
not replay unrelated work. Each notebook can start in a fresh kernel and restores
validated predecessor evidence instead of repeating provisioning or evaluation.
Each folder `labs/lab01` through `labs/lab14` holds exactly one walkthrough,
its adjacent authoring source and its own README. Reusable product code and
internal helpers live outside learner folders in [`shared/`](shared/README.md).
Existing `artifacts/lab1` through `lab5`,
`stretch6`, `stretch7` and `part_a.json`/`part_b.json` names remain internal
compatibility contracts, not learner lab numbers.

Each hosted breakout retains teach, demo, exercise and checkpoint sections.
Read its README first, then execute notebook cells in order, including each
**YOUR TURN** acceptance gate. Readiness, deployment and live evaluation are
explicit notebook actions, not dev-container bootstrap or offline CI actions.

## Technical progression

| Lab | Engineering decision |
|---|---|
| 1-2 | Account versus project scope, model capacity, Entra identity and reproducible configuration |
| 3-4 | `FoundryChatClient`, typed `@tool` functions, `ResponsesHostServer`, flat packaging and immutable versions |
| 5-6 | Search indexes, knowledge sources, MCP authentication, governed citations and external message history |
| 7-8 | `WorkflowBuilder`, fan-out/fan-in, structured packets, bounded reflection, deterministic routing and human approval |
| 9-10 | OpenTelemetry, model-judged quality, deterministic safety checks, fail-closed gates and release ownership |
| 11-12 | `PromptAgentDefinition`, client tool execution, declarative workflows and delegated ownership |
| 13-14 | `InvocationsHostServer`, deterministic facts with bounded model explanations, progressive-disclosure Skills and optional MCP Toolbox |

## State and guardrails

Hosted containers may restart or scale out. Lab 6 demonstrates local restart
continuity with files, or shared message history with an existing Azure Blob
account/container. Azurite is an optional local Blob emulator, never a deployed
endpoint. Labs 7-8's pending-packet session map is file-backed: it supports a local
restart, not cross-replica or version-roll continuity. Lab 10 must inspect the
actual backend before claiming rollback preserves conversation history.

Every agent carries the shared compliance block: no plan recommendation or
ranking, no medical advice, data minimization, grounded facts and citations,
and licensed-advisor handoff for judgment. Sample gates provide acceptance
evidence, not production compliance certification or cost-per-outcome results.

## Configuration and recovery

The administrator supplies account details, permissions, network access and
shared Search/telemetry resources. Edit Labs 1-2's notebook inputs instead of
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
