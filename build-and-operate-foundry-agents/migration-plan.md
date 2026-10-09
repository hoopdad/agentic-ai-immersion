# Hosted-first lab migration plan

**Status: implementation integrated; live rehearsal outstanding.** This reviewed
plan follows [conventions.md](conventions.md) and records the design rationale
and migration sequence. The source/notebook, handoff, and documentation changes
are implemented on `copilot/hosted-first-lab-conventions`; actual prerequisites
are in [3-day-labs/README.md](3-day-labs/README.md). All fourteen learner numbers and notebook
paths are retained. Azure deployment/ingestion acceptance and observed learner
timing are not established by this code migration.

## Goal and initial proposal

Keep core Labs 1-10 focused on hosted agents. Reduce Lab 11 to a short optional
Prompt Agent comparison with no downstream consumers. Replace Lab 12's second,
prompt-backed MAF graph with authenticated hosted-to-hosted delegation. Keep
Labs 13-14 as optional hosted protocol/Skills extensions.

The initial proposal let Labs 11 and 13 start after Lab 2 and Lab 12 start after
Lab 8. That minimized artifact dependencies but did not fully account for what
a learner needs to understand one lab at a time.

## Learner critique

| Learner concern | Problem with the initial proposal | Revision |
|---|---|---|
| "I have not built a hosted agent. What am I comparing?" | Lab 11 after Lab 2 introduces a second hosting model before the first is understood. | Require Lab 4; compare one minimal Prompt Agent to the already deployed Responses product. Recommend the short comparison after the core. |
| "What does Invocations change?" | Lab 13 after Lab 2 assumes Responses, local host lifecycle, packaging, and deployment knowledge. | Require Lab 4; reuse its hosting concepts and explicitly introduce a separate stateless batch product. |
| "Why is the second workflow useful?" | The old Lab 12 repeats triage, specialists, compliance, and packet generation with another provider. | Reuse Lab 8's service; teach the network/identity boundary, not another graph. |
| "How do I diagnose a call across two services?" | Lab 12 proposes correlated tracing before Lab 9 teaches tracing. | Require both Labs 8 and 9; recommend finishing Lab 10 before modifying an extension candidate. |
| "Did my tool/policy edit disappear?" | Moving between shared products can silently reset prior exercise changes. | Audit and explicitly carry forward required behavior, or explain a branch. Add acceptance for retained behavior. |
| "The diagram branches, but should I jump around?" | A dependency tree alone does not provide a teachable sequence. | Recommend Labs 1-10 in order; distinguish executable dependencies from optional learning choices. |
| "Is this safe across replicas?" | Delegating to the triage service can make file-backed approval recovery look distributed. | Demonstrate one-shot pending-case delegation; retain the state limitation. Do not relay approval automatically or claim distributed resume. |
| "Did my release results change underneath me?" | Lab 12 modifies the concierge that Labs 9-10 measure. | Use a distinct extension candidate/version or environment; retain the exact core evaluation/release references. |

## Revised target curriculum

The guided route is Labs 1-10 in order, then selected optional Labs 11-14.
Lab numbers are stable identifiers, not instructions to skip prerequisites.
Lab 11 is a 10-15 minute comparison, not a second full agent-development track.
No remaining lab invokes its Prompt Agent, directly or indirectly.

| Lab | Target focus | Required predecessor labs | Main continuity contract |
|---|---|---|---|
| 1 | Identity and project | Administrator setup | Approved scope and attendee project |
| 2 | Models and verification | 1 | Verified model/project configuration |
| 3 | Typed tools and local Responses testing | 2 | Tested concierge source and local evidence |
| 4 | Deploy and invoke the hosted concierge | 3 | Same accepted product, pinned hosted version, invocation evidence |
| 5 | Hosted knowledge and retrieval | 4 | Extend concierge behavior with governed knowledge |
| 6 | Sessions and resiliency | 5 | Preserve knowledge/tools; prove the declared history backend |
| 7 | Hosted MAF specialist orchestration | 6 | Branch into triage product, parallel fan-out/fan-in, pending packets |
| 8 | Advisor approval and recovery | 7 | Resume original pending cases; deploy and verify triage service |
| 9 | Tracing and evaluation | 6 | Evaluate the pinned knowledge concierge; triage packets are optional |
| 10 | Release gates and rollback | 9 | Consume exact measured bundle; distinguish rehearsal from live promotion |
| 11 | Prompt versus hosted: short comparison | 4 | One optional prompt example; no downstream artifact consumers |
| 12 | Hosted-to-hosted delegation | 8, 9 | Concierge extension calls the pinned triage service; correlated traces |
| 13 | Structured batch Invocations | 4 | New stateless product; reuse verified config and hosting knowledge |
| 14 | Governed hosted Skills and optional Toolbox | 13 | Separate Responses Skills product; preserve completed batch evidence |

