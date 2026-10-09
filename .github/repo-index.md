# Repository index

## Functional areas

- `azure-ai-agents/`: numbered, capability-oriented Foundry notebooks.
- `agent-framework/`: provider, workflow, middleware, context, state, skills and telemetry notebooks.
- `observability-and-evaluations/`: tracing, evaluator and red-team notebooks.
- `hosted-agents/`: small deployable examples for the Responses and Invocations protocols.
- `AgentOps/`: standalone GitOps example with infrastructure and tests.
- `build-and-operate-foundry-agents/`: Healthcare Marketplace workshop; canonical three-day Labs 1-14 and generated one-day Labs 1, 2, 4, capstone 7, run through Jupyter notebooks.
- `byouc/`: use-case specification templates.

## Boundaries and navigation

- Agent navigation and index maintenance: `.github/copilot-instructions.md`, `.github/skills/repo-index/SKILL.md`, and this index.
- Shared line-ending policy: root `.gitattributes` normalizes text to LF; `.vscode/settings.json` defaults new files to LF. `.gitignore` permits these shared settings while excluding other VS Code files.
- Learner setup: `.devcontainer/devcontainer.json`, `.devcontainer/compose.yaml`, `.env.example`, root `requirements.in` and `requirements.txt`.
- Prerequisite collateral: root `Workshop-Agentic-AI-Immersion-Prerequisites-Datasheet*.pdf`;
  editable ReportLab generators are `scripts/generate_prereq_datasheet.py` and
  `scripts/generate_prereq_datasheet_v2.py`.
- Workshop entry point: `build-and-operate-foundry-agents/README.md` and `SETUP.md`.
- Workshop authoring contract: `build-and-operate-foundry-agents/conventions.md`;
  `migration-plan.md` records the learner-critique/revised hosted-first proposal.
  `3-day-labs/README.md` is the runnable dependency guide. Hosted-first migration is
  implemented on `copilot/hosted-first-lab-conventions`; Lab 12 replaces
  prompt-backed orchestration with hosted-to-hosted delegation, while Lab 11
  is a terminal optional comparison.
- Workshop `Datasheets/` is absent in this baseline; root prerequisite PDFs and
  their indexed generators remain independent collateral.
- Workshop implementation: `common/` (data, environment and state), `data/` (synthetic fixtures),
  `3-day-labs/lab01/` through `3-day-labs/lab14/` (one notebook, adjacent authoring source and README each),
  and `shared/` (reusable products and internal drivers). Paths below are relative to the workshop.
- Short-track ownership/sync: `tools/sync_one_day_labs.py` generates `1-day-labs/` from canonical
  sources and shared products; `--check` detects drift, default sync preserves learner edits.
  Lab 4 composes real Lab 3 local gates with deployment; no separate Lab 3 notebook.
  Short Lab 7 adapts canonical fan-out/classifier cells plus `tools/one_day_team_finish.py`
  for explicit local/hosted approval and fixed-version deployment. Its isolated triage
  product requires Lab 4, uses synthetic local knowledge and does not require Lab 6/Search.
  Isolated `1-day-labs/products/` and `artifacts/` preserve the three-day products/evidence.
  Root `.env`, ports and Azure quota are shared; fresh kernels and sequential track use are required.
  `tests/test_one_day_labs.py` covers generation, drift/conflict protection, genuine gates,
  path isolation, package preparation, explicit advisor boundaries, accepted prerequisites,
  source gates, retired-copy protection and canonical preservation.
- Labs 1-2: `shared/foundry-project-models/` creates a project in an approved existing Foundry account,
  deploys chat/embedding models, and saves the notebook configuration and `artifacts/lab1/project.json`.
- Numbered learner entry points: `3-day-labs/labNN/labNN_walkthrough.ipynb` for Labs 1-14,
  using two-digit names `lab01` through `lab14` for lexical sorting.
  Each folder documents only its own lab. Adjacent `labNN_*.py` files author each notebook.
  `shared/README.md` maps seven reusable implementation groups to their numbered consumers;
  original combined drivers are internal helpers, not learner entry points.
- Part handoffs: `common/notebook_parts.py` stores explicit JSON state and evidence fingerprints in
  `3-day-labs/artifacts/<topic-namespace>/part_a.json` and `part_b.json`. Stable namespaces `lab1` through
  `lab5`, `stretch6` and `stretch7` are not learner numbers; `LAB_NUMBERS` maps their recovery messages.
  Each notebook restores scoped, unchanged predecessor evidence in a fresh kernel without replaying
  cloud operations. Dependency navigation is in `3-day-labs/README.md`; Lab 9 branches from Lab 6,
  while Labs 11 and 13 require Lab 4. Lab 12 joins Labs 8 and 9 and publishes an
  independent `hosted_delegation/part_a.json` checkpoint.
