# Repository index

## Functional areas

- `azure-ai-agents/`: numbered, capability-oriented Foundry notebooks.
- `agent-framework/`: provider, workflow, middleware, context, state, skills and telemetry notebooks.
- `observability-and-evaluations/`: tracing, evaluator and red-team notebooks.
- `hosted-agents/`: small deployable examples for the Responses and Invocations protocols.
- `AgentOps/`: standalone GitOps example with infrastructure and tests.
- `build-and-operate-foundry-agents/`: cumulative Healthcare Marketplace workshop; five core labs and two stretch labs, run only through Jupyter walkthroughs.
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
- Workshop implementation: `common/` (data, environment and state), `data/` (synthetic fixtures), `labs/` (notebooks and adjacent authoring sources).
- First lab: `labs/lab1-foundry-project-models/` creates a project in an approved existing Foundry account, deploys chat/embedding models, and saves the notebook configuration and `artifacts/lab1/project.json`.
- Lab 3 conversation history: Azure Blob/Azurite or files; shared storage utilities retain optional backend implementations, but Redis is not a learner prerequisite or default.
- Lab 3 Search configuration: `labs/lab3-hosted-knowledge-sessions/knowledge_base.py` resolves underlying model identities separately from attendee-scoped deployment aliases.
- Hosted model resilience: `common/model_resilience.py` provides visible, retry-header-aware Agent Framework
  throttling retries and consistent failed Responses payload handling for Labs 2-4 and Stretch 7.
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
- Deployment: each lab's `hosted*/main.py` and minimal pinned requirements; `prepare.py` vendors shared files. Generated packages, credentials and runtime artifacts are not source.
- Deployment integration: `labs/deployment.py`; explicit notebook cells invoke deployment tooling, and Python holds validation/logic.
- Notebooks: edit adjacent `# %%` authoring sources and regenerate with `tools/py_to_ipynb.py`; give each code cell a preceding one-sentence description and keep CLI-only entry points out of learner notebooks.
- Lab teaching alignment: `labs/README.md`, each lab README, and Markdown cells in the six adjacent Python
  drivers connect outcomes to engineering decisions, acceptance evidence, ownership, and measurement limits.
  Generated notebooks mirror that wording; runtime instructions and executable cells remain unchanged.
- Offline checks: the workshop's `tools/validate_workshop.py` and `tests/`, plus `.github/workflows/workshop-validate.yml`. Validation checks notebook cells, dependency pins, self-tests, regression tests and all five hosted packages in a temporary copy.
- Cloud pipeline: Lab 5's nested workflow is an opt-in template, not an active deployment workflow.
- Shared RBAC setup: `scripts/setup-permissions.ps1` (PowerShell 7 in the dev container).

## Conventions

Use the root Python lock for workstation dependencies. Hosted requirements match its versions but contain only runtime packages.
Azure authentication is Entra-based; no committed credentials. Cloud operations require explicit learner action.
Keep capability notebooks independent from the cumulative use-case track.
Presentation decks and slide-build plans belong outside the runnable lab track.

## Freshness

