# Setup: Build and Operate Foundry Agents

## 1. Open the repository dev container

Use the repository-level dev container, not a separate workshop container. Docker Desktop
(Linux containers) and the VS Code Dev Containers extension are required locally.
GitHub Codespaces is an alternative when your organization's policy and Azure network allow it.

1. Open the repository root and select **Dev Containers: Reopen in Container**.
2. Wait for bootstrap to finish. It installs the root Python 3.14 dependency lock, the
   `azure.ai.agents` azd extension and checks the learner toolchain.
3. Select `/usr/local/bin/python` as the notebook kernel. Use a **Bash** terminal.
4. Copy `.env.example` to `.env` at the repository root, fill in the project settings, and set
   `MARKETPLACE_RESOURCE_SUFFIX` to a short value unique to you, such as `jd-4821`.
5. Sign in inside the container; host credentials are not mounted:

```bash
cd /workspaces/agentic-ai-immersion
cp -n .env.example .env
az login --use-device-code --tenant '<tenant-id>'
az account set --subscription '<subscription-id>'
azd config set auth.useAzCliAuth true
python build-and-operate-foundry-agents/tools/preflight.py
cd build-and-operate-foundry-agents
```

The shared permission setup remains PowerShell 7, which is installed in the container.
Use `pwsh -File ../scripts/setup-permissions.ps1` with the parameters documented in the
[repository setup guide](../README.md). Do not grant roles or alter networking without approval.

### Notebook kernel and bootstrap recovery

No additional virtual environment is required inside the dev container. Choose **Select Kernel >
Python Environments > `/usr/local/bin/python`**. Do not select a Windows interpreter or a venv
left over from a native setup.

If VS Code reports that `ipykernel` is missing, check the Dev Containers setup output: the container
can be running even when its package bootstrap failed. From the container's Bash terminal:

```bash
cd /workspaces/agentic-ai-immersion
bash .devcontainer/bootstrap.sh
python -c "import sys, ipykernel; print(sys.executable, ipykernel.__version__)"
```

After bootstrap succeeds, reselect the interpreter or reload the VS Code window. The bootstrap
script must have LF line endings in the working tree; `.devcontainer/.gitattributes` enforces LF
for Git checkouts, and offline validation rejects carriage returns. The shared dependency lock
uses platform markers for Windows-only notebook packages so Linux skips them.

### Local history stores and agent networking

Compose starts Redis and the Azurite Blob emulator without publishing their ports to the host.
`.env.example` sets `MARKETPLACE_REDIS_URL=redis://redis:6379/0` for optional generic shared-store
configurations and the Lab 4 infrastructure template; Labs 2 and 3 and Stretch 6 do not use it.
Lab 2 uses Azure Blob/Azurite or local files for message history, and Lab 3 uses a file-backed session map.
Azurite is available for optional local Blob-backend testing; Lab 2's README has its connection
string. Named Compose volumes retain both services' data across container restarts.

The local agent listens on port 8088; VS Code forwards it for host/browser use. Notebooks
inside the dev container call `http://localhost:8088` directly.

**Do not deploy local Redis or Azurite connection strings to Foundry.** The deployment helper
omits both. For Lab 2, Azure Blob is optional: set `MARKETPLACE_BLOB_STORAGE_URL` to an existing
account and container, and grant the hosted identity Storage Blob Data Contributor. Without Blob
configured, Lab 2 uses container-local files and does not claim continuity across replicas.
Other labs may use an Azure-reachable shared Redis endpoint.

### Working directories and runtimes

Open each walkthrough in its lab folder. Notebook paths assume that folder is the kernel's
working directory. Alternatively, from this workshop folder:

```bash
cd labs/lab1-hosted-agent-basics
python -m jupyter lab lab1_walkthrough.ipynb
```

Notebooks and driver scripts run in the learner dev container. `hosted/main.py` runs there
for local tests; Foundry separately builds and runs the deployed package.
Every hosted `prepare.py` vendors shared code/data before upload. Run deployment commands only
from the printed Bash block; printing alone never deploys.

Environment loading preserves exported variables, then reads the repository-root `.env`,
the workshop `.env`, and the current directory `.env`, in that precedence order.
Keep shared learner configuration in the repository root.

### Optional native setup

The supported workshop path is the dev container. For native Python 3.14 development, install
the root `requirements.txt`, Azure CLI, azd and its `azure.ai.agents` extension yourself.
The deployment command generators target Bash; run them in Linux/WSL or the dev container.
Do not paste Linux container paths into a Windows PowerShell terminal.

