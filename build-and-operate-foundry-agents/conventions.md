# Workshop lab conventions

These are the authoring and review rules for Build and Operate Foundry Agents.
Read them before changing a lab, shared product, checkpoint, or workshop guide.
The workshop is hosted-agent-first; Prompt Agents receive only a short optional
comparison. Microsoft Agent Framework (MAF) does not require Prompt Agents.

**Status:** the hosted-first source, notebook, checkpoint, and documentation
migration is implemented on `copilot/hosted-first-lab-conventions`.
[migration-plan.md](migration-plan.md) retains the learner critique and migration
sequence. Use [3-day-labs/README.md](3-day-labs/README.md) for executable prerequisites.
Live Azure acceptance and learner timing still require approved rehearsal;
implementation and offline validation do not establish those outcomes.

## Track ownership and synchronization

`3-day-labs/` is the canonical fourteen-lab curriculum, relocated from `labs/`
without teaching or gate changes; only relocation references change. The generated
`1-day-labs/` publishes original-number Labs 1, 4 and condensed capstone 7. Its Lab 4
folds real Lab 3 local exercises and acceptance into the deployment lesson; it
must not fabricate Lab 3 evidence or assume a completed starter solution.
Short Lab 1 combines canonical project setup with the chat-only cells owned by
`tools/one_day_setup_finish.py`. No standalone Lab 2, embedding deployment,
embedding inference or retrieval service is part of the short route.
Generated `one_day_parts.py` retains the canonical checkpoint implementation
but removes embeddings from short scope and maps both setup phases to Lab 1.
Never weaken three-day `common/notebook_parts.py` or its RAG gates for this purpose.
Short Lab 7 reuses the canonical MAF helper, fan-out demo and classifier exercise
with a Lab 4 prerequisite; its isolated product uses synthetic local knowledge
instead of Lab 6/Search. `tools/one_day_team_finish.py` owns the short-only
explicit local approval, deployment and fixed-version hosted review cells.
It publishes a terminal `one-day-team` checkpoint, not a claim of three-day
Lab 8 restart/recovery acceptance. Do not auto-send advisor decisions.

Authors edit canonical adjacent cell sources and regenerate their notebooks,
then run `python build-and-operate-foundry-agents/tools/sync_one_day_labs.py`
from the repository root. Short-only adaptations belong to that tool, `tools/one_day_setup_finish.py`
and `tools/one_day_team_finish.py`.
`--check` must pass in offline CI; it compares deterministic guides, source,
notebooks, helper/product copies and provenance without writing.
Default sync rejects modified generated files, including learner product edits.
Archive edits before explicitly using `--overwrite`; never sync during delivery.

Short-track exercises edit `1-day-labs/products/`, generated from shared source;
checkpoints live in `1-day-labs/artifacts/`. They never modify canonical artifacts
or shared starter products. Both tracks share root `.env`, Azure model quota and
port 8088: use a distinct attendee suffix for a separate run, fresh kernels,
and no simultaneous track execution. Local source changes require local
acceptance before deployment; source/version/evidence checks remain intact.

The sync excludes credentials, caches, executed notebooks, runtime evidence and
prepared common/data copies. Fail closed when upstream composition anchors
change; update the adapter and regression coverage rather than silently dropping
gates. Rehearse timings and live Azure acceptance separately from offline checks.

## 1. Learning progression

Each lab adds one primary capability to a solution the learner understands.
Teach foundational concepts before using them, move from local observation to
deployed evidence, and introduce orchestration before recovery or delegation.
Do not repeat the same graph merely with a different agent provider.

Keep two kinds of ordering explicit:

- **Required prerequisites:** prior learning and accepted artifacts needed to
  execute and understand the lab. A prior concept may be required even when
  no runtime artifact is consumed.
- **Recommended route:** the facilitator's simple-to-complex teaching sequence,
  including labs that are not technical dependencies.

Document both in the lab introduction and guide. Independent branches are
choices, not instructions to run several notebooks simultaneously. State shared
port, source, deployment, quota, and evaluation-version conflicts.

The default guided route is core Labs 1-10 in order, then selected extensions.
Optional means removable without breaking core completion. The Prompt Agent
comparison must have no downstream consumers. MAF is taught in the hosted
specialist workflow, not introduced as a Prompt Agent capability.

## 2. One learner entry point and clear ownership

Each `3-day-labs/labNN/` owns exactly one `labNN_walkthrough.ipynb`, one adjacent
`labNN_<topic>.py` authoring source, and one `README.md`. Use two-digit paths;
display Lab 1, Lab 2, and so on. Keep learner numbers separate from internal
artifact namespaces.

Learners run the notebook in the repository Python 3.14 dev container, using
`/usr/local/bin/python`. The source is an authoring input, not an alternate
terminal driver. Use Python for lab logic and explicit notebook calls for
deployment tooling; Bash is the learner shell. PowerShell remains limited to
shared administrator permission setup.