Baseline: `ec19e83bc42f4a332d46a9b9a4e6a6b0361d0ab9` (after squashing the initial workshop commits).
Pending additions considered: `.gitattributes`, `.vscode/settings.json`,
`.github/skills/repo-index/SKILL.md`, and this index; related updates to `.gitignore`
and `.github/copilot-instructions.md` establish shared LF settings and index startup/maintenance rules.
Updated for the replacement of `foundry-hosted-agents-labs/` with `build-and-operate-foundry-agents/`,
the shared dev-container Redis service, Bash/Python deployment path and offline validation workflow.
Updated for attendee-scoped resource naming, dry-run cleanup, startup Redis configuration and enforced
lab-specific step identifiers in generated walkthrough notebooks.
Updated for optional Azure Blob conversation history and the local Azurite emulator in Lab 2.
Removed the workshop's `deck/` directory on 2026-09-30; runnable lab assets remain in place.
Also removed seven facilitator/authoring documents and the old top-level workshop `infra/`
scaffolding. A self-contained private Standard Agent `infra/` implementation is pending addition;
Lab 4's `infra/README.md`, hosted packaging rules and runnable lab assets remain.
Lab 2 history is limited to Azure Blob/Azurite or files, and Lab 3 uses file-backed session state;
shared Redis remains available to generic store configurations.
Added `build-and-operate-foundry-agents/common/model_resilience.py` for shared hosted-agent rate-limit
handling and Responses failure reporting; updated affected drivers, hosted entry points, and generated notebooks.
Added the two-page Build and Operate Foundry Agents workshop datasheet, Word version, and editable HTML source under
`build-and-operate-foundry-agents/Datasheets/`.
Lab 4 handler-registration and human-approval regression tests are in
`build-and-operate-foundry-agents/tests/test_lab4_workflow.py` (real workflow, offline packet writer and
streaming AgentExecutor graph). Lab 4 designates only the advisor coordinator as the final-output executor;
specialist streaming updates are intermediate outputs.
Baseline for this addition: `e34129302cdfbff4ed1a41defa5c9b930641a5da`; pending structural change considered:
the new Lab 3 regression test file.
Baseline for the lab-alignment documentation pass: `1d7fdc56a41928596ff64b6d2d7efb66a3c89331`.
Pending changes considered: the lab overview, core and stretch READMEs, artifact and infrastructure guidance,
six Python Markdown-cell sources, and their regenerated walkthrough notebooks. No runtime architecture,
dependencies, executable cells, deployment workflow, storage implementation, or artifact contract changed.
Baseline for the sanitized workshop infrastructure addition: `2798ac5d51e00ed6d418d27c5f67dc9a813ba000`.
Pending structural change considered: `build-and-operate-foundry-agents/infra/`, including the deployment
README, ignored local tfvars convention, provider lock, complete Standard Agent resource graph and workshop
environment outputs. This supersedes the registry-coupled draft and its PowerShell-only deployment checks.
Baseline for the post-deployment validator: `15f9fdbca29b5137618ff947009cfa58d45e504f`.
Pending structural change considered: `build-and-operate-foundry-agents/infra/post-deploy-validation.sh`
and its README/index navigation updates.
Pending structural change considered: `build-and-operate-foundry-agents/infra/troubleshoot-private-endpoint.sh`
and its README/index navigation updates.
Parent integration baseline: fork `f6e5d4c092139995b4700bcfe7cf04dfc634ad26` and
parent `a92d5b746a08205c793dc27598c95529f11b0382`.
Added prerequisite PDFs and their two generator scripts; retained the fork's Compose/Bash/PowerShell
setup and newer GitHub CLI lock while adopting the parent's azd `:0` pin and Windows-only dependency markers.
Baseline for the network-variant split: `f6e5d4c092139995b4700bcfe7cf04dfc634ad26`.
Pending structural changes considered: relocation of the previous Terraform root to `infra/privatelink/`,
the parallel `infra/public-network/` root and mocked policy tests, the parent infrastructure selector/state
migration guide and ignore rules, workshop navigation updates and `tests/test_infra_network_variants.py`.
Provider versions and private resource addresses are unchanged; signed Windows checksums are added to locks.

Baseline for notebook-first enhancements: `f6e5d4c092139995b4700bcfe7cf04dfc634ad26`.
Pending structural changes considered: the new Foundry project/model setup lab with its local
`project_setup.py` helper and offline tests, the six existing lab directories/sources/notebooks shifted by one,
and corresponding artifact, validation and pipeline references. Learners use the Jupyter notebooks;
adjacent Python sources, catch-up helpers and command-line tools remain internal authoring/CI utilities.
Lab 3's exercises no longer require `RUN_LAB2_*` environment switches.
Converter tests are in `tests/test_py_to_ipynb.py`; provisioning and notebook environment
regressions are in `tests/test_project_setup.py` and `tests/test_notebook_environment.py`.
