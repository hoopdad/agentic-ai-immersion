# Build and Operate Foundry Agents

A notebook-first workshop for healthcare marketplace engineers building the
**Healthcare Marketplace Concierge** on Microsoft Foundry. Core Labs 1-10 teach
hosted agents, specialist orchestration, human approval and operations through
related products with explicit lineage. Optional Labs 11-14 compare prompt ownership,
delegate between hosted services, and explore protocols and Skills.
All participant data is synthetic; hosted MAF does not require Prompt Agents.

Start with [SETUP.md](SETUP.md), read the [use case](USE-CASE.md), and choose
the [three-day full sequence](3-day-labs/README.md) or the
[one-day hosted route](1-day-labs/README.md). The one-day route is **1 -> 2 -> 4 -> 7**,
with real local acceptance folded into Lab 4 and a condensed
**Lab 7: Build and host a multi-agent team** capstone. Learners change task routing,
review specialist work, explicitly approve a packet and invoke the edited team
hosted in Foundry. MAF supplies the workflow; no Search or Lab 6 is required.
Use the repository Python 3.14 dev container and
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

## Three-day agenda

| # | Notebook | Outcome | Evidence passed onward |
|---|---|---|---|
| 1 | [Identity and project](3-day-labs/lab01/lab01_walkthrough.ipynb) | Create a project in an existing admin-supplied Foundry account | `artifacts/lab1/part_a.json` |
| 2 | [Models and verification](3-day-labs/lab02/lab02_walkthrough.ipynb) | Provision chat and embedding deployments, verify access, persist downstream settings | `artifacts/lab1/part_b.json`, `project.json` and project/model configuration in the repository-root `.env` |
| 3 | [Tools and local testing](3-day-labs/lab03/lab03_walkthrough.ipynb) | Build a typed-tool concierge with shared compliance instructions and test locally | `artifacts/lab2/part_a.json` |
| 4 | [Deploy and invoke](3-day-labs/lab04/lab04_walkthrough.ipynb) | Deploy and inspect an immutable version | `artifacts/lab2/part_b.json`, `hosted.json`, transcripts |
| 5 | [Knowledge and retrieval](3-day-labs/lab05/lab05_walkthrough.ipynb) | Build governed Foundry IQ knowledge | `artifacts/lab3/part_a.json`, `knowledge.json` |
| 6 | [Sessions and resiliency](3-day-labs/lab06/lab06_walkthrough.ipynb) | Prove conversation continuity after a local restart; distinguish files from shared Blob history | `artifacts/lab3/part_b.json`, `hosted.json`, sessions |
| 7 | [Specialist orchestration](3-day-labs/lab07/lab07_walkthrough.ipynb) | Fan out to specialists and bound compliance reflection | `artifacts/lab4/part_a.json` |
| 8 | [Advisor approval and recovery](3-day-labs/lab08/lab08_walkthrough.ipynb) | Explicit advisor decisions, local file-backed pending-state recovery, and triage deployment acceptance | `artifacts/lab4/part_b.json`, `handoff_packets/`, `hosted.json` |
| 9 | [Tracing and evaluation](3-day-labs/lab09/lab09_walkthrough.ipynb) | Trace and evaluate once, preserving measured results | `artifacts/lab5/part_a.json`, `eval_report.md`, `evaluation_bundle.json`, `pipeline.md` |
| 10 | [Release and rollback](3-day-labs/lab10/lab10_walkthrough.ipynb) | Gate the measured results; rehearse promotion and rollback without deployment | `artifacts/lab5/part_b.json`, `gate_result.json`, `release_plan.json` |
| 11 | [Prompt versus hosted](3-day-labs/lab11/lab11_walkthrough.ipynb) | Short optional terminal comparison after Lab 4; one versioned prompt and invocation, no downstream consumers | `artifacts/stretch6/part_a.json` |
| 12 | [Hosted-to-hosted delegation](3-day-labs/lab12/lab12_walkthrough.ipynb) | After both Labs 8 and 9, an isolated concierge extension calls the pinned triage service with correlated evidence | `artifacts/hosted_delegation/part_a.json` |
| 13 | [Invocations](3-day-labs/lab13/lab13_walkthrough.ipynb) | Contrast structured Invocations with Responses | `artifacts/stretch7/part_a.json`, `invocations.json`, claim reviews |
| 14 | [Skills and Toolbox](3-day-labs/lab14/lab14_walkthrough.ipynb) | After Lab 13, introduce a distinct Responses Skills service and optionally attach preview Toolbox | `artifacts/stretch7/part_b.json`, skills transcript |

