# Copilot Instructions for Agentic AI Immersion Day

## Repository Index: Startup and Change Maintenance

- At the start of every session working in this repository, load the
  [repo-index skill](skills/repo-index/SKILL.md) and read [repo-index.md](repo-index.md)
  before exploring files or making changes.
- Navigate from the index first. If it is missing or stale, refresh it using the
  skill. Search text only when the index cannot locate the target, then improve
  the index with useful navigation information.
- After adding, deleting, or renaming files, or changing architecture, boundaries,
  entry points, ownership, major dependencies, workflows, or conventions, refresh
  the affected index entries before completing the task. Keep the index compact,
  preserve useful notes, and record the baseline commit and pending structural
  changes considered. Do not rewrite it for minor edits that leave it accurate.

## Project Overview

This is a hands-on workshop repository for building AI agents with Microsoft Azure AI Foundry. It covers Azure AI Agents SDK, Microsoft Agent Framework, observability, evaluations, and hosted agents.

### Repository Structure

```
azure-ai-agents/           # Azure AI Agents notebooks (basics, tools, search, MCP, IQ, memory, hosted-skills)
agent-framework/            # Microsoft Agent Framework notebooks
  agents/                   #   Agent providers (Azure AI, OpenAI, etc.)
  workflows/                #   Multi-agent workflows (sequential, magentic, human-in-the-loop)
  middleware/                #   Function/class/decorator middleware patterns
  threads/                  #   Custom thread stores (Redis, suspend/resume)
  context-providers/         #   Context providers (simple, AI Search agentic retrieval)
  skills/                   #   Agent Skills (file-based, code-defined, FSI scenarios)
  observability/             #   Tracing with Foundry & OpenTelemetry
observability-and-evaluations/  # Telemetry, agent evaluation, red-team testing
build-and-operate-foundry-agents/ # Cumulative Healthcare Marketplace lab track
byouc/                      # Bring Your Own Use Case templates
```

### Key SDK Packages (Python)

| Package | Purpose |
|---------|---------|
| `azure-ai-projects` | **Recommended entry point** — AIProjectClient for agents, evals, connections |
| `azure-ai-agents` | Low-level AgentsClient (auto-installed as dependency, access via `project_client.agents`) |
| `azure-ai-evaluation` | Agent evaluation, red-teaming, quality metrics |
| `azure-search-documents` | Azure AI Search SDK for vector/hybrid/agentic retrieval |
| `azure-identity` | DefaultAzureCredential for authentication |
| `microsoft-agent-framework` | Agent Framework for persistent agents, workflows, middleware |

### Authentication Pattern