Labs 11 and 13 now explicitly validate the Lab 4 prerequisite rather than relying
on undocumented hosting knowledge. Lab 12 restores Lab 6 transitively through
Lab 8, plus Lab 9's telemetry evidence. Lab 10 is recommended release background,
not an input artifact required by Lab 12.

```text
START: Administrator prerequisites and dev container
|
`-- 01 Identity and project
    `-- 02 Models and verification
        `-- 03 Typed tools and local Responses testing
            `-- 04 Deploy and invoke hosted concierge
                |
                +-- 05 Hosted knowledge and retrieval
                |   `-- 06 Sessions and resiliency
                |       |
                |       +-- 07 Hosted MAF specialist orchestration
                |       |   `-- 08 Advisor approval and recovery -------+
                |       |                                             |
                |       `-- 09 Tracing and evaluation -----------------+-- 12 Hosted-to-hosted
                |           |                                             delegation [optional]
                |           `-- 10 Release gates and rollback
                |
                +-- 11 Prompt versus hosted [short, optional, terminal]
                |
                `-- 13 Structured batch Invocations [optional]
                    `-- 14 Hosted Skills and optional Toolbox [optional]

Core completion: 08 + 10
Lab 12 joins BOTH 08 and 09; it does not consume Lab 11.
Guided teaching route: 01..10, then selected 11..14.
Dependency-independent branches still share ports, sources, and Azure quota.
```

This is a dependency graph, not a timed critical-path estimate. Rehearsal will
establish per-lab durations. The deepest target chain remains nine labs through
Lab 12; branch completion time depends on real durations and resource contention.

## Migration scope

Migrate only workshop-related content; preserve the independent
`azure-ai-agents/`, `agent-framework/`, and other capability tracks.

| Surface | Work |
|---|---|
| Fourteen adjacent cell sources and generated notebooks | Align prerequisite restore, teaching, exercises, acceptance, handoffs, and navigation; regenerate from sources only |
| Fourteen lab READMEs and `3-day-labs/README.md` | Align titles, required/recommended ordering, graph, product lineage, checkpoints, and honest limitations |
| `shared/` products and internal drivers | Simplify Prompt Agent example; replace prompt-backed Lab 12 integration; preserve core behaviors and import-without-side-effects |
| `common/notebook_parts.py`, `3-day-labs/lab_helpers.py`, artifact guide, recovery helpers | Decouple Lab 12 from Lab 11; validate real scopes/versions; use clear producer/recovery messages |
| `tools/validate_workshop.py`, notebook converter, regression tests, CI | Update changed dependency/checkpoint assumptions; retain fourteen paths, offline behavior, and source parity |
| Workshop `README.md`, `SETUP.md`, `USE-CASE.md`, shared/data/infra guides | Update only affected claims, permission/setup ownership, service boundaries, scenario flows, and release behavior |
| Root `README.md`, `.github/copilot-instructions.md`, `.github/repo-index.md`, workshop-related prerequisite collateral | Align navigation and workshop descriptions; do not rewrite unrelated setup/track instructions |
| Datasheets or other customer deliverables, if present | Inventory tracked sources, regenerate affected PDF/Word outputs using their source tooling, and inspect rendered results |
| Skill sources and knowledge fixtures | Audit for affected references; preserve factual content and policy unless the changed exercise actually requires an edit |

The present workshop has fourteen numbered notebooks and seven shared topic
groups. Its `stretch6/part_a.json` and `part_b.json` currently encode the
Lab 11 -> Lab 12 prompt dependency. That pairing must change, not merely its prose.
Some index collateral entries may describe absent assets; inventory tracked files
before updating or regenerating anything.

## Revised execution plan

### 1. Establish contracts and a baseline

Record branch/worktree baseline and run existing offline validation in the
documented environment. Inventory tracked docs, generated collateral, notebook
sources, exercise edits, source fingerprints, product consumers, and runtime
artifact contracts. Record pre-existing failures separately.

Use the target table above as the agreed dependency design. Record each lab's
primary delta, retained behavior, accepted inputs/outputs, failure case, and
current-to-target change. Do not add another curriculum framework or duplicate
the existing validator's runtime dependency map.

