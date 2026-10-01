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
- Workshop entry point: `build-and-operate-foundry-agents/README.md` and `SETUP.md`.
- Workshop implementation: `common/` (data, environment and state), `data/` (synthetic fixtures), `labs/` (drivers and notebooks).
- Lab 2 conversation history: Azure Blob/Azurite or files; shared `common/message_store.py` retains Redis support for other labs. Cloud Blob uses an existing account/container and managed identity.
- Hosted model resilience: `common/model_resilience.py` provides visible, retry-header-aware Agent Framework
  throttling retries and consistent failed Responses payload handling for Labs 1-3 and Stretch 6.
- Workshop resource lifecycle: `common/resource_names.py` applies one attendee suffix to every created
  agent, evaluation, Search resource and project connection; `tools/cleanup_workshop.py` provides
  dry-run-first cleanup for one suffix or every workshop suffix without deleting shared infrastructure.
- Deployment: each lab's `hosted*/main.py` and minimal pinned requirements; `prepare.py` vendors shared files. Generated packages, credentials and runtime artifacts are not source.
- Shell integration: `labs/deployment.py`; Bash is the learner shell, Python holds deployment validation/logic.
- Notebooks: edit the adjacent `# %%` Python driver and regenerate with `tools/py_to_ipynb.py`; preserve exercise gates.
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
Also removed seven facilitator/authoring documents and the unused top-level workshop `infra/`
scaffolding. Lab 4's `infra/README.md`, hosted packaging rules and runnable lab assets remain.
Lab 2 history is limited to Azure Blob/Azurite or files, and Lab 3 uses file-backed session state;
shared Redis remains available to generic store configurations.
Added `build-and-operate-foundry-agents/common/model_resilience.py` for shared hosted-agent rate-limit
handling and Responses failure reporting; updated affected drivers, hosted entry points, and generated notebooks.