- Labs 5-6 conversation history: Azure Blob/Azurite or files; shared storage utilities retain optional backend implementations, but Redis is not a learner prerequisite or default.
- Labs 5-6 Search configuration: `shared/hosted-knowledge-sessions/knowledge_base.py` resolves underlying model identities separately from attendee-scoped deployment aliases.
- Lab 11: `shared/prompt-agents-and-workflows/stretch6_prompt_agents.py` owns the
  short, terminal Foundry Prompt Agent comparison. No hosted product consumes it.
- Lab 12: `shared/hosted-delegation/` owns authenticated, bounded delegation from
  an isolated knowledge-concierge candidate to the existing Lab 8 hosted triage
  service. Its sixth hosted package vendors original Lab 6 code without modifying
  the core product; callee version and trace evidence are explicit prerequisites.
  The prompt-backed graph, hosted snippet and old graph-only suite are removed.
- Hosted model resilience: `common/model_resilience.py` provides visible, retry-header-aware Agent Framework
  throttling retries and consistent failed Responses payload handling for Labs 3-8 and 13-14.
- Workshop resource lifecycle: `common/resource_names.py` applies one attendee suffix to every created
  agent, evaluation, Search resource and project connection; `tools/cleanup_workshop.py` provides
  dry-run-first cleanup for one suffix or every workshop suffix without deleting shared infrastructure.
- Workshop infrastructure: `build-and-operate-foundry-agents/infra/README.md` selects between independent
  `privatelink/` and `public-network/` Terraform roots and documents state-safe relocation of existing
  private deployments. Each root owns variables, example tfvars, provider lock and state; use distinct
  resource suffixes/backend keys. Both deploy identity, Storage, Cosmos DB, AI Search, Foundry
  project/capability host, monitoring, registry and vault with the same workshop `.env` contract.
  `privatelink/` retains VNet injection, private endpoints/DNS and AMPLS; `public-network/` uses public
  service hostnames with open Foundry/data-service access and mandatory Key Vault/ACR IPv4 allowlists,
  retaining service Entra/RBAC controls with no private network resources.
  Each root's `post-deploy-validation.sh` checks Azure context/resources and mini-model inference.
  `privatelink/troubleshoot-private-endpoint.sh` diagnoses private network/DNS, service settings and RBAC.
  Public firewall policy has mocked Terraform tests in `public-network/tests/`; offline variant contracts
  are tested in the workshop's `tests/test_infra_network_variants.py`.
- Deployment: `shared/<topic>/hosted*/main.py` and minimal pinned requirements;
  `prepare.py` vendors common/data/Skills files. Generated packages, credentials and runtime artifacts are not source.
- Deployment integration: `3-day-labs/deployment.py`; explicit notebook cells invoke deployment tooling, and Python holds validation/logic.
- Notebooks: edit adjacent `# %%` authoring sources and regenerate with `tools/py_to_ipynb.py`; give each code cell a preceding one-sentence description and keep CLI-only entry points out of learner notebooks.
- Lab teaching alignment: `3-day-labs/README.md`, each lab README, and Markdown cells in the fourteen adjacent
  numbered authoring sources connect outcomes to engineering decisions, prerequisites, acceptance evidence and measurement limits.
- Offline checks: the workshop's `tools/validate_workshop.py` and `tests/`, plus `.github/workflows/workshop-validate.yml`. Validation checks notebook cells, dependency pins, self-tests, regression tests and all six hosted packages in a temporary copy.
- Checkpoint/retry coverage: `tests/test_split_labs_1_3.py`, `test_split_labs_4_7.py`, and
  `test_notebook_parts.py` retain internal topic namespace names. `test_py_to_ipynb.py` checks
  Labs 1-14 numbering, two-digit path sorting, one-lab-per-folder layout, prerequisites,
  navigation and source parity. `test_project_setup.py`
  covers provisioning; `test_lab4_workflow.py` covers real graph/streaming/human-approval behavior offline.
- Hosted-first continuity regression coverage: `tests/test_core_continuity.py`
  checks retained exercise behavior, deployed triage evidence and immutable
  evaluation/release contracts. `tests/test_hosted_delegation.py` covers scope/version,
  remote failure, pending-only behavior and independent handoff restoration.