Ownership boundaries:

| Location | Owns |
|---|---|
| `3-day-labs/labNN/` | Explanation, editable inputs, exercises, acceptance gates, and checkpoint publication |
| `shared/<topic>/` | Original deployable products and reusable implementation helpers |
| `common/` | Shared configuration, synthetic-data access, policy, storage, naming, and checkpoint behavior |
| `data/` | Synthetic fixtures, source knowledge, and evaluation scenarios |
| `3-day-labs/artifacts/` | Ignored runtime evidence and scoped handoffs, not source |
| `infra/` and administrator setup | Shared Azure prerequisites and approved infrastructure, not hidden notebook side effects |

Helpers may implement lifecycle mechanics, but must not conceal the engineering
decision being taught. Show the actual product function, tool registration, graph,
storage choice, or deployment reference before asking a learner to change it.
Importing a helper must not provision, publish, deploy, evaluate, or replay a lab.

## 3. Individual lab contract

The README and notebook must agree on this structure:

1. **Goal and delta:** one primary outcome, what already exists, what this lab
   adds, and what is deliberately out of scope.
2. **Prerequisites:** required labs and artifacts, prior concepts, administrator
   dependencies, identity/network access, and recommended route.
3. **Restore and inspect:** start in a fresh kernel, validate predecessor scope
   and evidence, show the current product and configuration without cloud replay.
4. **Teach and demonstrate:** explain the decision and expected behavior before
   execution; distinguish local mechanics from Azure-hosted behavior.
5. **YOUR TURN:** edit original product code or a bounded notebook input, predict
   the change, run it, and interpret the evidence.
6. **Acceptance:** demonstrate the intended change and a meaningful failure or
   boundary case. A file's existence or a printed PASS is not sufficient.
7. **Publish and hand off:** save accepted evidence, identify its consumers, and
   link the next required/recommended lab or optional branch.
8. **Recovery and cleanup:** identify the producing lab/cell to rerun, notebook-owned
   processes to stop, and attendee-owned resources subject to reviewed cleanup.

Put editable inputs before their first use. Precede each code cell with a
one-sentence explanation; label steps `Step N.k`. Preserve exercise gates.
For cloud-changing or charged actions, explain the target, consequence, expected
evidence, and approval/input before the explicit action cell.

Do not hide a complete solution behind an exercise helper. Keep the starting
state, edit location, expected effect, and acceptance conditions inspectable.
Time boxes must reflect rehearsal, not a blanket claim that every split lab
takes the same time. Optional exercises must not become checkpoint requirements
for the required route.

## 4. Continuity between labs

A later lab restores state, not the earlier notebook's execution. Fresh-kernel
startup must not rerun provisioning, deployment, model judges, or prior exercises.
Missing prerequisites fail with the producing learner lab and recovery action.
Never fabricate checkpoints or accept another attendee's evidence.

Use the existing scope-bound checkpoint helpers. Record the approved
project/model scope and attendee suffix, relevant source/evidence fingerprints,
and actual accepted state. For deployed dependencies, preserve the agent name,
version, endpoint reference, and demonstrated capability. Keep credentials out
of checkpoints, logs, committed notebooks, and deployment packages.

Every consumer validates the predecessor evidence it actually relies on.
Changes to scope, relevant source, configuration, or measured versions invalidate
dependent acceptance. Do not invalidate unrelated branches merely because a
different product changed. Republish only after the affected gates pass.

Preserve the current internal namespaces (`lab1` through `lab5`, `stretch6`,
`stretch7`) unless the dependency or evidence meaning changes. They do not map
one-to-one to learner numbers. A genuinely new independent capability needs an
explicit contract; do not reinterpret an old prompt-backed checkpoint as proof
of hosted-to-hosted delegation. Any incompatible handoff must fail with a clear
rerun instruction rather than silently upgrading evidence.

Document product lineage at every boundary:

- **Continue:** reuse the same product and retain earlier learner changes.
- **Extend:** carry accepted behavior into the next product and test it along
  with the new capability; explain any deliberate replacement.
- **Branch:** name the new service/product, reused inputs, separate state, and
  behavior it does not inherit.

Do not silently drop a prior tool, policy edit, or exercise result when moving
between shared products. Do not copy whole products just to manufacture continuity.
Reuse shared implementations and transfer only the behavior needed by the lab.
The concierge, triage service, batch Invocations service, and Skills example
are not automatically one deployable product.

## 5. Runtime, identity, and state

Use `DefaultAzureCredential`, async Azure I/O where applicable, and context
managers or explicit closure. Consult current official documentation and verify
installed SDK versions before implementing Azure/Foundry calls. Use root lock
pins; hosted requirements are minimal matching subsets.

Notebook = learner cockpit; hosted Python = deployed product. Test the same
product locally and remotely, but label the evidence separately. Notebook
lifecycle helpers own specific process IDs, readiness, logs, timeouts, and
cleanup. Never terminate unrelated processes or silently reuse a server on a
busy port.