**Exit:** every lab has an explicit contract and every affected document has
an owner/source; the implementation baseline is known.

### 2. Migrate foundation and continuity in learner order

Review Labs 1-4 first, then 5-6. Preserve verified project/model settings,
attendee scoping, root lock pins, explicit action cells, and local/deployed
separation. Make restoration and recovery understandable in a fresh kernel.

Audit the tool and policy edits introduced in Lab 3 against Lab 5's different
shared product. Carry required behavior forward through existing reusable code
or a minimal transfer, with acceptance evidence; explain intentional resets.
Do not pretend distinct hosted folders automatically retain learner edits.

For each lab or tightly coupled pair, change authoring source, guide, affected
shared code, tests, and generated notebook together. Update local navigation
and relevant overview claims in the same slice.

**Exit:** a learner can complete 1-6 one lab at a time, restart between labs,
and identify the same accepted behavior plus each new capability.

### 3. Preserve the primary hosted MAF and approval sequence

Align Labs 7-8 as the only full specialist-workflow teaching sequence.
Explicitly explain the branch from concierge to triage service. Retain parallel
fan-out/fan-in, bounded compliance reflection, pending-case snapshots, advisor
revision/approval, and local restart provenance.

Lab 8's handoff must identify the deployed version/endpoint and accepted
capabilities needed by Lab 12. Preserve pending/approved state semantics and
make the single-instance/file-state limitation prominent. Do not expand this
slice into production authorization or distributed-state implementation.

**Exit:** Lab 8 consumes original Lab 7 cases in a fresh kernel and publishes
real deployed triage evidence without repeating intake.

### 4. Stabilize operations before extending the concierge

Align Labs 9-10 with the pinned Lab 6 target. Introduce tracing before expecting
Azure correlation evidence, preserve exact responses/scores, and keep release
gating separate from judge execution. Keep the default rehearsal and optional
live/cloud pipeline distinction explicit.

Retain immutable evaluation/version references so an extension cannot silently
replace the measured product. Add recovery guidance for intentional candidate
changes: rerun affected evaluation and gate, not stale PASS reuse.

**Exit:** 9-10 run without 7-8, and the release gate consumes the exact accepted
evaluation bundle.

### 5. Replace the optional prompt/delegation content coherently

Change Lab 11 and Lab 12 in one integration slice so documentation, checkpoints,
runtime imports, and validation do not temporarily describe conflicting graphs.

Lab 11: retain one minimal, versioned Prompt Agent, one invocation and a concise
ownership comparison to Lab 4. Remove the multi-role ensemble, portal edit/
restore exercise, prompt-backed workflow publishing, and references consumed by
other labs. Check invocation plus explicit absence of downstream prompt usage.

Lab 12: reuse the triage graph/service from Labs 7-8; do not author a new graph.
Restore Labs 8 and 9, pin the remote target, and introduce the authenticated
delegation tool in an isolated concierge extension candidate. Teach bounded
timeouts, explicit remote errors, case/session correlation, and the retry/
duplicate-request boundary. First demonstrate a controlled failure, then one
deployed pending-case call and a trace correlated across caller/callee.

Do not forward an advisor decision automatically. Do not claim replica-safe
approval resume. If existing service telemetry lacks the necessary context
propagation, implement and test it in this slice before requiring live traces.
Verify current supported endpoint/authentication behavior before implementation;
the plan does not assume an unverified service-to-service SDK signature.

Decouple the old paired checkpoint: keep Lab 11's comparison evidence separate
and introduce a clearly named hosted-delegation contract for Lab 12. Update
`LAB_NUMBERS`, checkpoint validation, dependency declarations, recovery helpers,
and the artifact guide together. Reject old prompt-backed Lab 12 evidence with
an instruction to rerun the new Lab 12; do not replay Lab 11 or rewrite local
attendee artifacts automatically.

Remove obsolete prompt graph/snippet source and packaging references only after
replacement consumers are wired. Do not commit or silently reuse prepared
`triage_workflow.py`/`triage_agents.json` deployment copies from the old exercise.

**Exit:** core + Lab 12 works without running Lab 11; missing either Lab 8 or 9
blocks Lab 12 clearly; no Prompt Agent is invoked by hosted products.

### 6. Align the protocol and Skills extensions

Require Lab 4 for Lab 13 and explain structured stateless Invocations relative
to the learner's tested Responses host. Preserve deterministic claim facts,
bounded model explanations, and explicit optional deployment.

