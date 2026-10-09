# Setup: Build and Operate Foundry Agents

## 1. Open the repository dev container

Use the repository-level Python 3.14 dev container, not a separate workshop
environment. Locally, Docker Desktop (Linux containers) and the VS Code Dev
Containers extension are required. GitHub Codespaces is supported when your
organization's policy and Azure network allow it.

1. Open the repository root and select **Dev Containers: Reopen in Container**.
2. Wait for bootstrap to finish installing the root dependency lock and toolchain.
3. Open [Lab 1](3-day-labs/lab01/lab01_walkthrough.ipynb) beneath this workshop.
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

After Lab 1 creates the learner project, the administrator must confirm that
**that new project** is enabled for hosted agents and its identity has the required
resource access before Labs 3-4. Creating a project does not copy another project's
RBAC, connections or Standard Agent capability host; private Standard Agent
environments require the project-scoped configuration described in
[`infra/README.md`](infra/README.md). Lab 2's model smoke tests do not verify it.
The approved account must be `AIServices` with project management enabled;
model deployments are account-level resources used through the learner project.

Shared permission administration remains valid: an authorized administrator
uses `scripts/setup-permissions.ps1` and its documented parameters in the
[repository setup guide](../README.md). This is permission setup, not an
alternative way to execute a lab. Never change roles or networking without approval.

For a private workshop environment, administrators can follow
[`infra/README.md`](infra/README.md). Learner kernels must already be able to
reach its private endpoints. Do not enable public access to bypass a blocked path.

| Shared prerequisite | Needed by | Owner |
|---|---|---|
| Existing Foundry account, approved model quota and creation permissions | Labs 1-2 | Account administrator |
| Azure AI Search with managed identity, semantic ranker and Foundry IQ support | Labs 5-6 and later knowledge consumers | Search administrator |
| Existing Blob account/container, if shared history is requested | Optional Labs 5-6 shared history | Storage administrator |
| Application Insights connected to the learner project, with approved ingestion access for the measured core and caller/callee | Labs 9-10 and optional Lab 12 | Telemetry administrator |
| OIDC and protected GitHub Environments | Optional Labs 9-10 cloud pipeline | Release administrator |
| Foundry Toolbox endpoint and access | Optional Lab 14 preview | Project administrator |
| Project access for publishing/invoking one prompt version | Optional Lab 11 terminal comparison | Project administrator |
| Hosted triage invocation access for the extension caller identity, approved callee endpoint/network path and telemetry access | Optional Lab 12 after both Labs 8 and 9 | Project and telemetry administrators |

Lab 12 reuses Lab 8's deployed triage service and Lab 9's tracing concepts,
extending accepted concierge behavior in a separate `shared/hosted-delegation/`
candidate. It consumes no Lab 11 prompt references and builds no second graph.
Review caller/callee identities, supported invocation endpoint/token audience,
network reachability, telemetry permissions and the pinned target before the
explicit deployment/invocation cells. Model access alone does not grant agent
invocation access. Keep the evaluated Lab 9-10 core version untouched.
No additional model or prompt-backed workflow service is a prerequisite.

Lab 11 requires Lab 4 and ends after one prompt comparison. Lab 13 also requires
Lab 4's hosted Responses concepts; Lab 14 requires Lab 13 but starts a distinct
Responses Skills service, not a stateful batch service.

## 3. Notebook inputs and downstream persistence

Enter approved account context in Lab 1 and model/downstream configuration in
Lab 2's editable input cell; later walkthroughs provide
their own relevant exercise inputs. Lab 2 resolves and writes downstream
configuration to the repository-root `.env`. That file remains the persistence
contract, not a manual prerequisite to copy or populate first. Do not commit
`.env`, tokens, local deployment state or executed notebook outputs.

| Configuration | Meaning |
|---|---|
| Tenant, subscription, resource group and existing Foundry account | Approved management scope and authentication context |
| Unique attendee suffix | Project/resource names derive from this value; retain the same suffix across labs |
| Chat deployment and embedding deployment choices | Names, supported model versions and capacity used by agents and retrieval |
| `FOUNDRY_PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID`, `AZURE_OPENAI_ENDPOINT` | Resolved endpoints and project ARM identity persisted for downstream notebooks |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `EMBEDDING_MODEL_DEPLOYMENT_NAME` | Provisioned deployment names; retrieval assumes `text-embedding-3-large` with 3072 dimensions |
| `AZURE_AI_SEARCH_ENDPOINT` | Administrator-supplied Lab 2 input used by Lab 5; not inferred by account discovery |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional administrator-supplied Lab 2 input used by Lab 9, or resolved from the project connection |
| `MARKETPLACE_RESOURCE_SUFFIX` | Attendee resource isolation persisted by Labs 1-2 |
| `MARKETPLACE_TODAY` | Scenario date, defaulting to `2026-10-06`; change in notebook configuration only when an exercise needs a different date |
| Optional Blob account URL and container | Existing shared message-history service for Labs 5-6, using Entra credentials |

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