Separate message history, session/case mapping, workflow pending state, and
release evidence. State exactly which backend supports each. File-backed local
restart recovery does not establish replica, version-roll, or cross-service
continuity. Azurite is local only. Shared history does not by itself make pending
workflow state durable.

Keep attendee-scoped resource names and distinct identities explicit. Document
caller and callee access for service delegation; model access does not establish
permission to invoke another agent. Administrator access changes are reviewed
prerequisites, not implicit notebook setup.

Delegation must expose failures, bound waits, retain case/session correlation,
and make retry behavior deliberate. Do not blindly replay a state-changing
request. A concierge may relay a pending status, but must not manufacture an
advisor decision. Production authorization and distributed recovery remain
explicit limitations unless implemented and demonstrated.

## 6. Evidence and release boundaries

Each checkpoint binds evidence to the capability claimed:

| Claim | Required observation |
|---|---|
| Local behavior | Current product, controlled invocation, expected result, and relevant negative case |
| Deployed readiness | Specific deployed version and an actual successful invocation |
| Retrieval | Grounded response and source citation; describe freshness limits |
| Recovery | Same case/session before and after restart, with backend provenance |
| Human approval | Pending state followed by the explicit decision and resulting transition |
| Telemetry | New trace/correlation ID found in the intended Azure resource |
| Evaluation | Target version, question set, configuration, responses, scores, and limitations |
| Release gate | Exact evaluated bundle and fail-closed result, not rerun judges |
| Skills/Toolbox | Observed Skill/tool use; configuration alone is not invocation |

Pin the evaluated candidate. Later modifications or deployment promotion must
not mutate the evidence under review. Extensions use separate candidate versions
or environments, with reviewed resource names, rather than overwriting the core
release target. A changed product needs new evaluation before a release claim.

Every agent carries the shared healthcare compliance boundaries. Human approval
in an exercise is simulated, not proof of production authorization. Schema
validity, citations, judge scores, and sample gates are not regulatory
certifications or measured cost-per-success results. Label skipped live/preview
checks; do not replace them with success-shaped defaults.

## 7. Authoring, documentation, and validation

Edit adjacent cell sources and regenerate `.ipynb` with `tools/py_to_ipynb.py`.
Never hand-edit generated notebooks independently. Commit no executed outputs,
local `.env`, `.azure`, caches, vendored package output, or runtime artifacts.
Edit original product/Skill sources, not prepared copies.

Keep the implementation dependency map in `tools/validate_workshop.py`
authoritative for required lab IDs. Update its checks and regression tests with each changed contract;
do not introduce a second competing runtime dependency map.

Documentation responsibilities:

- Workshop/root READMEs: scope, audience, entry points, agenda, and hosted focus.
- `3-day-labs/README.md`: full dependency graph, recommended route, titles, and handoffs.
- Per-lab README and notebook: matching local prerequisites, teaching, evidence,
  limitations, recovery, and onward navigation.
- `shared/README.md` and artifact guide: product owners/consumers and contract meanings.
- `SETUP.md` and infrastructure guides: administrator prerequisites, permissions,
  network, telemetry, resource ownership, and cleanup.
- `USE-CASE.md`, data, and Skills: consistent scenarios and policy; do not change
  factual fixtures or policy solely to make the agenda sound consistent.
- Customer collateral, when present: update editable sources first and regenerate
  rendered deliverables; do not leave old curriculum claims in distributed copies.

Prefer linked authoritative explanations over duplicated setup instructions.
Audit workshop-related root docs, instructions, CI templates, notebook prose,
and generated collateral too. Preserve independent capability tracks elsewhere
in the repository.

Use existing offline tests for contract behavior, notebook/source parity,
fresh-kernel restoration, prerequisite failure, source invalidation, and bounded
failure handling. Run focused tests for each slice, then the full workshop
validator before integration. Offline CI never authenticates or deploys.

From the repository root in the author environment:

```bash
python build-and-operate-foundry-agents/tools/validate_workshop.py
```

Live acceptance is a separate, approved rehearsal on the learner notebook path.
Finish by running a cold start, an interrupted/resumed boundary, and the selected
branches without undeclared predecessor state. Documentation-only changes need
link/consistency review, not cloud execution.

## Change checklist

- The learner knows every concept used before the lab assumes it.
- Required dependencies and the recommended route are explicit and consistent.
- The previous accepted product/evidence survives, or a branch/reset is explained.
- Fresh-kernel restoration does not repeat cloud work.
- The exercise teaches the primary delta and its acceptance observes real behavior.
- Local, deployed, distributed, preview, and simulated claims are distinguished.
- Original sources, generated notebooks, tests, and affected docs agree.
- Relevant permissions, scope, costs, failure paths, and cleanup are visible.
- Repository index entries are refreshed after structural changes.