## 2. Environment variables

| Variable | Used by | Example shape (no real values here) | Notes |
|---|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | all | `https://<account>.services.ai.azure.com/api/projects/<project>` | Foundry portal, project Overview page. Required by every lab |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | all | `gpt-5.4-mini` | Chat model deployment name. Default `gpt-5.4-mini` |
| `FOUNDRY_MODEL` | hosted agents | `gpt-5.4-mini` | Agent Framework model name; defaults to `AZURE_AI_MODEL_DEPLOYMENT_NAME` |
| `EMBEDDING_MODEL_DEPLOYMENT_NAME` | Lab 2 | `text-embedding-3-large` | 3072 dimensions; the index schema assumes this model |
| `AZURE_AI_SEARCH_ENDPOINT` | Lab 2 | `https://<search>.search.windows.net` | Basic tier or above, semantic ranker enabled |
| `AZURE_OPENAI_ENDPOINT` | Lab 2, Lab 4 judges | `https://<account>.openai.azure.com/` | Only the resource host is used; `/openai/...` suffixes are stripped |
| `PROJECT_RESOURCE_ID` | Lab 2 (project connection PUT), every `azd ai agent init` | `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>` | ARM id of the project |
| `TENANT_ID` | all | `<guid>` | Passed to `AzureCliCredential(tenant_id=...)` and `az login --tenant` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Lab 4, hosted agents | `InstrumentationKey=...;IngestionEndpoint=...` | Optional on the workstation (Lab 4 fetches it from the project when blank). On the hosted agent it is set with `azd env set` and turns the container's tracing on |
| `MARKETPLACE_TODAY` | all | `2026-10-06` | Workshop "today" for enrollment-window answers. See section 9 |
| `MARKETPLACE_KB_MCP_URL` | Lab 2 hosted agent, Lab 4, CI | `https://<search>.search.windows.net/knowledgebases/healthcare-marketplace-kb/mcp?api-version=2025-11-01-Preview` | The knowledge base MCP endpoint. Written to `artifacts/lab2/knowledge.json` by Lab 2; the lab passes it to the local `main.py`; `azd env set MARKETPLACE_KB_MCP_URL ...` for the container |
| `MARKETPLACE_BLOB_STORAGE_URL` | Lab 2 hosted agent (conversation history) | `https://<account>.blob.core.windows.net` | Optional existing account URL. Uses DefaultAzureCredential and the existing `MARKETPLACE_BLOB_STORAGE_CONTAINER`; Blob takes precedence for conversation history |
| `MARKETPLACE_BLOB_STORAGE_CONTAINER` | Lab 2 hosted agent (conversation history) | `marketplace-history` | Existing Blob container. The lab does not create cloud storage resources |
| `MARKETPLACE_AZURITE_CONNECTION_STRING` | Lab 2 local Blob tests | Azurite connection string | Local emulator only; never sent to Foundry |
| `MARKETPLACE_REDIS_URL` | Optional generic shared-store configuration; Lab 4 infrastructure template | `redis://redis:6379/0` locally; `rediss://<name>.<region>.redis.azure.net:10000/0` for Azure Managed Redis | Labs 2 and 3 and Stretch 6 do not use this setting |
| `MARKETPLACE_RESOURCE_SUFFIX` | every created resource | `jd-4821` | Required, unique per attendee, 1-16 lowercase letters/numbers/hyphens. Every workshop-created Azure resource ends with this suffix |
| `MARKETPLACE_SESSION_TTL_SECONDS` | Redis and Blob message stores | `604800` | Idle message-history expiry, default 7 days |
| `MARKETPLACE_HOSTED_PORT` | local `main.py` | `8088` | Only for running two local replicas in the Lab 2 YOUR TURN |
| `MARKETPLACE_WORKFLOW_AGENT_NAME` | Stretch 5 hosted tool | `healthcare-marketplace-triage-workflow` | Lets the hosted agent find the workflow agent without the artifacts file |
| `MARKETPLACE_SESSION_DIR` | Lab 3 hosted agent (local) | `labs/artifacts/lab3/sessions` | File-backed session map; the Lab 3 driver sets it so pending packets are visible next to the artifacts |
| `MARKETPLACE_INVOCATIONS_PATH` | Stretch 6 client | `/invocations` | Path the local `InvocationsHostServer` serves (VERIFY); `test_local.py` also tries `/invoke` and `/` |
| `SKILL_NAMES` | Stretch 6 skills agent | `hra-reimbursement-rules` | Comma list of `skills/<name>/SKILL.md` to embed; unset embeds every skill in the folder |
| `TOOLBOX_NAME`, `TOOLBOX_MCP_URL` | Stretch 6 skills agent (preview) | `agent-tools`, `https://.../mcp` | Foundry Toolbox with web_search + code_interpreter over MCP; unset disables the toolbox, the agent still runs |
| `MARKETPLACE_AGENT_NAME` | Stretch 6 skills agent | `healthcare-marketplace-concierge-hosted` | Override the agent name when you do not want the skills build to become a new version of the concierge |

