# Repository index

## Functional areas

- `azure-ai-agents/`: numbered, capability-oriented Foundry notebooks.
- `agent-framework/`: provider, workflow, middleware, context, state, skills and telemetry notebooks.
- `observability-and-evaluations/`: tracing, evaluator and red-team notebooks.
- `hosted-agents/`: small deployable examples for the Responses and Invocations protocols.
- `AgentOps/`: standalone GitOps example with infrastructure and tests.
- `build-and-operate-foundry-agents/`: cumulative Healthcare Marketplace workshop; core Labs 1-10 and optional Labs 11-14, run only through fourteen Jupyter notebooks.
- `byouc/`: use-case specification templates.

## Boundaries and navigation

- Agent navigation and index maintenance: `.github/copilot-instructions.md`, `.github/skills/repo-index/SKILL.md`, and this index.
- Shared line-ending policy: root `.gitattributes` normalizes text to LF; `.vscode/settings.json` defaults new files to LF. `.gitignore` permits these shared settings while excluding other VS Code files.
- Learner setup: `.devcontainer/devcontainer.json`, `.devcontainer/compose.yaml`, `.env.example`, root `requirements.in` and `requirements.txt`.
- Prerequisite collateral: root `Workshop-Agentic-AI-Immersion-Prerequisites-Datasheet*.pdf`;
  editable ReportLab generators are `scripts/generate_prereq_datasheet.py` and
  `scripts/generate_prereq_datasheet_v2.py`.
- Workshop entry point: `build-and-operate-foundry-agents/README.md` and `SETUP.md`.
- Workshop customer collateral: `build-and-operate-foundry-agents/Datasheets/` contains editable HTML sources and rendered PDF/Word deliverables.
- Workshop implementation: `common/` (data, environment and state), `data/` (synthetic fixtures),
  `labs/lab01/` through `labs/lab14/` (one notebook, adjacent authoring source and README each),
  and `shared/` (reusable products and internal drivers). Paths below are relative to the workshop.
- Labs 1-2: `shared/foundry-project-models/` creates a project in an approved existing Foundry account,
  deploys chat/embedding models, and saves the notebook configuration and `artifacts/lab1/project.json`.
- Numbered learner entry points: `labs/labNN/labNN_walkthrough.ipynb` for Labs 1-14,
  using two-digit names `lab01` through `lab14` for lexical sorting.
  Each folder documents only its own lab. Adjacent `labNN_*.py` files author each notebook.
  `shared/README.md` maps seven reusable implementation groups to their numbered consumers;
  original combined drivers are internal helpers, not learner entry points.
- Part handoffs: `common/notebook_parts.py` stores explicit JSON state and evidence fingerprints in
  `labs/artifacts/<topic-namespace>/part_a.json` and `part_b.json`. Stable namespaces `lab1` through
  `lab5`, `stretch6` and `stretch7` are not learner numbers; `LAB_NUMBERS` maps their recovery messages.
  Each notebook restores scoped, unchanged predecessor evidence in a fresh kernel without replaying
  cloud operations. Dependency navigation is in `labs/README.md`; Labs 9 and 11 branch from Lab 6,
  while Lab 13 requires only Lab 2.
- Labs 5-6 conversation history: Azure Blob/Azurite or files; shared storage utilities retain optional backend implementations, but Redis is not a learner prerequisite or default.
- Labs 5-6 Search configuration: `shared/hosted-knowledge-sessions/knowledge_base.py` resolves underlying model identities separately from attendee-scoped deployment aliases.
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
- Deployment integration: `labs/deployment.py`; explicit notebook cells invoke deployment tooling, and Python holds validation/logic.
- Notebooks: edit adjacent `# %%` authoring sources and regenerate with `tools/py_to_ipynb.py`; give each code cell a preceding one-sentence description and keep CLI-only entry points out of learner notebooks.
- Lab teaching alignment: `labs/README.md`, each lab README, and Markdown cells in the fourteen adjacent
  numbered authoring sources connect outcomes to engineering decisions, prerequisites, acceptance evidence and measurement limits.
- Offline checks: the workshop's `tools/validate_workshop.py` and `tests/`, plus `.github/workflows/workshop-validate.yml`. Validation checks notebook cells, dependency pins, self-tests, regression tests and all five hosted packages in a temporary copy.
- Checkpoint/retry coverage: `tests/test_split_labs_1_3.py`, `test_split_labs_4_7.py`, and
  `test_notebook_parts.py` retain internal topic namespace names. `test_py_to_ipynb.py` checks
  Labs 1-14 numbering, two-digit path sorting, one-lab-per-folder layout, prerequisites,
  navigation and source parity. `test_project_setup.py`
  covers provisioning; `test_lab4_workflow.py` covers real graph/streaming/human-approval behavior offline.
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

Baseline: `9db4b96a32238137d33261618295bb03be301d0d`.
Pending structural changes considered: zero-padding Labs 1-9's learner folders and adjacent
source/notebook filenames to `lab01` through `lab09`; updating links, fresh-kernel source lookup,
authoring tables, generated notebooks and sort/layout regression checks. Labs 10-14's paths
already use two digits. Original internal drivers, artifact
namespaces, hosted package basenames, cloud APIs and dependency pins remain compatible.
The workshop uses notebook-only Python 3.14 dev-container execution, attendee-scoped naming,
Blob/Azurite or file history, and explicit acceptance before cloud actions. Generic store utilities
may retain Redis support, but Redis is not a workshop prerequisite.
Private Standard Agent infrastructure, read-only troubleshooting scripts and customer datasheets
remain in their indexed locations. Labs 7-8 emit final workflow output only from the advisor
coordinator; streaming specialist updates are intermediate. No live Azure outcome is established
by offline validation.
