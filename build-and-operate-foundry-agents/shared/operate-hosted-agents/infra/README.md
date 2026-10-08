# Infrastructure notes for the hosted-agent pipeline

What the pipeline expects to exist per environment (dev, test, prod), who creates it, and what `azd` creates on its own. No Bicep ships in this folder on purpose: the source workshop's `AgentOps/` material is only a reference, and the hosting organization will have its own landing zone. This file lists the contract the code has with the infrastructure.

## Per environment
| Resource | Created by | Used by | Notes |
|---|---|---|---|
| Foundry resource + project | platform team (Bicep in base repo `AgentOps/infra`) | every lab | `FOUNDRY_PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID` |
| Model deployment `gpt-5.4-mini` and `text-embedding-3-large` | platform team for pipeline targets; Lab 2 for learner deployments | hosted agents, judges, Lab 5 indexes | Names in `AZURE_AI_MODEL_DEPLOYMENT_NAME` / `EMBEDDING_MODEL_DEPLOYMENT_NAME`; raise TPM for the eval job (18 questions x up to 4 model calls) |
| Azure AI Search with Foundry IQ knowledge base `healthcare-marketplace-kb` + project connection | Lab 5 creates knowledge in the existing dev Search service; platform team in test/prod | hosted agent (`MARKETPLACE_KB_MCP_URL`) | Semantic ranker enabled; search service identity needs Cognitive Services OpenAI User + Cognitive Services User on the Foundry account |
| Azure Blob Storage account + container, when shared history is required | platform team, Entra auth | Lab 6 message history (`MARKETPLACE_BLOB_STORAGE_URL` and `MARKETPLACE_BLOB_STORAGE_CONTAINER`) | files are local teaching state; shared Blob history must be explicitly configured for deployed replica/version continuity; this does not migrate Labs 7-8's file-backed packet store |
| Application Insights connected to the project | platform team | Lab 9 tracing, hosted agent spans | `APPLICATIONINSIGHTS_CONNECTION_STRING` on the hosted agent through `azd env set` |
| Hosted agent `healthcare-marketplace-concierge-hosted` | `azd ai agent init` + `azd up` in the deploy job | Labs 3-6 and 9-10 | One azd environment per target: `healthcare-marketplace-concierge-dev`, `-test`, `-prod`; every `azd up` is a new version |
| Entra app with GitHub OIDC federated credentials | platform team | `azure/login@v2` in every Azure job | One per environment; subject `repo:<org>/<repo>:environment:<env>` |

## Roles the pipeline identity needs
| Scope | Role | Why |
|---|---|---|
| Foundry project | Azure AI User | run the model and the judges in the evaluate job |
| Foundry project | Foundry Project Manager | `azd ai agent init` / `azd up` (deploy and rollback jobs) |
| Foundry project | Foundry Agent Consumer | `test_local.py --deployed` smoke test |
| Foundry account | Cognitive Services OpenAI User | azure-ai-evaluation judges, embeddings |
| Search service | Search Index Data Reader | the evaluate job's local hosted/main.py calls the knowledge base MCP endpoint |
| Search service (dev) | Search Service Contributor + Search Index Data Contributor | Internal `catch_up.py --through 3` rebuilds indexes when they are missing; these are artifact group numbers, not learner labs |

## Roles the hosted agent's managed identity needs
| Scope | Role | Why |
|---|---|---|
| Foundry project | Azure AI User | `FoundryChatClient` model calls with `DefaultAzureCredential` |
| Search service | Search Index Data Reader | `MCPStreamableHTTPTool` to the knowledge base with the Entra bearer |
| Azure Blob container or account, when shared history is configured | Storage Blob Data Contributor | Lab 6 message history, using the hosted agent's dedicated Entra agent identity |

Propagation takes 5 to 15 minutes. The first pipeline run after a role change usually fails with 403; re-run.

## Hosted agent environment variables
`azd ai agent init` writes `agent.yaml` next to `hosted/main.py`; do not check it in unless the extension needs it (document the choice). The Lab 6 container reads: `FOUNDRY_PROJECT_ENDPOINT` (injected by Foundry), `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `MARKETPLACE_KB_MCP_URL`, optional `MARKETPLACE_BLOB_STORAGE_URL` and `MARKETPLACE_BLOB_STORAGE_CONTAINER`, `MARKETPLACE_SESSION_TTL_SECONDS`, `MARKETPLACE_TODAY`, optional `APPLICATIONINSIGHTS_CONNECTION_STRING`, and `ENABLE_SENSITIVE_DATA` (never true outside dev). The local Azurite connection string is not a cloud deployment setting, and Redis settings do not configure this lab's history backend. VERIFY the `agent.yaml` environment block format and the `azd env set` to container-env mapping against the azd extension output before the workshop.

## Environments and promotion
- `envs/.env.dev.example`, `.env.test.example`, `.env.prod.example`: placeholder-only templates for the reused Lab 6 product, including optional Blob history settings forwarded by the nested workflow. Configuration alone is not validated cross-replica or version-roll continuity. Internal `promote.py --execute` requires an untracked `envs/.env.<target>` with every value resolved; shared-history access and deployment still require approved live validation.
- GitHub Environments `dev`, `test`, `prod` hold the values as variables (none are secrets). `test` and `prod` have required reviewers: that is the human approval for a deploy, the same idea as the advisor approval in Lab 8.
- Actual promotion is an administrator-owned `workflow_dispatch` with `target_environment`, or internal `python ./promote.py --to test --execute` from this topic folder in the dev container. Both require a passing `artifacts/lab5/gate_result.json`; the workstation path prints and then runs one fail-fast Bash block. Lab 10 performs only a dry-run promotion and rollback rehearsal.
- Rollback is a `workflow_dispatch` with `rollback_to=<tag>`: checks out the tag and runs `azd up` again. Hosted agent versions in the portal are the second rollback path (delete the bad version; `agent_reference` by name resolves to the latest active one). Message history can remain available across those operations only when the deployed Lab 6 versions use the same accessible shared Azure Blob history backend and compatible session configuration. Container-local files and placeholder settings do not establish that continuity.

## What is deliberately not here
- Networking (private endpoints, VNet injection for the hosted agent), Key Vault (nothing to store: Entra only), APIM in front of the agent endpoint. the organization's landing zone owns these.
- Data pipelines for the knowledge base. The workshop uses `data/knowledge/*.md` checked in; production needs the SharePoint indexer or the Word-to-Markdown conversion job.