Lab 14 consumes accepted batch evidence but introduces a distinct Responses
Skills product. Explain that boundary rather than suggesting Invocations has
become a stateful service. Introduce Skill index/body loading before the learner
adds a Skill; make optional Toolbox failures/skips visible and retain egress/
privacy limitations. Do not add Prompt Agents or unrelated session prerequisites.

**Exit:** 13-14 work after Lab 4 without knowledge, MAF, operations, or Prompt
Agent lab artifacts.

### 7. Complete the documentation and collateral sweep

Local guides, notebook prose, and relevant overview text change with every
slice; this final sweep catches cross-document drift, not delayed documentation.
Align root/workshop agendas, the ASCII graph, setup roles, shared product map,
artifact contracts, use-case service boundaries, infrastructure guidance, and
author instructions. Check all fourteen titles and prerequisite links.

Audit old "Lab 11 -> 12", six-prompt-agent ensemble, prompt-backed hosted graph,
and generic "MAF workflows" claims. Retain statements about the original
implementation only in clearly labeled migration/history context.

Regenerate any affected customer collateral from tracked editable sources and
review rendered documents. Leave synthetic knowledge and unrelated infrastructure
content unchanged when it does not make a conflicting claim. Refresh the index
for added/removed source, boundaries, and contract ownership.

**Exit:** no current learner or distributed customer document contradicts the
implemented dependencies, hosted focus, or evidence limits.

### 8. Rehearse learner journeys and integrate

Run focused tests per slice, then the full offline validator. Update existing
tests rather than adding a parallel validation system. Cover new prerequisite
failures, checkpoint incompatibility, source/version invalidation, retained
exercise behavior, delegation failures, and import-without-cloud-replay.

With approved live resources, rehearse:

- Core Labs 1-10 in order with a fresh kernel at each boundary.
- Operations 9-10 directly after 6, with no triage artifacts.
- Lab 12 after 8 and 9, with no Lab 11 artifacts; preserve the core release target.
- Labs 13-14 after 4, with no knowledge/MAF/Prompt Agent artifacts.
- Lab 11 alone after 4, then confirm it is unnecessary for all other routes.
- Interrupted/retried work at the tool/deploy, pending-approval, and eval/gate
  boundaries; wrong scope, changed source, unavailable service, and busy-port cases.

Do not delete real learner checkpoints to manufacture a cold start; use an
isolated rehearsal workspace and approved attendee suffix/resources.
Record actual teach/exercise durations and observe a learner explaining what
changed, where it runs, what evidence passed, and what remains unproven.

**Exit:** offline consistency and live notebook behavior are separately reported;
unrun live checks remain open, not inferred from offline PASS.

## Scope boundaries and completion

This migration is not a dependency upgrade, infrastructure redesign, new A2A
protocol implementation, production authorization system, or distributed
workflow-state project. It does not promise that the revised workshop runs
within a particular day length before rehearsal.

Code migration completion requires all fourteen labs to follow the conventions,
core and optional contracts to restore without hidden predecessor state, no
hosted path to depend on Prompt Agents, retained behavior acceptance, and affected
documents to match the implemented curriculum. Release readiness additionally
requires the approved live notebook rehearsals in Step 8.

Implementation includes a sixth isolated hosted package, the independent
`hosted_delegation/part_a.json` handoff, terminal prompt comparison, explicit
Lab 4 prerequisites for Labs 11/13, accepted tool/policy transfer into the
knowledge concierge, deployed triage references, immutable evaluation/release
evidence, regenerated notebooks, and updated offline checks. The old
prompt-backed graph/snippet and its graph-only tests are removed.

The existing Python 3.14 environment supplies the relevant pinned SDKs; no
dependency upgrade or cloud provisioning is part of this migration. The Docker
daemon is unavailable in the author environment. Offline checks are run with
`py -3.14` on Windows, separately from the Linux dev-container learner route.
No tracked workshop Datasheets directory is present; unrelated root prerequisite
collateral is unchanged. Do not describe unrun live or rendered-collateral checks
as passed.

Offline validation uses an isolated repository copy for hosted package snapshots.
Its retained-behavior input is a synthetic author-test fixture passed through the
real transfer generator, not a fabricated learner checkpoint. Production package
preparation still rejects missing accepted behavior; no fixture is imported from
an attendee workspace or shipped as a runtime fallback.

Integration verification: the complete offline workshop validator passed with
Python 3.14, including 192 regression tests, all fourteen notebook/source pairs,
the exact dependency table, twenty converter checks in the isolated copy, and
six hosted package snapshots. No live Azure or Docker build result is inferred.
