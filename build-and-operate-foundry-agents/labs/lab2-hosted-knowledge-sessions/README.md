# Lab 2: Hosted knowledge and durable sessions

| | |
|---|---|
| Goal | Add a Foundry IQ knowledge base and durable conversation history to `healthcare-marketplace-concierge-hosted`, prove local process-restart continuity, then deploy and record version 2. |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab1/hosted.json`; configured Azure AI Search and Foundry project |
| Produces | `artifacts/lab2/knowledge.json`, `hosted.json`, `sessions/`, `transcripts.md`, `hosted_local.log` |
| Runs on | The notebook/driver runs on the workstation; `hosted/main.py` runs locally and in Microsoft Foundry |

## Required configuration

Use the dev container's Python 3.14 interpreter. In the repository-root `.env`, set:

- `FOUNDRY_PROJECT_ENDPOINT`
- `AZURE_AI_MODEL_DEPLOYMENT_NAME`
- `AZURE_AI_SEARCH_ENDPOINT`
- `AZURE_OPENAI_ENDPOINT` or a compatible `FOUNDRY_PROJECT_ENDPOINT`
- `EMBEDDING_MODEL_DEPLOYMENT_NAME` when it is not `text-embedding-3-large`
- `PROJECT_RESOURCE_ID` for the project connection and `--deploy`
- `MARKETPLACE_TODAY` for deterministic enrollment-window answers
- Optional `MARKETPLACE_BLOB_STORAGE_URL` and existing `MARKETPLACE_BLOB_STORAGE_CONTAINER` for Azure Blob history
- An Azure Blob URL before claiming deployed scale-out or version-roll continuity

The learner identity needs access to create Search indexes, knowledge sources, the knowledge base, and the
project connection. The deployed agent identity needs Azure AI Search data access. Deployment requires Foundry
Project Manager; invocation requires Foundry Agent Consumer or Foundry User.

## Workstation setup

From the workshop root:

```bash
# Reopen the repository in its dev container; dependencies are preinstalled.
python --version  # Python 3.14
# Dependencies were installed by the repository dev-container bootstrap.
```

In VS Code, select `/usr/local/bin/python` as the notebook kernel.

Start the notebook with its folder as the working directory:

```bash
cd ./labs/lab2-hosted-knowledge-sessions
python -m jupyter lab ./lab2_walkthrough.ipynb
```

Run the equivalent driver from `labs`:

```bash
cd ./labs
python ./lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py
```

## What the lab proves

1. `knowledge_base.py` creates two Search indexes, two knowledge sources, one Foundry IQ knowledge base, and a
   project managed-identity connection. Both ARM and MCP authentication use Entra bearer tokens.
2. `hosted/prepare.py` copies all imported `common/` and `data/` files beside `main.py`. `.agentignore` excludes
   credentials, local state, notebooks, caches, and deployment tooling without excluding the vendored app.
3. The local demo sends a stable Responses API `conversation` ID, kills the Python process after turn 2, restarts
   it, and asserts that turn 3 remembers `atorvastatin`.
4. Local files are a one-workstation teaching backend. They are not a deployed durability claim. Azure Blob
   Storage can keep message history available across multiple Foundry replicas and version rolls.
5. The deployment command generator requires `PROJECT_RESOURCE_ID`, prints an absolute quoted Bash block,
   checks the command exit status after every external command, and never deploys by itself.

## Run paths

```bash
# Build Azure knowledge resources, prepare the package, run the restart demo, print deployment commands
python ./lab2_hosted_knowledge.py

# Build only
python ./lab2_hosted_knowledge.py --build-only

# Reuse existing Lab 2 artifacts for the local restart demo
python ./lab2_hosted_knowledge.py --demo-only

# Print deployment Bash only
python ./lab2_hosted_knowledge.py --deploy

# After the Foundry version is active
python ./lab2_hosted_knowledge.py --record-version '2'
```

To run `hosted/main.py` manually, use two terminals:

```bash
# Terminal 1, from this lab folder
cd ./hosted
python ./prepare.py
python ./main.py
```

```bash
# Terminal 2, also from hosted
cd ./hosted
python ./test_local.py --session 'lab2-manual'
```

## Learner acceptance gates

The notebook preserves each **YOUR TURN** exercise and follows it with executable guarded code that always stops
child processes. The same gates are available from the driver:

```bash
# Uses the configured Azurite or Azure Blob shared-history backend
python ./lab2_hosted_knowledge.py --acceptance-gate scale-out

