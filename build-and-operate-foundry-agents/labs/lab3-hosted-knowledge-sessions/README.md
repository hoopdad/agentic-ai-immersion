# Lab 3: Hosted knowledge and durable sessions

| | |
|---|---|
| Goal | Add Foundry IQ knowledge and conversation history, prove local restart continuity, then deploy the updated concierge |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab2/hosted.json`; Lab 1 configuration and administrator-supplied Search access |
| Notebook | `lab3_walkthrough.ipynb` |
| Produces | `artifacts/lab3/knowledge.json`, `hosted.json`, `sessions/`, `transcripts.md`, `hosted_local.log` |

Open this notebook with `/usr/local/bin/python` in the repository dev container.
Run cells in order; use its editable inputs for optional Blob configuration.
The root `.env` persists setup values downstream, but manual copying or terminal
drivers are not learner prerequisites.

## Configuration and identity

The notebook reads the project/model configuration established by Lab 1 and
the administrator-supplied Search endpoint. Retrieval assumes the configured
3072-dimensional embedding deployment. It creates indexes, knowledge sources,
the knowledge base and its project connection using Entra credentials.

The learner needs Search creation/data-write access and project-connection
write permission. The hosted agent needs Search Index Data Reader. Deployment
requires Foundry Project Manager; invocation requires Agent Consumer or User.

Optional shared history uses an **existing** Blob account URL and separate
container name. The URL is not an identity or credential. Local
`DefaultAzureCredential` selects the developer; deployed access uses the
dedicated agent identity with Storage Blob Data Contributor. The lab does not
create cloud storage. Azurite is a local emulator option and is never deployed.

## Technical features and evidence

| Feature | Implementation | Acceptance meaning |
|---|---|---|
| Governed retrieval | `knowledge_base.py`: vector/semantic indexes, knowledge sources and Foundry IQ KB | Sources are indexed and reusable; review dates still need human maintenance |
| Identity connection | Project managed-identity connection and `MCPStreamableHTTPTool` with Entra bearer authentication | Local and deployed principals must each reach the correct endpoint |
| Product packaging | `hosted/prepare.py` vendors shared code/data; package review excludes credentials/caches | The tested product is the uploaded product |
| Conversation history | `common.message_store` with Blob/Azurite or files | History is keyed by stable conversation identity, not process memory |
| Local lifecycle | Notebook cell source `lab3_hosted_knowledge.py` starts/stops product subprocesses | Two turns, restart, third turn remembers `atorvastatin` |
| Replica distinction | Shared Blob gate versus file fallback | Files prove local continuity only; shared storage must be configured before scale-out claims |

Conversation history is not automatically reviewed organizational knowledge or
evidence that the agent learned a reusable improvement. A citation alone does
not prove correctness or source freshness.

## Teach and demo

1. Inspect bounded-context documents and the two indexes/sources, KB and project
   connection created by the knowledge cells.
2. Run the local conversation/restart cells. Read the `history:` log and show
   the two different process IDs with the same conversation ID.
3. Inspect a cited knowledge answer and compare its statement with the source rule.
4. Explain where history lives and why container-local files are not a deployed
   durability guarantee.
5. Run explicit deployment cells and record the actual active version.

## Do and learner acceptance gates

Run every **YOUR TURN** cell and its executable gate; the notebook cleans up
child processes even when a gate fails.

- **Shared-history continuity:** use the configured Blob/Azurite backend across
  two local replicas. Confirm both actually use the same history service.
  Without either backend configured, the gate reports SKIPPED, not proof of scale-out.
- **Broken store:** intentionally restart with an empty store and explain the
  loss of remembered facts rather than treating it as a model failure.
- **Knowledge unavailable:** inspect honest behavior without retrieval and
  require governed citations when the live Foundry IQ endpoint is available.
- **Deploy:** review target settings, prepare and validate the package, deploy
  through the notebook, wait for `active`, enter the actual `DEPLOYED_VERSION`
  and run **Verify the deployed knowledge agent**.

The notebook warns when deployment is file-backed. Do not claim replica or
version-roll continuity in that configuration. Message history expires
logically after the configured idle period (seven days by default); an
administrator-managed Storage lifecycle rule can physically remove inactive
history blobs under the container's `sessions/` prefix.

## Checkpoint

Share the continuity PASS, two process IDs, one grounded answer with a `[KB-...]`
citation and the `deployed` block of `artifacts/lab3/hosted.json`. State the
backend exercised and the rule supporting the answer. Lab 4 consumes this
checkpoint; Lab 5 evaluates this concierge.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Missing project ARM ID or endpoint | Rerun Lab 1's configuration persistence and restart this kernel |
| Missing Lab 2 checkpoint | Reopen Lab 2 and rerun its producing cells |
| Missing `common` or stale package | Rerun notebook package preparation after source edits |
| Restart forgets facts | Inspect conversation ID, backend settings, startup errors and `artifacts/lab3/hosted_local.log` |
| Second replica forgets the first turn | Confirm the same Blob container/Azurite service, permissions and network path |
| Embedding 429 | Allow header-aware retries; inspect current quota with the administrator if throttling persists |
| Knowledge 401/403 | Verify the calling identity's Search permissions and propagation |
| Missing citation | Inspect `knowledge.json`, the MCP endpoint, project connection and retrieval logs |
| `424 session_not_ready` | Read version logs, repair startup and redeploy through the notebook |
