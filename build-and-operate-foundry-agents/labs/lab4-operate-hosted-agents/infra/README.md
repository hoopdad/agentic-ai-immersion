# Infrastructure notes for the hosted-agent pipeline

What the pipeline expects to exist per environment (dev, test, prod), who creates it, and what `azd` creates on its own. No Bicep ships in this folder on purpose: the source workshop's `AgentOps/` material is only a reference, and the hosting organization will have its own landing zone. This file lists the contract the code has with the infrastructure.

## Per environment
| Resource | Created by | Used by | Notes |
|---|---|---|---|
| Foundry resource + project | platform team (Bicep in base repo `AgentOps/infra`) | every lab | `FOUNDRY_PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID` |
| Model deployment `gpt-5.4-mini` and `text-embedding-3-large` | platform team | hosted agents, judges, Lab 2 index | Names in `AZURE_AI_MODEL_DEPLOYMENT_NAME` / `EMBEDDING_MODEL_DEPLOYMENT_NAME`; raise TPM for the eval job (18 questions x up to 4 model calls) |
| Azure AI Search with Foundry IQ knowledge base `healthcare-marketplace-kb` + project connection | Lab 2 in dev; platform team in test/prod | hosted agent (`MARKETPLACE_KB_MCP_URL`) | Semantic ranker enabled; search service identity needs Cognitive Services OpenAI User + Cognitive Services User on the Foundry account |
| Azure Blob Storage account + container, when shared history is required | platform team, Entra auth | Lab 2 message history (`MARKETPLACE_BLOB_STORAGE_URL` and `MARKETPLACE_BLOB_STORAGE_CONTAINER`) | files are local teaching state; shared Blob history must be explicitly configured for deployed replica/version continuity; this does not migrate Lab 3's file-backed packet store |
| Application Insights connected to the project | platform team | Lab 4 tracing, hosted agent spans | `APPLICATIONINSIGHTS_CONNECTION_STRING` on the hosted agent through `azd env set` |
| Hosted agent `healthcare-marketplace-concierge-hosted` | `azd ai agent init` + `azd up` in the deploy job | Labs 2 to 4 | One azd environment per target: `healthcare-marketplace-concierge-dev`, `-test`, `-prod`; every `azd up` is a new version |
| Entra app with GitHub OIDC federated credentials | platform team | `azure/login@v2` in every Azure job | One per environment; subject `repo:<org>/<repo>:environment:<env>` |

## Roles the pipeline identity needs
| Scope | Role | Why |
|---|---|---|
| Foundry project | Azure AI User | run the model and the judges in the evaluate job |
| Foundry project | Foundry Project Manager | `azd ai agent init` / `azd up` (deploy and rollback jobs) |
| Foundry project | Foundry Agent Consumer | `test_local.py --deployed` smoke test |
| Foundry account | Cognitive Services OpenAI User | azure-ai-evaluation judges, embeddings |
| Search service | Search Index Data Reader | the evaluate job's local hosted/main.py calls the knowledge base MCP endpoint |
| Search service (dev) | Search Service Contributor + Search Index Data Contributor | `catch_up.py --through 2` rebuilds indexes when they are missing |

## Roles the hosted agent's managed identity needs
| Scope | Role | Why |
|---|---|---|
| Foundry project | Azure AI User | `FoundryChatClient` model calls with `DefaultAzureCredential` |
| Search service | Search Index Data Reader | `MCPStreamableHTTPTool` to the knowledge base with the Entra bearer |
| Azure Blob container or account, when shared history is configured | Storage Blob Data Contributor | Lab 2 message history, using the hosted agent's dedicated Entra agent identity |

Propagation takes 5 to 15 minutes. The first pipeline run after a role change usually fails with 403; re-run.

## Hosted agent environment variables
`azd ai agent init` writes `agent.yaml` next to `hosted/main.py`; do not check it in unless the extension needs it (document the choice). The Lab 2 container reads: `FOUNDRY_PROJECT_ENDPOINT` (injected by Foundry), `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `MARKETPLACE_KB_MCP_URL`, optional `MARKETPLACE_BLOB_STORAGE_URL` and `MARKETPLACE_BLOB_STORAGE_CONTAINER`, `MARKETPLACE_SESSION_TTL_SECONDS`, `MARKETPLACE_TODAY`, optional `APPLICATIONINSIGHTS_CONNECTION_STRING`, and `ENABLE_SENSITIVE_DATA` (never true outside dev). The local Azurite connection string is not a cloud deployment setting, and Redis settings do not configure this lab's history backend. VERIFY the `agent.yaml` environment block format and the `azd env set` to container-env mapping against the azd extension output before the workshop.

## Environments and promotion
- `envs/.env.dev.example`, `.env.test.example`, `.env.prod.example`: placeholder-only templates that still contain legacy Redis settings; the nested workflow also forwards Redis rather than configuring shared Blob history. Do not treat them as a validated cross-replica or version-roll recipe for the Lab 2 target. `promote.py --execute` requires an untracked `envs/.env.<target>` with every value resolved; shared-history configuration and its deployment validation need a separately approved update.
- GitHub Environments `dev`, `test`, `prod` hold the values as variables (none are secrets). `test` and `prod` have required reviewers: that is the human approval for a deploy, the same idea as the advisor approval in Lab 3.
- Promotion is a `workflow_dispatch` with `target_environment`, or `python ./promote.py --to test --execute` from Lab 4 on the dev container. Both require a passing `artifacts/lab4/gate_result.json`; the workstation path prints and then runs one fail-fast Bash block.
- Rollback is a `workflow_dispatch` with `rollback_to=<tag>`: checks out the tag and runs `azd up` again. Hosted agent versions in the portal are the second rollback path (delete the bad version; `agent_reference` by name resolves to the latest active one). Message history can remain available across those operations only when the deployed Lab 2 versions use the same accessible shared Azure Blob history backend and compatible session configuration. Container-local files and the current Redis-oriented templates do not establish that continuity.

## What is deliberately not here
- Networking (private endpoints, VNet injection for the hosted agent), Key Vault (nothing to store: Entra only), APIM in front of the agent endpoint. the organization's landing zone owns these.
- Data pipelines for the knowledge base. The workshop uses `data/knowledge/*.md` checked in; production needs the SharePoint indexer or the Word-to-Markdown conversion job.