# Intentionally changes the restarted process to an empty message store
python ./lab2_hosted_knowledge.py --acceptance-gate broken-store

# Requires the live Foundry IQ MCP endpoint
python ./lab2_hosted_knowledge.py --acceptance-gate knowledge
```

Azure Blob Storage is opt-in and must already exist. For cloud use, set `MARKETPLACE_BLOB_STORAGE_URL` to the
storage account's Blob endpoint (for example, `https://<storage-account>.blob.core.windows.net`, without a
container path) and set the container separately in the root `.env`. This URL identifies the service endpoint;
it does not identify or authenticate an identity. `DefaultAzureCredential` uses the signed-in developer identity
locally. A deployed Foundry hosted agent uses its dedicated Microsoft Entra agent identity, not a user-assigned
managed identity. Grant that agent identity **Storage Blob Data Contributor** on the container or account.

For local Blob API testing, the dev container also runs Azurite. Set
`MARKETPLACE_AZURITE_CONNECTION_STRING` in the root `.env` to the local emulator connection string below.
The application creates the local emulator container if needed; it never creates a cloud account or container.

```text
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
```

The Azurite connection string is local-only and is never passed to Foundry. In Azure, the configured Blob URL uses Entra credentials from `DefaultAzureCredential`; provision the container
and role assignment separately.
History expires logically after `MARKETPLACE_SESSION_TTL_SECONDS` (7 days by default) and is deleted when an
expired session is accessed or listed. For physical cleanup of inactive blobs, configure a Storage lifecycle
rule for this container's `sessions/` prefix.

## Deploy and record the version

Run `python ./lab2_hosted_knowledge.py --deploy` from the lab folder. Review and paste the printed block into an
authenticated Bash terminal. The block changes to the absolute `hosted` path, prepares the package, configures
`azd`, initializes the Responses-protocol agent, sets non-placeholder environment values, and runs `azd up`.

If an Azure Blob URL is not configured, the generated block warns that deployed history is file-backed and
does not claim continuity across replicas or version rolls.
After the version is `active` in **Foundry > Agents > healthcare-marketplace-concierge-hosted > Versions**, record it:

```bash
python ../lab2_hosted_knowledge.py --record-version '<version>'
python ./test_local.py --deployed --session 'lab2-deployed-smoke'
```

`--record-version` updates `artifacts/lab2/hosted.json`; it does not query or change Azure.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `PROJECT_RESOURCE_ID is not set` | The project connection or deployment block needs the full ARM resource ID | Set it in the workshop-root `.env`; placeholders are not accepted |
| `FOUNDRY_PROJECT_ENDPOINT is not set` | The child process did not receive the workshop environment | Put `.env` at the workshop root and start through the driver, or set it in the terminal |
| `ModuleNotFoundError: common` | The hosted package was not prepared | Run `python ./prepare.py` from `hosted`; run it again after shared-code changes |
| Local restart assertion fails | The request used a different conversation ID, the message store changed, or startup failed | Read `artifacts/lab2/hosted_local.log` and the `history:` line |
| Second replica forgets the first turn | The replicas do not use the same Azure Blob container or Azurite instance | Check the `history:` log, storage RBAC/network access, and backend settings; restart and rerun the scale-out gate |
| `429 RateLimitReached` while creating embeddings | Other callers or this build exhausted the deployment's current RPM or TPM budget | Let the build honor Azure's `retry-after` header. It reports any request/token limit headers returned by the service and retries up to five times; use Foundry quota management if throttling persists |
| 401/403 from the knowledge MCP endpoint | The local or hosted identity lacks Search data access | Assign the documented Search role and wait for propagation |
| No `[KB-...]` citation | MCP URL missing, connection unavailable, or retrieval failed | Check `MARKETPLACE_KB_MCP_URL`, the project connection, and Search permissions |
| `424 session_not_ready` | The deployed container is still starting or failed | Open the active version Logs, fix the startup error, deploy a new version |

## Checkpoint

Share the continuity `PASS`, the two process IDs, one grounded answer with a `[KB-...]` citation, and the `deployed`
block from `artifacts/lab2/hosted.json`. Lab 3 consumes the Lab 2 artifact shape and agent name.