`MARKETPLACE_*` variables hold no secrets. Every lab README lists the ones it reads.

## 3. Model deployments

Deploy in the Foundry project, in a region that offers Agent Service, Foundry IQ and evaluations (the base
repo datasheet lists tested regions):

| Deployment | Purpose | Notes |
|---|---|---|
| `gpt-5.4-mini` (or the name you put in `AZURE_AI_MODEL_DEPLOYMENT_NAME`) | every agent, the evaluators' grader model, the label_model criteria | Global Standard, 100K+ TPM for a room of 20. Raise quota before the day |
| `text-embedding-3-large` | knowledge indexes (Lab 2) | 3072 dimensions |
| (no other deployments) | | The hosted agents and the evaluation judges share `gpt-5.4-mini` |

The hosted agents in Labs 1-3 and Stretch 6 retry model 429 responses up to five times, honor Azure's
`retry-after-ms` or `retry-after` header, and log any request/token limit and remaining-budget headers returned by
the service. A quota increase can take several minutes to propagate; if throttling persists after the retries,
compare those runtime headers with the deployment's quota allocation in Foundry.

## 4. Azure resources and connections

To provision a complete private workshop environment instead of using existing
shared resources, follow the Terraform deployment in
[`infra/README.md`](infra/README.md). Its outputs map directly to the environment
variables in section 2. Because every data-plane endpoint is private, connect the
learner workstation to the deployed virtual network before running preflight or
the labs.

| Resource | Needed by | Setup |
|---|---|---|
| Foundry account + project | all | Create the project first; copy `FOUNDRY_PROJECT_ENDPOINT` and `PROJECT_RESOURCE_ID` |
| azd + `azure.ai.agents` extension | Labs 1 to 4, S6 (every hosted deploy) | `azd config set auth.useAzCliAuth true`, `azd extension install azure.ai.agents`. Deployer needs Foundry Project Manager on the project |
| Azure AI Search with Foundry IQ | Lab 2 (and every later lab through `MARKETPLACE_KB_MCP_URL`) | Enable system-assigned managed identity on the search service. Semantic ranker: free or standard |
| Project connection to the Foundry IQ knowledge base | Lab 2 | Created by the lab code with an ARM PUT on `{PROJECT_RESOURCE_ID}/connections/healthcare-marketplace-kb-connection` (authType ProjectManagedIdentity, category RemoteTool). Needs a role that can write connections (Azure AI Owner or Contributor on the account) |
| Redis | Optional generic shared-store configurations; Lab 4 infrastructure template | Locally the dev-container Redis companion service and `MARKETPLACE_REDIS_URL=redis://redis:6379/0`. Azure: Azure Managed Redis with Entra auth (`rediss://`). Not required by Labs 2 or 3 or Stretch 6 |
| Azure Blob Storage | Optional Lab 2 shared conversation history | Use an existing account and container, set `MARKETPLACE_BLOB_STORAGE_URL`; the lab does not provision storage resources |
| Application Insights | Lab 4 and the hosted agents' tracing | Connect it to the project (Foundry portal: project, Tracing, connect) so `telemetry.get_application_insights_connection_string()` works; set the complete connection string in the root `.env` and, for deployment, on the hosted agent with `azd env set`. Confirm publishing permissions and network access below before Lab 4 |
| GitHub repository with Environments `dev`, `test`, `prod` and an Entra app with OIDC federated credentials | Lab 4 pipeline (optional on the day) | See `labs/lab4-operate-hosted-agents/infra/README.md` |
| Foundry Toolbox (preview) | Stretch 6 skills agent, optional | Create a Toolbox with `web_search` and `code_interpreter` in the project (base repo `AgentOps/src/tools/toolbox_config.py` pattern), set `TOOLBOX_NAME` and `TOOLBOX_MCP_URL` on the hosted agent. Region-limited; skip if unavailable |