Always use `DefaultAzureCredential`. The project endpoint is in `.env` as `FOUNDRY_PROJECT_ENDPOINT`:

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
agents_client = project_client.agents  # access agents via project client
```

### Environment Variables

All config is in `.env` at the repo root. Key variables:
- `FOUNDRY_PROJECT_ENDPOINT` — Foundry project endpoint
- `AZURE_AI_MODEL_DEPLOYMENT_NAME` — Model deployment (gpt-5.4)
- `AZURE_AI_SEARCH_ENDPOINT` / `AZURE_SEARCH_INDEX_NAME` — AI Search config
- `FOUNDRY_MCP_CONNECTION_ID` — MCP server connection

## ⚠️ Fresh Information First

**Azure SDKs and Foundry APIs change constantly. Never work with stale knowledge.**

Before implementing anything with Azure/Foundry SDKs:

1. **Search official docs first** — Use the Microsoft Docs MCP (`microsoft-docs`) to get current API signatures, parameters, and patterns
2. **Verify SDK versions** — Check `pip show <package>` for installed versions; APIs differ between versions
3. **Don't trust cached knowledge** — Your training data is outdated. The SDK you "know" may have breaking changes.

**If you skip this step and use outdated patterns, you will produce broken code.**

---

## Core Principles

Apply these principles to every task.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- If you write 200 lines and it could be 50, rewrite it.

**The test:** Would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution (TDD)

**Define success criteria. Loop until verified.**

| Instead of... | Transform to... |
|---------------|-----------------|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

---

## Installed Skills

Skills are domain-specific knowledge packages. Each has a `SKILL.md` with YAML frontmatter for discovery.

### Foundry Skills (`.github/plugins/azure-skills/skills/`)

| Skill | Purpose | Maps To |
|-------|---------|---------|
| `microsoft-foundry` | **Orchestrator** — routes intent to sub-skills | All Foundry notebooks |
| `foundry-hosted-agents` | Build/deploy containerized agents | `hosted-agents/` |
| `foundry-toolboxes` | Intent-based Toolboxes (MCP, AI Search, Code Interpreter) | Tool integration |
| `foundry-workflows` | Multi-agent orchestration & Connected Agents | `agent-framework/workflows/` |
| `foundry-iq-knowledge-bases` | Agentic retrieval pipelines | `azure-ai-agents/8-foundry-IQ-agents.ipynb` |
| `foundry-memory` | Long-term memory across sessions | `azure-ai-agents/9-agent-memory-search.ipynb` |
| `foundry-observability` | Tracing, eval-trace correlation, batch evals | `observability-and-evaluations/` |
| `foundry-governance` | RBAC, RAI policies, AI Gateway | Security & governance |
| `foundry-managed-skills` | SKILL.md as Foundry-side resource | Managed skills |
| `foundry-projects-resources` | Provision resources, connections, networking | Project setup |
| `foundry-models` | Model deployment, capacity, quota | Model management |

### Python SDK Skills (`.github/plugins/azure-sdk-python/skills/`)

| Skill | Purpose | Maps To |
|-------|---------|---------|
| `azure-ai-projects-py` | **Recommended** — AIProjectClient for agents, evals, connections | All notebooks |
| `agent-framework-azure-ai-py` | Agent Framework with AzureAIAgentsProvider | `agent-framework/` |
| `azure-search-documents-py` | AI Search SDK for vector/hybrid/agentic retrieval | `azure-ai-agents/5-agents-aisearch.ipynb` |
| `azure-identity-py` | DefaultAzureCredential authentication | All notebooks |

### Core Skills (`.github/skills/`)

| Skill | Purpose | Maps To |
|-------|---------|---------|
| `cloud-solution-architect` | Azure architecture design, WAF reviews, design patterns, technology choices | Architecture decisions |
| `mcp-builder` | Building MCP servers | `azure-ai-agents/7-mcp-tools.ipynb` |
| [repo-index](skills/repo-index/SKILL.md) | Repository navigation at startup and index maintenance after structural changes | [repo-index.md](repo-index.md) |
| `skill-creator` | Creating new custom skills | Extending the repo |

### Skill Selection

Only load skills relevant to the current task. Loading all skills causes context rot.

---

## MCP Servers

Pre-configured Model Context Protocol servers in `.vscode/mcp.json`:

### Documentation & Search

| MCP | Purpose |
|-----|---------|
| `microsoft-docs` | **Search Microsoft Learn** — Official Azure/Foundry docs. Use this FIRST. |
| `context7` | Indexed documentation with semantic search |
| `deepwiki` | Ask questions about GitHub repositories |

### Development Tools

| MCP | Purpose |
|-----|---------|
| `github` | GitHub API operations |
| `playwright` | Browser automation and testing |

### Utilities

| MCP | Purpose |
|-----|---------|
| `sequentialthinking` | Step-by-step reasoning for complex problems |
| `markitdown` | Convert documents to markdown |
| `memory` | Persistent memory across sessions |

**Usage:** Use `microsoft-docs` to search official documentation before implementing Azure SDK code.

---

## SDK Quick Reference

| Package | Purpose | Install |
|---------|---------|---------|
| `azure-ai-projects` | Foundry project client, agents, evals, connections | `pip install azure-ai-projects` |
| `azure-ai-agents` | Standalone agents client (use via projects) | `pip install azure-ai-agents` |
| `azure-search-documents` | Azure AI Search SDK | `pip install azure-search-documents` |
| `azure-identity` | Authentication | `pip install azure-identity` |

### Authentication Pattern

Always use `DefaultAzureCredential` for production:

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

credential = DefaultAzureCredential()
client = AIProjectClient(
    endpoint="https://<resource>.services.ai.azure.com/api/projects/<project>",
    credential=credential
)
```

### Environment Variables

```bash
FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.4
```

---

## Conventions

### Code Style

- Prefer `async/await` for all Azure SDK I/O
- Use context managers: `with client:` or `async with client:`
- Close clients explicitly or use context managers
- Use `create_or_update_*` for idempotent operations
- Use type hints on all function signatures

### Git & GitHub

- Always use `gh` CLI for GitHub operations (PRs, issues, etc.) — never the MCP `github-create_pull_request` tool
- Use `gh pr create` for pull requests, `gh issue create` for issues

### Clean Code Checklist

Before completing any code change:

- [ ] Functions do one thing
- [ ] Names are descriptive and intention-revealing
- [ ] No magic numbers or strings (use constants)
- [ ] Error handling is explicit (no empty catch blocks)
- [ ] No commented-out code
- [ ] Tests cover the change