Follow **core Labs 1-10 in order, then selected extensions**, using the
[prerequisite table and dependency graph](3-day-labs/README.md#sequence-and-artifact-chain).
Lab 9 requires Lab 6, not Lab 8; Labs 11 and 13 require Lab 4.
Lab 12 joins both Labs 8 and 9 and does not consume Lab 11. Lab 10 is recommended
release background for Lab 12, not its required artifact. Each notebook can start in a fresh kernel and restores
validated predecessor evidence instead of repeating provisioning or evaluation.
Each folder `3-day-labs/lab01` through `3-day-labs/lab14` holds exactly one walkthrough,
its adjacent authoring source and its own README. Reusable product code and
internal helpers live outside learner folders in [`shared/`](shared/README.md).
Existing topic namespaces `artifacts/lab1` through `lab5`, `stretch6` and
`stretch7` remain internal contracts, not learner lab numbers. Lab 12 has a new
independent `hosted_delegation/part_a.json` contract; old prompt-backed
`stretch6/part_b.json` is not valid hosted delegation evidence.
Independent branches still share local port 8088, edited product files and Azure
quota. Stop notebook-owned hosts before changing branches; do not run multiple
runtime notebooks concurrently in the same workspace.

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
| 11 | Minimal versioned prompt ownership comparison to Lab 4's hosted Responses product; no second workflow track |
| 12 | Authenticated hosted-service boundary, pinned callee, bounded timeout/errors, deliberate retries and caller/callee correlation |
| 13-14 | Separate stateless `InvocationsHostServer` batch product and Responses Skills product; deterministic facts, progressive disclosure and optional preview MCP Toolbox |

## Product lineage

Labs 3-4 test and deploy the same typed-tool concierge. Labs 5-6 extend it with
knowledge and history through `shared/hosted-knowledge-sessions/`; accepted tool
and policy behavior must be retained and checked, not assumed from a new folder.
Labs 7-8 branch into `shared/hosted-multi-agent-handoff/`, the triage service;
it is not a redeployment of the concierge. Labs 9-10 measure and gate the pinned
Lab 6 knowledge concierge; triage packet metadata is optional context.

Lab 12's `shared/hosted-delegation/` is an isolated extension candidate using
the accepted concierge behavior and Lab 8's deployed triage reference. It does
not overwrite the core version measured in Labs 9-10 or embed a new prompt graph.
Changing the candidate requires new evaluation before any release claim.
Lab 13 branches into a stateless batch product; Lab 14 preserves that evidence
while introducing a distinct Responses Skills service, not batch session state.

## State and guardrails

Hosted containers may restart or scale out. Lab 6 demonstrates local restart
continuity with files, or shared message history with an existing Azure Blob
account/container. Azurite is an optional local Blob emulator, never a deployed
endpoint. Labs 7-8's pending-packet session map is file-backed: it supports a local
restart, not cross-replica or version-roll continuity. Lab 10 must inspect the
actual backend before claiming rollback preserves conversation history.
Lab 12 may relay a remote pending case but never sends an automatic advisor
decision. Single-instance pending-state recovery is not distributed resume,
production advisor authorization or safe replay of a state-changing request.

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

Follow [conventions.md](conventions.md) when changing workshop labs, products,
handoffs, or documentation. The reviewed [migration plan](migration-plan.md)
records the integrated hosted-first implementation and remaining approved live
rehearsal. The agenda above describes the implemented curriculum;
[`3-day-labs/README.md`](3-day-labs/README.md) remains the actual prerequisite guide.
Integration and offline validation do not establish live Azure acceptance.

Adjacent Python cell sources and `tools/py_to_ipynb.py` are internal notebook
authoring tools, not learner entry points. Authors edit those sources and
regenerate notebooks while preserving exercise gates. Runtime `.py` files are
deployable product code and may be edited during notebook-guided exercises.
The root dependency lock supplies workstation packages; hosted subsets use
matching pins.

For authors and offline CI only, the existing validator checks notebook/source
alignment, package contracts and offline regression tests without deploying Azure.

The full curriculum is canonical in `3-day-labs/`; the relocated teaching
content is unchanged apart from required path references. `1-day-labs/` is a
generated subset with explicit adaptations and isolated editable products/artifacts.
Both tracks share root configuration, quota and local ports; use fresh kernels
and do not run the tracks concurrently.

After authoring a canonical source or shared product, synchronize the short
track before validation. Sync refuses to overwrite learner edits; archive them
before deliberately using `--overwrite`. `--check` is read-only and detects drift.

```bash
python build-and-operate-foundry-agents/tools/sync_one_day_labs.py
python build-and-operate-foundry-agents/tools/sync_one_day_labs.py --check
```

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