- Cloud pipeline: `shared/operate-hosted-agents/.github/workflows/agent-ci.yml`
  is an opt-in template, not an active deployment workflow.
- Shared RBAC setup: `scripts/setup-permissions.ps1` (PowerShell 7 in the dev container).

## Conventions

Use the root Python lock for workstation dependencies. Hosted requirements match its versions but contain only runtime packages.
Azure authentication is Entra-based; no committed credentials. Cloud operations require explicit learner action.
Keep capability notebooks independent from the cumulative use-case track.
Presentation decks and slide-build plans belong outside the runnable lab track.

## Freshness

Parent integration baseline: fork `f6e5d4c092139995b4700bcfe7cf04dfc634ad26` and
parent `a92d5b746a08205c793dc27598c95529f11b0382`.
Added prerequisite PDFs and their two generator scripts; retained the fork's Compose/Bash/PowerShell
setup and newer GitHub CLI lock while adopting the parent's azd `:0` pin and Windows-only dependency markers.
Baseline for the network-variant split: `f6e5d4c092139995b4700bcfe7cf04dfc634ad26`.
Pending structural changes considered: relocation of the previous Terraform root to `infra/privatelink/`,
the parallel `infra/public-network/` root and mocked policy tests, the parent infrastructure selector/state
migration guide and ignore rules, workshop navigation updates and `tests/test_infra_network_variants.py`.
Provider versions and private resource addresses are unchanged; signed Windows checksums are added to locks.

Integration baseline: `bdc877cc5283e04b2564955007d08cc6972e571d` (parent sync and network PR merged).
Previous enhancement replay baseline: `e5eec2a` (two-digit Labs 1-14 and shared implementation preserved).
Pending structural changes considered: adding `shared/prompt-agents-and-workflows/triage_workflow.py`,
removing its legacy `marketplace_triage_workflow.yaml`, and replacing Lab 12's Foundry workflow-agent
publication with notebook/container-local MAF orchestration over Lab 11's pinned prompt versions.
Updated Lab 11 handoff teaching, Lab 12 authoring/notebook, hosted delegation, source evidence and regression
coverage. Numbered paths, artifact namespaces and dependency pins remain unchanged.
The workshop uses notebook-only Python 3.14 dev-container execution, attendee-scoped naming,
Blob/Azurite or file history, and explicit acceptance before cloud actions. Generic store utilities
may retain Redis support, but Redis is not a workshop prerequisite.
Both Standard Agent network variants, read-only troubleshooting scripts and customer datasheets
remain in their indexed locations. Labs 7-8 emit final workflow output only from the advisor
coordinator; streaming specialist updates are intermediate. No live Azure outcome is established
by offline validation.

Hosted-first migration baseline: `d575a5c9876ca4bd9e61261e56a442d38eb16bed`.
Pending structural changes considered: workshop conventions and reviewed migration
plan, new `shared/hosted-delegation/` candidate package and independent checkpoint,
removed prompt-backed graph/snippet/suite, core continuity and release evidence,
fourteen source/notebook pairs, dependency validation and related documentation.
This migration supersedes the previous Lab 11 -> 12 graph described above.
The source branch `copilot/enhance-labs-for-foundry-agents-again` stays clean at
the baseline; implementation is isolated on `copilot/hosted-first-lab-conventions`.
The notebook converter emits LF explicitly on Windows as well as Linux; offline
validation checks those bytes, the exact dependency table and six named package roots.

Short-track baseline: `d575a5c9876ca4bd9e61261e56a442d38eb16bed`, with the complete
uncommitted hosted-first snapshot retained from `copilot/hosted-first-lab-conventions`.
Implementation is isolated on `copilot/one-day-foundry-workshop`; parent worktrees are unchanged.
Pending structural changes considered: `labs/` -> `3-day-labs/` relocation and required
path references, generated `1-day-labs/` subset/products/provenance, explicit composition
and conflict-safe sync tool, isolated ignored runtime output, new regression coverage
and multi-duration navigation/conventions. The full curriculum and acceptance gates
are unchanged beyond relocation references; one-day Lab 4 adds their necessary local phase.
Latest short-track adaptation replaces Lab 13/batch copies with condensed Lab 7
and the generated MAF triage product. Added `tools/one_day_team_finish.py`; canonical
three-day material is untouched. The terminal `one-day-team` checkpoint must not
be confused with three-day Lab 8's recovery contract.
