# Shared workshop implementation

This is reusable product and internal helper code, not a second learner lab
sequence. Each learner folder under [`labs/lab1` through `labs/lab14`](../labs/README.md)
contains exactly one notebook, adjacent authoring source and lab-specific README.

| Shared implementation | Learner consumers |
|---|---|
| `foundry-project-models/` | Labs 1-2: provisioning, verification and persistence helpers |
| `hosted-agent-basics/` | Labs 3-4: the same locally tested/deployed concierge product |
| `hosted-knowledge-sessions/` | Labs 5-6, 9 and 12: knowledge-enabled concierge and durable history |
| `hosted-multi-agent-handoff/` | Labs 7-8: specialists, workflow and advisor recovery |
| `operate-hosted-agents/` | Labs 9-10: evaluation, release gates and optional administrator pipeline |
| `prompt-agents-and-workflows/` | Labs 11-12: prompt/workflow definitions and hosted integration |
| `invocations-toolbox-skills/` | Labs 13-14: separate batch/Responses products and governed skill collection |

The original combined drivers remain callable implementation helpers. Importing
them must not replay notebook actions. Learners execute only their numbered
notebooks and edit the original product files named by the lab guide.

`prepare.py` vendors `common/`, synthetic `data/` and selected Skills into five
flat hosted packages. Those generated copies, credentials, deployment state and
caches are ignored and never hand-edited or committed. Hosted requirements are
minimal subsets of the root dependency lock.

Runtime evidence stays in `labs/artifacts/` under its stable internal topic
namespaces, not here. Notebook handoffs validate current scope and fingerprints
before reusing resources, packets, prompt references or measured evaluations.
The opt-in cloud workflow is under `operate-hosted-agents/.github/workflows/`;
it remains administrator-owned and is not installed automatically.