Search, optional Blob and telemetry settings are editable Lab 2 inputs supplied
by the facilitator, not resources provisioned or reliably discovered by Labs 1-2.
Blank optional inputs preserve existing values; rerun the setup inputs and
publication cells after the facilitator supplies a missing value.
Knowledge MCP endpoints and agent/version references are produced by the
notebooks and passed through checkpoint artifacts. They are not values learners
must invent. Optional Toolbox configuration belongs in Lab 14's editable inputs.
Do not deploy Azurite's local emulator settings to Foundry.

## 4. Project and model setup: Labs 1-2

This section describes the full three-day route. The generated one-day route
combines these foundations in **Lab 1**, deploys and verifies **chat only**,
then proceeds to Labs 4 and 7. Do not run the three-day embedding setup for
that route; follow `1-day-labs/lab01/lab01_walkthrough.ipynb` instead.

Lab 1 authenticates and creates or resolves the project. Lab 2 reuses that
project, provisions chat and embedding deployments, verifies readiness and
persists their settings. Lab 2's `artifacts/lab1/project.json` checkpoint records project/model references
and successful chat/3072-dimensional embedding smoke checks.
Review the selected model/version, deployment names and capacity before the
provisioning cell. Account permissions and quota do not become available merely
because a notebook input is filled in.

| Deployment | Purpose | Teaching constraint |
|---|---|---|
| Configured chat deployment, such as `gpt-5.4-mini` | Agent reasoning and evaluation judges | A room shares quota; plan capacity with the administrator rather than assuming a fixed allocation works everywhere |
| `text-embedding-3-large` | Labs 5-6 retrieval indexes | 3072 dimensions; changing the model requires matching the index schema |

Model throttling retries honor Azure retry headers. If repeated 429s persist,
inspect runtime limit headers and the deployment allocation with the administrator.
A quota change can take time to propagate.

## 5. Identity and RBAC

Local notebooks reuse Azure CLI sign-in, and hosted model clients use
`DefaultAzureCredential`; deployed containers use their dedicated agent identity. Management-plane provisioning,
data-plane inference, Search retrieval and telemetry publishing are separate
permissions. Allow propagation before retesting.

| Principal | Scope | Required access |
|---|---|---|
| Learner creating the project/models | Existing Foundry account and approved management scope | Administrator-approved project/model creation rights |
| Learner developing agents | Foundry project | Azure AI User or Azure AI Developer, as appropriate |
| Learner creating the Labs 5-6 project connection | Foundry account/project | Connection-write permission, such as Azure AI Owner or Contributor at the appropriate scope |
| Hosted deployer | Foundry project | Foundry Project Manager |
| Hosted invoker | Foundry project | Foundry Agent Consumer or Foundry User |
| Lab 12 extension caller identity | Pinned triage agent's approved project scope | Administrator-verified hosted invocation access; not inferred from Azure AI User/model permission |
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

### Lab 9 tracing prerequisites

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

