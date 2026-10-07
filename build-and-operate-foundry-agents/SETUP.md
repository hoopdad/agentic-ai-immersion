# Setup: Build and Operate Foundry Agents

## 1. Open the repository dev container

Use the repository-level Python 3.14 dev container, not a separate workshop
environment. Locally, Docker Desktop (Linux containers) and the VS Code Dev
Containers extension are required. GitHub Codespaces is supported when your
organization's policy and Azure network allow it.

1. Open the repository root and select **Dev Containers: Reopen in Container**.
2. Wait for bootstrap to finish installing the root dependency lock and toolchain.
3. Open `labs/lab1-foundry-project-models/lab1_walkthrough.ipynb` beneath this workshop.
4. Select **Select Kernel > Python Environments > `/usr/local/bin/python`**.
5. Edit the notebook's setup inputs using values supplied by your administrator,
   then run its authentication, provisioning, verification and persistence cells in order.

No extra virtual environment, manual `.env` copy, terminal driver or standalone
test helper is part of the learner path. Do not select a Windows interpreter or
a native-setup environment. If bootstrap or kernel selection fails, inspect the
Dev Containers setup output and ask the facilitator to repair the repository
environment before continuing.

## 2. Administrator prerequisites

Lab 1 creates a **project inside an existing Foundry account**, not a new account
or a complete enterprise network. The administrator supplies the account,
subscription, tenant, resource group, allowed region, approved network path and
permissions to create the project and model deployments. Confirm model
availability and quota before the session.

Shared permission administration remains valid: an authorized administrator
uses `scripts/setup-permissions.ps1` and its documented parameters in the
[repository setup guide](../README.md). This is permission setup, not an
alternative way to execute a lab. Never change roles or networking without approval.

For a private workshop environment, administrators can follow
[`infra/README.md`](infra/README.md). Learner kernels must already be able to
reach its private endpoints. Do not enable public access to bypass a blocked path.

| Shared prerequisite | Needed by | Owner |
|---|---|---|
| Existing Foundry account, approved model quota and creation permissions | Lab 1 | Account administrator |
| Azure AI Search with managed identity, semantic ranker and Foundry IQ support | Lab 3 and later knowledge consumers | Search administrator |
| Existing Blob account/container, if shared history is requested | Optional Lab 3 shared history | Storage administrator |
| Application Insights connected to the learner project, with approved ingestion access | Lab 5 | Telemetry administrator |
| OIDC and protected GitHub Environments | Optional Lab 5 cloud pipeline | Release administrator |
| Foundry Toolbox endpoint and access | Optional Stretch 7 preview | Project administrator |

## 3. Notebook inputs and downstream persistence

Enter configuration in Lab 1's editable input cell; later walkthroughs provide
their own relevant exercise inputs. Lab 1 resolves and writes downstream
configuration to the repository-root `.env`. That file remains the persistence
contract, not a manual prerequisite to copy or populate first. Do not commit
`.env`, tokens, local deployment state or executed notebook outputs.

| Configuration | Meaning |
|---|---|
| Tenant, subscription, resource group and existing Foundry account | Approved management scope and authentication context |
| Project name and unique attendee suffix | Learner project/resource ownership; retain the same suffix across labs |
| Chat deployment and embedding deployment choices | Names, supported model versions and capacity used by agents and retrieval |
| `FOUNDRY_PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID`, `AZURE_OPENAI_ENDPOINT` | Resolved endpoints and project ARM identity persisted for downstream notebooks |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `EMBEDDING_MODEL_DEPLOYMENT_NAME` | Provisioned deployment names; retrieval assumes `text-embedding-3-large` with 3072 dimensions |
| `AZURE_AI_SEARCH_ENDPOINT` | Administrator-supplied Search service for Lab 3 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Complete approved telemetry destination for Lab 5, or resolve it from the project connection |
| `MARKETPLACE_RESOURCE_SUFFIX`, `MARKETPLACE_TODAY` | Attendee resource isolation and reproducible scenario date |
| Optional Blob account URL and container | Existing shared message-history service for Lab 3, using Entra credentials |