## 5. RBAC

Run the base repo RBAC script first, then confirm these. Propagation takes 5 to 15 minutes; the most common
"it does not work" on the day is a role that was assigned 3 minutes ago.

| Principal | Scope | Role | Why |
|---|---|---|---|
| Attendee (user) | Foundry account or project | Azure AI User (minimum) or Azure AI Developer | Create agents, conversations, evals |
| Attendee | Foundry project | Azure AI Owner or Contributor (Lab 2 only) | ARM PUT of the project connection |
| Attendee (deployer) | Foundry project | Foundry Project Manager | `azd ai agent init` / `azd up` of a hosted agent (every lab); one proctor can deploy for the room |
| Attendee | Azure AI Search service | Search Service Contributor + Search Index Data Contributor | Create indexes, knowledge sources, knowledge base; upload documents |
| Attendee | Application Insights | Monitoring Reader (or Reader) | Read traces in the portal |
| Local publishing identity selected by `DefaultAzureCredential` (usually the attendee's Azure CLI user) | Destination Application Insights resource | Monitoring Metrics Publisher | Publish Lab 4 notebook and local hosted-server telemetry; Owner alone does not grant this data-plane permission |
| Deployed hosted agent identity (when tracing is enabled) | Destination Application Insights resource | Monitoring Metrics Publisher | Publish telemetry from the deployed container |
| Project managed identity | Azure AI Search service | Search Index Data Reader | Agent calls the knowledge base MCP endpoint through the connection |
| Search service managed identity | Foundry account | Cognitive Services OpenAI User AND Cognitive Services User | Vectorizer and knowledge base answer synthesis call the models |
| Invokers of a hosted agent | Foundry project | Foundry Agent Consumer or Foundry User | Call the deployed Responses endpoint (`hosted/test_local.py --deployed`) |
| Hosted agent managed identity | Foundry project | Azure AI User | `FoundryChatClient` model calls from the container |
| Hosted agent managed identity | Azure AI Search service | Search Index Data Reader | `MCPStreamableHTTPTool` to the knowledge base (Lab 2 onwards) |
| Hosted agent managed identity | Azure Managed Redis (test/prod) | Redis data access policy (Entra) | only when a deployment explicitly configures the generic Redis backend |
| Hosted agent managed identity (optional Lab 2 Blob backend) | Azure Storage account/container | Storage Blob Data Contributor | read/write Lab 2 conversation-history blobs |
| Attendee | Azure OpenAI / Foundry account | Cognitive Services OpenAI User | Lab 4 judges (`azure-ai-evaluation`) and Lab 2 embeddings |
| Hosted agent managed identity (`healthcare-marketplace-concierge-hosted`, skills version) | Foundry project / Toolbox | Access to the Toolbox MCP endpoint (VERIFY the exact role) | `MCPStreamableHTTPTool` calls to web_search / code_interpreter (Stretch 6, preview) |

### Lab 4 tracing prerequisites

Before running a traced evaluation or Step 4.11, verify:

- **Publishing permission:** the identity selected by `DefaultAzureCredential` has **Monitoring Metrics Publisher**
  on the destination Application Insights resource or an inherited scope. For local runs this is usually the
  Azure CLI signed-in user; for a deployed hosted agent, grant it to the agent identity as well.
- **Owner is not sufficient:** Owner grants management-plane access, but telemetry ingestion requires the
  data-plane `Microsoft.Insights/Telemetry/Write` action. Reader, Monitoring Reader, and Foundry roles also do not
  replace the publishing role. The shared permission script does not assign this Application Insights role.
- **Assignment and propagation:** with approval, use **Application Insights > Access control (IAM) > Add role
  assignment > Monitoring Metrics Publisher**, select the publishing identity, and allow RBAC propagation.
  Ask the resource administrator if you cannot assign roles.
- **Connection and network:** use the complete connection string from the resource's **Overview** in the root
  `.env`. If public ingestion is disabled, the dev container needs the approved private network path, private
  DNS, and Azure Monitor Private Link Scope access. Publishing permissions do not bypass network restrictions;
  do not enable public ingestion simply to bypass an error.
- **Fresh verification:** restart the notebook kernel after configuration changes, rerun Steps 4.1-4.6 and
  Step 4.11, then match its printed trace ID in Application Insights > Logs. Older records and a local PASS
  message do not establish that the current run was ingested.

## 6. Python packages

Python 3.14 (the repository dev-container interpreter). The base repo's pinned requirements cover `azure-ai-projects` 2.x, `openai`,
`azure-identity`, `azure-monitor-opentelemetry`, `python-dotenv`, `pydantic`, `requests`, `httpx`.

| Where | File | Contents |
|---|---|---|
| Workstation (notebooks, driver scripts, running `main.py` locally) | `labs/requirements.txt` (`python -m pip install -r labs/requirements.txt`) | Delegates to the repository root `requirements.txt`; no second workstation lock |
| Container (each hosted agent) | `labs/labN-*/hosted/requirements.txt` | minimal explicit pins: `agent-framework`, `agent-framework-foundry`, `agent-framework-foundry-hosting`, `azure-ai-projects`, `azure-identity`, `python-dotenv`, plus `httpx`, `redis` (not in Lab 2), and `azure-monitor-opentelemetry` where used. Never `agent-framework[foundry]` |
| Tools | `azd` + `azure.ai.agents` extension, Docker Desktop (dev container, local Redis and Azurite) | |

`common/marketplace_data.py`, `common/guardrails.py`, `common/session_store.py` and `common/message_store.py` need
nothing beyond the standard library for their self-tests, which is how they run on a laptop with no Azure packages.
Notebooks are generated from the scripts with `python tools/py_to_ipynb.py <script.py>`; nbformat is not required.

## 7. Five-minute verification

Run from the base repo root inside the dev container, after `az login --tenant $TENANT_ID`.

```bash
cd build-and-operate-foundry-agents

# 1. Data and helpers, no Azure needed. Expect "ALL CHECKS PASSED" and two "PASS" lines.
python common/marketplace_data.py
python common/session_store.py
python common/message_store.py

# 2. Environment variables resolved (blank values are printed as "(blank)").
python common/foundry_env.py

# 3. Foundry project reachable with your identity (lists model deployments and agents).
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from common import foundry_env
project = foundry_env.get_project_client()
print("deployments:", [d.name for d in project.deployments.list()])
openai_client = foundry_env.get_openai_client(project)
r = openai_client.responses.create(model=foundry_env.model_name(), input="Reply with the single word ready.")
print("model says:", r.output_text)
EOF

# 4. Search endpoint reachable (Lab 2 only).
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from common import foundry_env
from azure.search.documents.indexes import SearchIndexClient
env = foundry_env.load_env()
client = SearchIndexClient(env["AZURE_AI_SEARCH_ENDPOINT"], foundry_env.get_credential())
print("indexes:", [i for i in client.list_index_names()])
EOF
```

```bash
# 5. Hosted agent toolchain (Labs 1 to 4).
azd version && azd extension list | grep azure.ai.agents
python -c "import agent_framework, agent_framework_foundry_hosting; print('agent framework ok')"
```

Expected: step 1 ends with `ALL CHECKS PASSED` and `PASS`; step 3 prints your deployment names and `model says: ready`
(or a close variant); step 4 prints a list, possibly empty. A 401 or 403 in step 3 or 4 is RBAC or the wrong
tenant; see the troubleshooting table in every lab README.


Hosted folders build without Azure. Expect "wrote artifacts/lab1/hosted.json", "...lab3/hosted.json", and three claim packets:

```bash
python labs/lab1-hosted-agent-basics/lab1_hosted_basics.py --skip-demo
python labs/lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py --skip-demo --standalone
python labs/stretch6-invocations-toolbox-skills/stretch6_invocations.py --offline
python labs/stretch6-invocations-toolbox-skills/hosted-invocations/test_local.py --offline
```

### Agent names used by these labs

| Agent | Lab | Protocol | Folder |
|---|---|---|---|
| `healthcare-marketplace-concierge-hosted-<suffix>` | 1 (v1), 2 (v2), S6 skills build (optional new version) | responses | `lab1-hosted-agent-basics/hosted/`, `lab2-hosted-knowledge-sessions/hosted/`, `stretch6-.../hosted-responses-skills/` |
| `healthcare-marketplace-triage-hosted-<suffix>` | 3 | responses | `lab3-hosted-multi-agent-handoff/hosted/` |
| `healthcare-marketplace-claims-review-invocations-<suffix>` | S6 | invocations | `stretch6-.../hosted-invocations/` |

## 8. Proctor smoke test, the day before

Do this on the exact room account and network you will use. Tick every line.

- [ ] `az login --tenant <TENANT_ID>` works on the room laptops and in the dev container; no MFA prompt loops.
- [ ] `.env` at the base repo root has every variable in section 2 filled, `MARKETPLACE_TODAY` included.
- [ ] Model quota: `gpt-5.4-mini` at 100K+ TPM, `text-embedding-3-large` deployed. Run the section 7 snippet.
- [ ] RBAC table (section 5) applied at least 30 minutes ago; project managed identity and search identity
      roles verified in the portal, not assumed.
- [ ] Application Insights connected to the project; a test trace shows up in the portal.
- [ ] Local and deployed telemetry publishers have Monitoring Metrics Publisher on the destination Application
      Insights resource; Owner access is not being mistaken for ingestion permission.
- [ ] The room/dev-container network can reach the allowed ingestion path, including private DNS and Azure Monitor
      Private Link Scope access when public ingestion is disabled.
- [ ] `cd labs && python catch_up.py --through 2`, then `python lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py --demo-only`:
      `continuity check: OK` with two pids and a [KB-MKT-001] citation in turn 2.
- [ ] One proctor has deployed `healthcare-marketplace-concierge-hosted` with `azd up` on the room project and
      `python labs/lab2-hosted-knowledge-sessions/hosted/test_local.py --deployed` prints `PASS`; the version shows
      `active` in the portal. Note how long the first build took.
- [ ] `azd` login and the `azure.ai.agents` extension install on the room network without a proxy error.
- [ ] Docker Desktop runs the dev container and `redis:7-alpine` on the room laptops if using the base repo's Redis thread example or a generic Redis-backed store.
- [ ] `python labs/lab4-operate-hosted-agents/lab4_operate.py --limit 3 --skip-judges` passes and a
      `marketplace.golden_question` span shows up in Application Insights.
- [ ] Remote attendees: the recording and screen share show the terminal font at a readable size; the
      Foundry portal tabs you will click through are bookmarked.
- [ ] `data/` is untouched (`git status` clean) so every table shows the same numbers on every laptop.
- [ ] A throwaway `healthcare-marketplace-concierge-unsafe` agent (the "break the guardrail on purpose" YOUR TURN) has been
      created and deleted once, so you know how the model behaves without the compliance block.

## 9. MARKETPLACE_TODAY

Enrollment windows depend on the date. The labs read `MARKETPLACE_TODAY` (ISO date) through `common/marketplace_data.py` so
every attendee gets the same answer regardless of the real date. The default `2026-10-06` is nine days before
the Annual Enrollment Period opens, which makes the S1 answer "AEP opens October 15" with an SEP reminder.

| `MARKETPLACE_TODAY` | S1 Evelyn (Medicare, MA) | S3 Rosa (pre-Medicare) |
|---|---|---|
| `2026-10-06` (default) | SEP-possible, next window AEP 2026-10-15 to 2026-12-07 | SEP-possible, next window ACA OEP 2026-11-01 |
| `2026-10-20` | AEP | SEP-possible |
| `2026-11-15` | AEP | OEP (ACA open enrollment) |
| `2027-02-10` | OEP (MA open enrollment) | SEP-possible |
| `2027-09-01` | SEP-possible | IEP (turns 65 on 2027-11-20) |

Set it in `.env` or inline: `MARKETPLACE_TODAY=2026-10-20 python labs/lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py --demo-only`.
The hosted `main.py` reads it too (`azd env set MARKETPLACE_TODAY ...` for the container). Tests and demos that need a
fixed answer pass `today="..."` to `get_enrollment_window` directly.

## 10. Clean up workshop resources

Cleanup never deletes the shared Foundry project, model deployments, Search service, Redis service,
or resource group. It targets only agents, evaluations, indexes, knowledge sources, the knowledge
base, and the project connection created by this workshop. Every command is a dry run unless
`--execute` is present.

Preview and then delete only resources ending in your configured suffix:

```bash
python tools/cleanup_workshop.py
python tools/cleanup_workshop.py --execute
```

A facilitator can preview all suffixed workshop resources in the configured project and Search
service. Deleting that full set requires the exact Foundry project name as an additional guard:

```bash
python tools/cleanup_workshop.py --scope all
python tools/cleanup_workshop.py --scope all --execute --confirm-all '<project-name>'
```
