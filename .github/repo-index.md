# Repository index

## Functional areas

- `azure-ai-agents/`: numbered, capability-oriented Foundry notebooks.
- `agent-framework/`: provider, workflow, middleware, context, state, skills and telemetry notebooks.
- `observability-and-evaluations/`: tracing, evaluator and red-team notebooks.
- `hosted-agents/`: small deployable examples for the Responses and Invocations protocols.
- `AgentOps/`: standalone GitOps example with infrastructure and tests.
- `build-and-operate-foundry-agents/`: cumulative Healthcare Marketplace workshop; four core labs and two stretch labs. Replaces the old hosted-agent lab track.
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
- Workshop implementation: `common/` (data, environment and state), `data/` (synthetic fixtures), `labs/` (drivers and notebooks).
- Lab 2 conversation history: Azure Blob/Azurite or files; shared `common/message_store.py` retains Redis support for other labs. Cloud Blob uses an existing account/container and managed identity.
- Hosted model resilience: `common/model_resilience.py` provides visible, retry-header-aware Agent Framework
  throttling retries and consistent failed Responses payload handling for Labs 1-3 and Stretch 6.
- Workshop resource lifecycle: `common/resource_names.py` applies one attendee suffix to every created
  agent, evaluation, Search resource and project connection; `tools/cleanup_workshop.py` provides
  dry-run-first cleanup for one suffix or every workshop suffix without deleting shared infrastructure.
- Workshop infrastructure: `build-and-operate-foundry-agents/infra/README.md` is the entry point for a
  self-contained private Microsoft Foundry Standard Agent deployment. `variables.tf` and
  `terraform.tfvars.example` configure Azure placement, naming, networking, models and capacity; Terraform owns
  the VNet/private DNS, identity, Storage, Cosmos DB, AI Search, Foundry project/capability host, monitoring,
  registry and vault. Outputs map directly to the workshop `.env`; no concrete Azure identifiers are committed.
  `post-deploy-validation.sh` reuses Azure CLI credentials, verifies the tfvars-selected Azure context and
  Foundry resources, and runs a mini-model Responses API smoke test.
  `troubleshoot-private-endpoint.sh` performs read-only, continue-on-error diagnostics across the deployed
  resource inventory, VNet/subnets, NSGs, private endpoints and NICs, private DNS zones and links, service
  public-access settings, Foundry/operator/managed-identity RBAC, local private-IP resolution and activity logs.
- Deployment: each lab's `hosted*/main.py` and minimal pinned requirements; `prepare.py` vendors shared files. Generated packages, credentials and runtime artifacts are not source.
- Shell integration: `labs/deployment.py`; Bash is the learner shell, Python holds deployment validation/logic.
- Notebooks: edit the adjacent `# %%` Python driver and regenerate with `tools/py_to_ipynb.py`; preserve exercise gates.
- Lab teaching alignment: `labs/README.md`, each lab README, and Markdown cells in the six adjacent Python
  drivers connect outcomes to engineering decisions, acceptance evidence, ownership, and measurement limits.
  Generated notebooks mirror that wording; runtime instructions and executable cells remain unchanged.
- Offline checks: the workshop's `tools/validate_workshop.py` and `tests/`, plus `.github/workflows/workshop-validate.yml`. Validation checks notebook cells, dependency pins, self-tests, regression tests and all five hosted packages in a temporary copy.
- Cloud pipeline: Lab 4's nested workflow is an opt-in template, not an active deployment workflow.
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
Lab 3 handler-registration and human-approval regression tests are in
`build-and-operate-foundry-agents/tests/test_lab3_workflow.py` (real workflow, offline packet writer and
streaming AgentExecutor graph). Lab 3 designates only the advisor coordinator as the final-output executor;
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