### Administrator infrastructure variants

To provision a complete workshop environment instead of using existing shared
resources, choose a Terraform variant in [`infra/README.md`](infra/README.md):

- [`infra/privatelink/`](infra/privatelink/README.md) keeps the private deployment.
  Connect the learner workstation to its virtual network, with private DNS
  resolution, before running preflight or the labs.
- [`infra/public-network/`](infra/public-network/README.md) uses public endpoints,
  with all network sources allowed on Foundry, Storage, Cosmos DB and AI Search
  so the managed agent runtime can reach its dependencies. Existing Entra/RBAC
  controls remain in place; public reachability does not grant data access.
  Key Vault and ACR deny other sources and require
  `allowed_public_ipv4_cidrs` for the actual operator/CI outbound public IPs.
  Replace the example's `<your-public-egress-ip>/32` placeholder before applying;
  empty, `/0`, private and reserved ranges are rejected. Application Insights
  and Log Analytics permit public ingestion/query as an explicit exception:
  they have no native source-IP allowlist. This variant is not network-isolated.

Run Terraform from the selected variant directory, not the `infra/` root. Both
variants expose the same downstream workshop configuration contract; keep their
state and local tfvars separate. Review the selected variant's networking and
hosted-agent limitations before deployment.

Knowledge MCP endpoints and agent/version references are produced by the
notebooks and passed through checkpoint artifacts. They are not values learners
must invent. Optional Toolbox configuration belongs in Stretch 7's editable inputs.
Do not deploy Azurite's local emulator settings to Foundry.

## 4. Project and model setup: Lab 1

The new Lab 1 notebook authenticates, creates or resolves the project, provisions
chat and embedding deployments, verifies readiness and persists their settings.
Review the selected model/version, deployment names and capacity before the
provisioning cell. Account permissions and quota do not become available merely
because a notebook input is filled in.

| Deployment | Purpose | Teaching constraint |
|---|---|---|
| Configured chat deployment, such as `gpt-5.4-mini` | Agent reasoning and evaluation judges | A room shares quota; plan capacity with the administrator rather than assuming a fixed allocation works everywhere |
| `text-embedding-3-large` | Lab 3 retrieval indexes | 3072 dimensions; changing the model requires matching the index schema |

Model throttling retries honor Azure retry headers. If repeated 429s persist,
inspect runtime limit headers and the deployment allocation with the administrator.
A quota change can take time to propagate.

## 5. Identity and RBAC

Local notebook and hosted-model calls use `DefaultAzureCredential`; deployed
containers use their dedicated agent identity. Management-plane provisioning,
data-plane inference, Search retrieval and telemetry publishing are separate
permissions. Allow propagation before retesting.

| Principal | Scope | Required access |
|---|---|---|
| Learner creating the project/models | Existing Foundry account and approved management scope | Administrator-approved project/model creation rights |
| Learner developing agents | Foundry project | Azure AI User or Azure AI Developer, as appropriate |
| Learner creating the Lab 3 project connection | Foundry account/project | Connection-write permission, such as Azure AI Owner or Contributor at the appropriate scope |
| Hosted deployer | Foundry project | Foundry Project Manager |
| Hosted invoker | Foundry project | Foundry Agent Consumer or Foundry User |
| Learner creating knowledge resources | Search service | Search Service Contributor and Search Index Data Contributor |
| Project and hosted agent identities retrieving knowledge | Search service | Search Index Data Reader |
| Search managed identity invoking embeddings/answer synthesis | Foundry account | Cognitive Services OpenAI User and Cognitive Services User |
| Hosted agent invoking the model | Foundry project | Azure AI User |
| Learner running embedding calls/evaluation judges | Foundry account | Cognitive Services OpenAI User |
| Hosted agent using optional shared Blob history | Existing Blob account/container | Storage Blob Data Contributor |
| Telemetry reader | Application Insights | Monitoring Reader or Reader |
| Local and deployed telemetry publishers | Application Insights | Monitoring Metrics Publisher |

Toolbox access is preview-specific: verify the endpoint's required role and
token audience with its administrator rather than assuming model access grants
tool access.

