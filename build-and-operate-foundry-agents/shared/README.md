# Shared workshop implementation

This is reusable product and internal helper code, not a second learner lab
sequence. Each learner folder under [`3-day-labs/lab01` through `3-day-labs/lab14`](../3-day-labs/README.md)
contains exactly one notebook, adjacent authoring source and lab-specific README.

| Shared implementation | Learner consumers |
|---|---|
| `foundry-project-models/` | Labs 1-2: provisioning, verification and persistence helpers |
| `hosted-agent-basics/` | Labs 3-4: the same locally tested/deployed concierge product |
| `hosted-knowledge-sessions/` | Labs 5-6 and 9-10: knowledge-enabled core concierge and declared history backend; accepted baseline reused by Lab 12 |
| `hosted-multi-agent-handoff/` | Labs 7-8: specialists, workflow and advisor recovery |
| `operate-hosted-agents/` | Labs 9-10: evaluation, release gates and optional administrator pipeline |
| `prompt-agents-and-workflows/` | Lab 11 only: short terminal comparison with one versioned prompt and invocation; legacy folder name, no workflow consumers |
| `hosted-delegation/` | Lab 12: isolated concierge extension candidate invoking Lab 8's pinned hosted triage service; requires both Labs 8 and 9 |
| `invocations-toolbox-skills/` | Labs 13-14: separate batch/Responses products and governed skill collection |

The original combined drivers remain callable implementation helpers. Importing
them must not replay notebook actions. Learners execute only their numbered
notebooks and edit the original product files named by the lab guide.

`prepare.py` vendors `common/`, synthetic `data/` and selected Skills into
flat hosted packages. Those generated copies, credentials, deployment state and
caches are ignored and never hand-edited or committed. Hosted requirements are
minimal subsets of the root dependency lock.

## Product lineage and boundaries

Labs 3-4 continue the same typed-tool concierge. Labs 5-6 extend accepted
tool/policy behavior with retrieval and history; moving folders does not
automatically preserve learner edits, so use the notebook's explicit carry-forward
and acceptance gates. Lab 5 carries the accepted Lab 3 `get_sponsor` function
and rule 3 enrollment policy into ignored `hosted/common/accepted_concierge.py`;
it does not copy every arbitrary concierge edit. `artifacts/lab3/accepted_behavior.json`
binds that transfer to accepted source, and Lab 6 records retained behavior and
the hosted source hash. Edit the original product, not the prepared transfer.
Labs 7-8 branch into the hosted triage service, with the
workshop's only full specialist MAF graph and explicit advisor decisions.
Its file-backed pending-state recovery proves only a local restart.
Lab 8 publishes a scoped triage name/version/project/protocol reference and
separate deployed invocation evidence without replacing the original local packets.

Labs 9-10 measure and gate the pinned Lab 6 concierge, independently of triage.
Lab 9 defaults to local evaluation and binds its target, configuration/source
hashes and measured bundle; a deployed reference is not itself an Azure
evaluation or ingestion observation. Lab 10 checks those exact results and
rejects candidate edits; its default promotion/rollback is a rehearsal.
Lab 12's `hosted-delegation/` extends the accepted concierge behavior in a
separate candidate; it calls the existing triage service rather than copying a
graph or packaging prompt references. Preserve the core evaluated version and
release bundle. A modified extension needs new evaluation before release.
Its hosted package is `hosted-delegation/hosted/`; `prepare.py` vendors the
accepted core implementation as generated `core_product.py` alongside the
delegation helper without modifying Lab 6's original product. Edit original
sources, not these prepared copies. The candidate uses the distinct
`healthcare-concierge-delegation-{suffix}` name; source fingerprints include the
core, candidate and shared dependencies. Callee acceptance checks its fixed
100% version selector before and after the call and compares the returned
runtime version; a name alone is not immutable version evidence.
The delegation tool accepts no model arguments: the application binds the
explicit case/session/participant envelope, rather than allowing model-generated
identifiers. The remote client sets `max_retries=0` to avoid automatic replay.
Trace context travels in the supported Responses input envelope and outbound
headers; triage extracts envelope context, not assumed HTTP middleware access.
Delegation exposes bounded failures and case/session correlation; a pending
reply is not an automatic advisor decision or distributed approval resume.

Lab 13's batch Invocations service and Lab 14's Responses Skills service are
distinct products under `invocations-toolbox-skills/`. Lab 14 retains batch
acceptance evidence, not batch session state. Toolbox is an optional preview.
Lab 11 has no downstream consumers or hosted product dependencies.

Run runtime notebooks sequentially within a workspace: products share local
port 8088, editable source and Azure quota. Stop only notebook-owned processes.

Runtime evidence stays in `3-day-labs/artifacts/` under its stable internal topic
namespaces, not here. Notebook handoffs validate current scope and fingerprints
before reusing resources, packets or measured evaluations. Lab 11 keeps terminal
`stretch6/part_a.json`; Lab 12 uses independent
`hosted_delegation/part_a.json`, never legacy prompt-backed `stretch6/part_b.json`.
The opt-in cloud workflow is under `operate-hosted-agents/.github/workflows/`;
it remains administrator-owned and is not installed automatically.