Open each numbered walkthrough in its matching two-digit `3-day-labs/labNN` folder, read that
folder's README and run prerequisite cells
first. Follow the [Labs 1-14 dependency table](3-day-labs/README.md#sequence-and-artifact-chain);
each notebook starts in a fresh kernel and restores validated predecessor
metadata rather than rerunning provisioning or evaluation work.
The guided route is core Labs 1-10 in order, then chosen extensions. A dependency
branch does not mean parallel runtime in one workspace: local hosts share port
8088, editable source, deployment targets and Azure quota. Stop the current
notebook-owned host before starting another, and do not reuse an unrelated
process on a busy port. Protect the exact evaluated core version when branching.
The notebook manages local servers on port 8088, readiness probes, package
preparation and process cleanup. Foundry separately builds and runs the uploaded
Python product package. Deployment is an explicit notebook action; review its
target before running it and wait for an `active` version before invocation.

If an earlier artifact is missing, return to its producing notebook and rerun
the checkpoint cells. If a server or kernel fails, inspect the saved local log,
stop only the identified process through the notebook's lifecycle controls,
then rerun the preparation and readiness cells. Restart kernels after changing
persisted configuration so a stale environment does not mask the change.
Lab 12 uses `artifacts/hosted_delegation/part_a.json`; old prompt-backed
`stretch6/part_b.json` cannot satisfy its acceptance. Restore accepted Labs 8
and 9 and rerun the new Lab 12 rather than replaying Lab 11.

## 7. Facilitator readiness rehearsal

Rehearse the notebooks on the exact room account and network; offline CI does
not prove any of these live outcomes.

- [ ] Dev-container bootstrap and Python 3.14 kernel selection succeed.
- [ ] Lab 1 authenticates and creates/resolves the project; Lab 2 provisions both models,
      verifies access and writes downstream configuration.
- [ ] Roles and approved network paths are effective for learner, project,
      Search and hosted agent identities.
- [ ] Lab 3 passes local safety checks; Lab 4 deploys a version and invokes it when active.
- [ ] Labs 5-6 produce cited knowledge answers and local restart continuity; shared
      history claims are made only when Blob/Azurite gates actually exercise that backend.
- [ ] Labs 7-8 produce pending, revised and approved packets and demonstrate
      file-backed local restart recovery without claiming replica continuity.
- [ ] Labs 9-10 write evaluation and gate evidence; a new trace ID is visible in
      the correct telemetry resource.
- [ ] Lab 11 runs after Lab 4 as a short terminal comparison; no other lab needs its prompt.
- [ ] Lab 12 blocks when either Lab 8 or 9 is missing; its isolated candidate
      retains accepted concierge behavior and does not overwrite the measured core.
- [ ] Lab 12 demonstrates a controlled failure, bounded remote pending-case call
      and current caller/callee Azure trace correlation, with no automatic advisor
      decision or blind state-changing replay.
- [ ] Labs 13-14 work after Lab 4 without knowledge, MAF, operations or prompt
      artifacts; the batch and Responses Skills services remain distinct.
- [ ] Optional preview exercises are available in the selected region or clearly skipped.
- [ ] Synthetic source data is unchanged and generated artifacts remain uncommitted.

## 8. Reproducible workshop date

The default workshop date `2026-10-06` is nine
days before Medicare AEP opens; the notebooks propagate it to local and hosted
agents so enrollment-window answers are comparable across learners. Use editable
notebook configuration when an exercise calls for another date.

| Date | S1 Evelyn | S3 Rosa |
|---|---|---|
| `2026-10-06` | SEP possible; next AEP October 15–December 7 | SEP possible; next ACA OEP November 1 |
| `2026-10-20` | AEP | SEP possible |
| `2026-11-15` | AEP | ACA OEP |
| `2027-02-10` | MA OEP | SEP possible |
| `2027-09-01` | SEP possible | IEP for the November 20, 2027 birthday |

## 9. Clean up workshop resources

Review attendee-scoped resources with the facilitator before approving any
notebook deletion action. Keep the exact attendee suffix and project scope
visible; never broaden deletion to the room without administrator approval.
The shared account, Search service, telemetry resource, storage and resource
group are administrator-owned. Review project/model ownership separately:
Labs 1-2 provision them, while agent/knowledge cleanup must not be assumed to
delete them automatically.

## 10. Internal authoring and offline CI

Authors maintain adjacent Python cell sources and regenerate walkthroughs;
learners run the `.ipynb` files. Standalone helper self-tests, package preparation
checks and the root offline workflow are implementation validation, not extra
learner setup steps. The root dependency lock remains authoritative, with
matching minimal hosted-runtime pins. Offline results make no live Azure claim.

Original topic drivers and the hosted-delegation extension remain internal helpers under `shared/`,
alongside reusable product code. Authors edit the
fourteen adjacent numbered cell sources below and regenerate their paired notebooks;
do not convert the original drivers into learner notebooks.

| Directory under `3-day-labs/` | Adjacent source → notebook |
|---|---|
| `lab01` | `lab01_identity_project.py` → `lab01_walkthrough.ipynb` |
| `lab02` | `lab02_models_verify.py` → `lab02_walkthrough.ipynb` |
| `lab03` | `lab03_tools_local.py` → `lab03_walkthrough.ipynb` |
| `lab04` | `lab04_deploy_invoke.py` → `lab04_walkthrough.ipynb` |
| `lab05` | `lab05_knowledge_retrieval.py` → `lab05_walkthrough.ipynb` |
| `lab06` | `lab06_sessions_resiliency.py` → `lab06_walkthrough.ipynb` |
| `lab07` | `lab07_specialist_orchestration.py` → `lab07_walkthrough.ipynb` |
| `lab08` | `lab08_advisor_recovery.py` → `lab08_walkthrough.ipynb` |
| `lab09` | `lab09_tracing_evaluation.py` → `lab09_walkthrough.ipynb` |
| `lab10` | `lab10_release_rollback.py` → `lab10_walkthrough.ipynb` |
| `lab11` | `lab11_prompt_agents.py` → `lab11_walkthrough.ipynb` |
| `lab12` | `lab12_workflows_delegation.py` → `lab12_walkthrough.ipynb` |
| `lab13` | `lab13_invocations.py` → `lab13_walkthrough.ipynb` |
| `lab14` | `lab14_skills_toolbox.py` → `lab14_walkthrough.ipynb` |

Each numbered folder has only that lab's source, notebook and README.
Folders and learner filenames use two-digit lab numbers for lexical sorting;
titles, steps and stable artifact namespaces retain their original numbers.
The [shared implementation guide](shared/README.md) identifies product ownership
and consumers without duplicating a second learner sequence.

For example, from the workshop directory, these internal author commands
regenerate Labs 1-2; use the same explicit source/output pairing above for
each other lab.

```bash
python tools/py_to_ipynb.py 3-day-labs/lab01/lab01_identity_project.py --name lab01_walkthrough
python tools/py_to_ipynb.py 3-day-labs/lab02/lab02_models_verify.py --name lab02_walkthrough
```