### Lab 5 tracing prerequisites

- Confirm **Monitoring Metrics Publisher** for the identity selected locally by
  `DefaultAzureCredential` and for the deployed agent when tracing its container.
  **Owner alone is insufficient:** ingestion needs the data-plane
  `Microsoft.Insights/Telemetry/Write` action. The shared permission script does
  not assign this Application Insights publishing role.
- Use the complete connection string in notebook configuration and confirm
  Application Insights is actually connected to the project.
- With private ingestion, verify the approved network path, private DNS and
  Azure Monitor Private Link Scope access. Permissions do not bypass network rules.
- After changes, restart the kernel, rerun prerequisite and tracing cells, and
  match the newly printed trace ID in Application Insights > Logs. A local PASS
  or an older portal record is not evidence of current Azure ingestion.

## 6. Notebook execution and recovery

Open each walkthrough in its own lab folder and run prerequisite cells first.
The notebook manages local servers on port 8088, readiness probes, package
preparation and process cleanup. Foundry separately builds and runs the uploaded
Python product package. Deployment is an explicit notebook action; review its
target before running it and wait for an `active` version before invocation.

If an earlier artifact is missing, return to its producing notebook and rerun
the checkpoint cells. If a server or kernel fails, inspect the saved local log,
stop only the identified process through the notebook's lifecycle controls,
then rerun the preparation and readiness cells. Restart kernels after changing
persisted configuration so a stale environment does not mask the change.

## 7. Facilitator readiness rehearsal

Rehearse the notebooks on the exact room account and network; offline CI does
not prove any of these live outcomes.

- [ ] Dev-container bootstrap and Python 3.14 kernel selection succeed.
- [ ] Lab 1 authenticates, creates/resolves the project, provisions both models,
      verifies access and writes downstream configuration.
- [ ] Roles and approved network paths are effective for learner, project,
      Search and hosted agent identities.
- [ ] Lab 2 passes local safety checks, deploys a version and invokes it when active.
- [ ] Lab 3 produces cited knowledge answers and local restart continuity; shared
      history claims are made only when Blob/Azurite gates actually exercise that backend.
- [ ] Lab 4 produces pending, revised and approved packets and demonstrates
      file-backed local restart recovery without claiming replica continuity.
- [ ] Lab 5 writes evaluation and gate evidence; a new trace ID is visible in
      the correct telemetry resource.
- [ ] Optional preview exercises are available in the selected region or clearly skipped.
- [ ] Synthetic source data is unchanged and generated artifacts remain uncommitted.

## 8. Reproducible workshop date

Set the workshop date in Lab 1's editable inputs. The default `2026-10-06` is nine
days before Medicare AEP opens; the notebooks propagate it to local and hosted
agents so enrollment-window answers are comparable across learners.

| Date | S1 Evelyn | S3 Rosa |
|---|---|---|
| `2026-10-06` | SEP possible; next AEP October 15–December 7 | SEP possible; next ACA OEP November 1 |
| `2026-10-20` | AEP | SEP possible |
| `2026-11-15` | AEP | ACA OEP |
| `2027-02-10` | MA OEP | SEP possible |
| `2027-09-01` | SEP possible | IEP for the November 20, 2027 birthday |

## 9. Clean up workshop resources

Use the setup notebook's cleanup guidance to review attendee-scoped resources
before approving deletion. Keep the exact attendee suffix and project scope
visible; never broaden deletion to the room without administrator approval.
The shared account, Search service, telemetry resource, storage and resource
group are administrator-owned. Review project/model ownership separately:
Lab 1 provisions them, while agent/knowledge cleanup must not be assumed to
delete them automatically.

## 10. Internal authoring and offline CI

Authors maintain adjacent Python cell sources and regenerate walkthroughs;
learners run the `.ipynb` files. Standalone helper self-tests, package preparation
checks and the root offline workflow are implementation validation, not extra
learner setup steps. The root dependency lock remains authoritative, with
matching minimal hosted-runtime pins. Offline results make no live Azure claim.