### Testing Patterns

```python
# Arrange
service = ProjectService()
expected = Project(id="123", name="test")

# Act  
result = await service.get_project("123")

# Assert
assert result == expected
```

---

## Creating New Skills

1. Create a new directory under `.github/skills/<skill-name>/`
   - Use language suffix: `-py`, `-dotnet`, `-ts`, `-java`
   - Core/cross-language skills have no suffix
   - Example: `azure-cosmos-db-py`, `azure-ai-inference-dotnet`, `mcp-builder`
2. Add a `SKILL.md` file with YAML frontmatter:
   ```yaml
   ---
   name: skill-name-py
   description: Brief description of what the skill does and when to use it
   ---
   ```
3. Add detailed instructions in the markdown body
4. Keep skills focused on a single domain
5. Reference official docs via `microsoft-docs` MCP for current API patterns

---

## Do's and Don'ts

### Do

- ✅ Use `DefaultAzureCredential` for authentication
- ✅ Use async/await for all Azure SDK operations
- ✅ Write tests before or alongside implementation
- ✅ Keep functions small and focused
- ✅ Match existing patterns in the codebase
- ✅ Use `gh` CLI for all GitHub operations (PRs, issues, releases)

### Don't

- ❌ Hardcode credentials or endpoints
- ❌ Suppress type errors (`as any`, `@ts-ignore`, `# type: ignore`)
- ❌ Leave empty exception handlers
- ❌ Refactor unrelated code while fixing bugs
- ❌ Add dependencies without justification
- ❌ Use GitHub MCP tools for write operations (enterprise token restrictions)

---

## Success Indicators

These principles are working if you see:

- Fewer unnecessary changes in diffs
- Fewer rewrites due to overcomplication
- Clarifying questions come before implementation (not after mistakes)
- Clean, minimal PRs without drive-by refactoring
- Tests that document expected behavior


### Build and Operate workshop

Before changing this workshop, read `build-and-operate-foundry-agents/conventions.md`.
Read `migration-plan.md` for migration history and implementation status; use
`3-day-labs/README.md` for the hosted-first curriculum and required prerequisites.
Canonical lab sources live in `3-day-labs/`. The generated `1-day-labs/` route is
Labs 1, 2, 4 and capstone 7; Lab 4 includes genuine local acceptance before deployment.
Short Lab 7 requires Lab 4, not Lab 6: reuse the MAF graph with synthetic local
knowledge, a changed classifier, explicit human decisions and pinned Foundry
invocation. Short-only finish cells live in `tools/one_day_team_finish.py`.
Do not claim three-day recovery acceptance or silently auto-approve packets.
After canonical/shared changes run `tools/sync_one_day_labs.py`; validation includes
its read-only `--check`. Never hand-edit generated short material or sync over
learner edits without archiving them and explicitly choosing `--overwrite`.
Short exercises and evidence use `1-day-labs/products/` and `artifacts/`, not the
three-day product/checkpoints. Root `.env`, ports and quota remain shared.
The hosted-first implementation is integrated; approved live learner rehearsal
remains outstanding. Do not infer Azure acceptance from offline validation.
Teach core Labs 1-10 in order, then chosen extensions; dependency independence
does not authorize parallel same-workspace runtime (shared port 8088, sources and quota).
Lab 11 is a short terminal prompt comparison requiring Lab 4, with no downstream
consumers. Lab 12 requires both Labs 8 and 9, calls the existing hosted triage
service from an isolated `shared/hosted-delegation/` concierge candidate, and
publishes `3-day-labs/artifacts/hosted_delegation/part_a.json`; never accept legacy
`stretch6/part_b.json` as delegation evidence or package a prompt-backed graph.
Lab 13 requires Lab 4; Lab 14 requires Lab 13 and introduces a distinct Responses
Skills product, not a stateful conversion of the batch Invocations service.
Document product lineage and retained exercise behavior, preserve the exact
core evaluation/release target, and distinguish local file-backed pending-state
recovery from distributed continuity. Never manufacture an advisor decision.
Preserve existing topic checkpoint mappings outside the new Lab 12 contract.
Label optional/preview skips and offline versus actual Azure evidence explicitly.

The learner path is the repository Python 3.14 dev container with Bash instructions.
Keep lab logic in Python; retain PowerShell
only for shared permission setup. Edit the adjacent cell scripts and regenerate notebooks.
Use the root requirements lock; hosted subsets must match its pins. Never import local `.env`,
`.azure`, caches, vendored package output or executed notebook output. Validate offline with
`python build-and-operate-foundry-agents/tools/validate_workshop.py`.
