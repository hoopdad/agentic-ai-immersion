# Lab 3: Hosted multi-agent handoff

| | |
|---|---|
| Goal | Run the Healthcare Marketplace triage workflow (intake, two specialists in parallel, compliance review, advisor handoff packet) inside a hosted agent, and let the licensed advisor approve, revise or decline the packet on the next HTTP turn. |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab2/hosted.json` (or `python catch_up.py --through 2`; `--standalone` skips the check) |
| Produces | `artifacts/lab3/handoff_packets/S1.json`, `S2.json`, `S3.json`, `artifacts/lab3/hosted.json`, `artifacts/lab3/sessions/` |
| Learn path modules | 8 Orchestrate a multi-agent solution using the Microsoft Agent Framework; 6 Build agent-driven workflows using Microsoft Foundry; 7 Develop an AI agent with Microsoft Agent Framework |

**Where this runs:** both. The notebook (workstation) plays participant and advisor against `hosted/main.py` on port 8088 and writes the final packets. `hosted/main.py` (container) runs the `WorkflowBuilder` graph and pauses at `request_info`; Foundry runs it as `healthcare-marketplace-triage-hosted` after `azd up`.

## Workstation setup and paths

From the workshop root (`build-and-operate-foundry-agents`):

```bash
# Reopen the repository in its dev container; dependencies are preinstalled.
python --version  # Python 3.14
# Dependencies were installed by the repository dev-container bootstrap.
```

Select `python` as the notebook kernel. Start the notebook from its own folder:

```bash
cd ./labs/lab3-hosted-multi-agent-handoff
python -m jupyter lab ./lab3_walkthrough.ipynb
```

Run the driver from `labs`:

```bash
cd ./labs
python ./lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py --auto-approve --standalone
```

Run the hosted server manually only from the folder containing `main.py`:

```bash
cd ./labs/lab3-hosted-multi-agent-handoff/hosted
python ./prepare.py
python ./main.py
```

The driver resolves all paths from its own file, starts `hosted\main.py` with an explicit working directory,
writes process output to `labs/artifacts/lab3/hosted_local.log`, and stops the child process on success or failure.

## What you'll learn
- Build an explicit `WorkflowBuilder` graph with custom executors: fan-out to two specialists, fan-in by counting, a compliance gate that sends a draft back once, and a coordinator that asks a human.
- Produce a strict JSON handoff packet with Pydantic `response_format` and carry compliance flags through it. A schema-valid packet is an inspectable handoff contract, not proof that its facts are correct, its content is safe, or an advisor approved it.
- Explain how `ctx.request_info` pauses a workflow and how to resume it with `workflow.run(responses={request_id: ...})`.
- Move human-in-the-loop from a terminal `input()` to HTTP turns: the packet comes back `pending_advisor_approval`, the decision arrives as the next `POST /responses`.
- Keep the paused case in the file-backed `common.session_store` so a local process restart can still finish it; the file is not shared across deployed replicas.
- Route every Responses turn through agent middleware that short-circuits the model when the turn is a case or a decision.

## Technical features taught

| Feature | Foundry / SDK object | Where in the code | Why it matters for Healthcare Marketplace |
|---|---|---|---|
| Explicit workflow graph | `WorkflowBuilder(start_executor=..., output_from=[coordinator], intermediate_output_from="all_other").add_edge(a, b).build()` | `hosted/marketplace_workflow.py` `build_workflow()` | The triage path is a reviewed graph; only the coordinator emits the final packet, while specialist updates remain intermediate |
| Custom executors | `Executor`, `@handler async def h(self, msg: T, ctx: WorkflowContext[Out])` | `IntakeExecutor`, `SpecialistMerge`, `ComplianceGate`, `AdvisorCoordinator` | Intake, merge, gate and coordinator are plain Python you can unit test |
| Fan-out / fan-in | `ctx.send_message(..., target_id=...)` + a counting merge | `IntakeExecutor.start`, `SpecialistMerge.collect` | Marketplace and Accounts answer in parallel for "both LOB" participants |
| Agents as workflow nodes | `AgentExecutor(agent, id=...)`, `AgentExecutorRequest/Response` | `build_workflow()` | Specialists are ordinary `Agent`s reused from any lab |
| Structured outputs | `Agent(..., default_options={"response_format": ReviewVerdict / HandoffPacket})` | `hosted/marketplace_specialists.py` builders, `parse_structured()` | The advisor gets a schema-checked packet, not prose |
| Reflection with a bound | `ComplianceGate.decide` (revise once, then flag) + `guardrails.contains_recommendation` | `hosted/marketplace_workflow.py` | A bad prompt cannot loop forever; unresolved drafts are flagged for the human |
| Human in the loop | `ctx.request_info(request_data=..., response_type=str)`, `@response_handler`, `workflow.run(responses={...})` | `AdvisorCoordinator`, `start_case()`, `resume_case()` | The sample simulates advisor review; production must authenticate an authorized advisor before accepting a decision |
| HITL across HTTP turns | `@agent_middleware` router sets `context.result` | `hosted/main.py` `triage_router`, `TriageService.start/decide` | A web chat has no `input()`; the decision is simply the next turn |
| Pending state | `common.session_store` (`SessionRecord.notes["packet"]`), file-backed under `artifacts/lab3/sessions/` | `TriageService.store_pending/store_final/decide` | A local process restart can resume from the packet (`resume_path=session_store`); files do not provide cross-replica or version-roll continuity |
| Knowledge for specialists | local `search_knowledge` over `data/knowledge`, or `MCPStreamableHTTPTool` to Lab 2's KB when `MARKETPLACE_KB_MCP_URL` | `hosted/marketplace_specialists.py` `knowledge_tool()` | Same container, two knowledge backends; citations either way |

## Teach (10 min)
- Lab 1 and 2 hosted one agent. Lab 3 hosts a **workflow**: the container still speaks Responses, but a turn now runs a graph of four agents and three pure-Python executors and returns a packet. Role separation makes responsibilities, review, and advisor handoff explicit; more model calls are not by themselves evidence of lower cost, faster answers, or better quality.
- Fan-out and fan-in are explicit edges plus a counter. Intake decides which specialists are in scope for this participant (marketplace, accounts, both) and sends one request per specialist; the merge waits for all of them.
- Reflection: the compliance reviewer returns a structured verdict. If it (or the cheap heuristic) flags a recommendation, the gate sends the offending section back once. Once. Then it forwards the draft with the flag attached so the human sees it. This is a bounded review loop with a defined exit: an unresolved flag is escalation evidence, not an automatic pass or proof that reflection improved the answer.
- `request_info` is how Agent Framework asks a human. The workflow yields a `request_info` event with a `request_id` and goes idle. In a terminal you call `input()` and resume with `workflow.run(responses={request_id: answer})`. A web chat cannot block on `input()`.
- So the hosted agent returns the packet with `status: pending_advisor_approval` and remembers two things: the paused workflow (in memory, this process) and the packet (in the file-backed `common.session_store`). The advisor's next turn resumes the workflow if it is still here; after a local process restart, approve and decline finish from the stored packet and revise re-runs only the packet writer. A different deployed replica or version cannot access that file.
- The middleware trick: every turn passes through `triage_router` before the outer model is called. A case envelope or a decision is handled deterministically and the model never runs; anything else falls through to the outer agent, which explains the format. Deterministic routing is what you want in front of a compliance process.
- Same deploy story as Lab 1: flat folder, `azd up`, `healthcare-marketplace-triage-hosted` version 1. The session map is file-backed; use one replica for deployed human-approval turns. Set `MARKETPLACE_KB_MCP_URL` to use Lab 2's knowledge base instead of the local search.

```
POST /responses  {"input": "{\"session_id\":\"S3-../",\"participant_id\":\"P-1005\",\"message\":\".../"}"}
   |
   v  triage_router (middleware)
 intake --lob=both--> marketplace-guide --+
        \-----------> accounts-assistant -+--> merge --> compliance-reviewer --> gate --(revise once)--> specialist
                                                                                   |
                                                                                   v
                                                        advisor-coordinator --> advisor-handoff (HandoffPacket)
                                                                 |
                                            request_info: PAUSE  |  session_store[S3-..] = packet, status pending
   <-- {"status":"pending_advisor_approval","packet":{...},"next":"approve | revise: .. | decline: .."}

POST /responses  {"input": "{\"session_id\":\"S3-../",\"advisor\":\"revise: add the IEP dates\"}"}
   -> resume_case(request_id, feedback) -> advisor-handoff again -> PAUSE again (packet_attempts 2)
POST /responses  {"input": "approve"}  (session id from the Responses session or the envelope)
   -> yield_output -> {"status":"approved","packet":{...,"advisor_decision":"approve"}}
```

## Demo (10 min)
1. From `labs`, run `python ./lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py --auto-approve --scenario S3`. While it runs, tail `artifacts\lab3\hosted_local.log` in a second terminal: `intake CASE-S3-...: lob=both, specialists=['accounts-assistant', 'marketplace-guide']`, two `merge: got ...` lines, `compliance: compliant=True`, then the pause.
2. Point at the client output: `status=pending_advisor_approval lob=both attempts=1`, then `advisor> revise: add the IEP dates for turning 65 to open_questions`, then `attempts=2`, then `advisor> approve`, then `wrote artifacts/lab3/handoff_packets/S3.json (decision approve ...)`.
3. Open `S3.json`. Read `open_questions` (the "which one should I pick" request is there for the advisor, not answered), `facts_gathered` with sources, `compliance_flags`, `advisor_decision`, `packet_attempts`.
4. Run `--auto-approve --scenario S2 --restart-between-turns`. The server dies after the pending packet and comes back before `approve`; the reply shows `resume_path=session_store`. Open `artifacts/lab3/sessions/S2-*.json`: this is what survived.
5. `--deploy`, then in the portal show `healthcare-marketplace-triage-hosted` version 1 and its logs carrying the same `[healthcare-marketplace-triage]` lines.

## Do (35 min)
1. **Run all three scenarios (10 min).** `python lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py --auto-approve`. You should see three packets written. Checkpoint: S1 is `lob=marketplace`, S2 `lob=accounts`, S3 `lob=both`; no packet's `options_discussed` names a plan to pick.
2. **YOUR TURN (10 min): revise instead of approve.** Run without `--auto-approve` and with `--scenario S3`. At the prompt type `revise: add the IEP dates for turning 65 to open_questions`, then `approve`. The notebook gate verifies `packet_attempts >= 2`, the IEP question, the final decision and packet safety.
3. **YOUR TURN (10 min): lose the process, keep the case.** Run `--auto-approve --scenario S2 --restart-between-turns`. The notebook gate verifies `resume_path=session_store` and the persisted session JSON. This proves local restart continuity; the file store is not shared across deployed replicas.
4. **YOUR TURN (5 min): make the reviewer earn its keep.** In `hosted/marketplace_specialists.py` add "Finish with the single plan you would pick." to `MARKETPLACE_INSTRUCTIONS`. The notebook gate checks the rejection log, the one-revision route, and the safe final packet. Remove the line after it passes.
5. **YOUR TURN (10 min): replace the keyword classifier with a model.** Keep `classify_lob()` as the fallback. The workflow accepts an optional `agents["lob-classifier"]`; add a `LobCall` structured-output agent to `build_all()`. The notebook gate sends an ambiguous declined-card/prescription case through the workflow and requires `lob=accounts`. This routes work to the appropriate specialist; it does not select a cheaper or stronger model tier or establish a routing cost benefit.
6. **Deploy (optional in the room, 10 min).** `--deploy` prints commands only and requires `PROJECT_RESOURCE_ID`. Paste the absolute, quoted, fail-fast Bash block into an authenticated terminal. Wait for `active`, then separately record the version and run the deployed smoke test.

## Checkpoint (5 min)
Paste `S3.json`'s `open_questions`, `compliance_flags` and `advisor_decision` in the room chat. Lab 4's core evaluation targets the Lab 2 concierge and requires the Lab 2 checkpoints; Lab 3 metadata is optional. Keep these packets as handoff evidence, not as required inputs to that evaluation.

## If you're behind
From `labs`, run `python ./catch_up.py --through 3` (vendors and writes `hosted.json`). The packets still need a model run:
`python ./lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py --auto-approve --standalone`.
Skip the deploy step.

## Stretch (only if you're done early)
Enable `build_workflow(..., checkpoint_dir=...)` (VERIFY tag in `marketplace_workflow.py`) so the paused workflow itself, not only the packet, survives a restart, then make `TriageService.decide` resume from the checkpoint instead of re-running `advisor-handoff` on `revise`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Missing artifact artifacts/lab2/hosted.json` | Lab 2 not run | `python catch_up.py --through 2`, or add `--standalone` (local knowledge search) |
| Step 3.8 exits at startup with `Response handler parameter 'ctx' must be annotated as WorkflowContext` | Agent Framework 1.9.0 reads string annotations from `from __future__ import annotations` without resolving them | Keep that future import out of `hosted/marketplace_workflow.py`; its handler annotations must resolve to runtime types. Rerun Step 3.8 after updating the source; no dependency upgrade is required |
| A case or revision fails with `Message.__init__() got an unexpected keyword argument 'text'` | The pinned SDK accepts message text in `contents`, not a `text` constructor argument | Use `Message("user", contents=[text])` for workflow requests and the same `contents` pattern for assistant replies |
| Step 3.8 returns `TypeError: 'AgentResponseUpdate' object is not subscriptable` | Specialist streaming updates were designated as final workflow outputs and mistaken for the handoff packet | Set `output_from=[coordinator]` and `intermediate_output_from="all_other"` in `build_workflow`; rerun Step 3.8 after updating the source |
| Reply `status: no_pending_case` on an advisor turn | Session id in the decision does not match the envelope's, or the case was already closed | Reuse the exact `session_id`; one case per session id; start a new session for a new case |
| Reply `status: error` with `AgentExecutorResponse` or `executor_id` in the text | Framework build differs from the VERIFY notes in `marketplace_workflow.py` | Check the two VERIFY tags (`executor_id`, `AgentExecutor(agent, id=)`) against the installed version |
| Turn takes 60-120 s | Two specialists, a reviewer and the packet writer run per case | Expected; the driver uses a 600 s timeout. Watch the log for progress |
| `resume_path=session_store` after an unexpected restart | The process lost its paused workflow and did not find the session file | Check the configured session directory and the server log; deployed replicas do not share this file store |
| Packet `compliance_flags` contains `heuristic: ...` on every run | A specialist instruction invites recommendation language | Read the flagged section; tighten the instruction; the gate revises once and then flags |
| 401/403 on deploy or invoke | Roles (Project Manager to deploy, Agent Consumer or User to invoke) | Same as Lab 1; wait for propagation |
| Version `failed`, `ModuleNotFoundError: common` in the error | `prepare.py` not run before `azd up` | Run it, `azd up` again |
| `424 session_not_ready` | Container still starting (four agents build at startup) | Read the version logstream; wait for `agent healthcare-marketplace-triage-hosted: ...` before invoking |
| Wrong LOB for a message | Keyword classifier | Use the classifier YOUR TURN exercise: model-based classification with the keyword list as fallback |

## Deployment and validation contracts

- `python ./lab3_hosted_multi_agent.py --deploy` is print-only. It fails before printing unless
  `PROJECT_RESOURCE_ID` is set, and the generated block uses the absolute `hosted` path plus
  the command exit status checks after every external command.
- After `azd up` reports success, wait for the version to become `active`. From `hosted`, record and smoke it
  as separate steps:

```bash
python ../lab3_hosted_multi_agent.py --record-version '<version>'
python ./test_local.py --deployed
```

- Offline validation needs no Azure or model:

```bash
cd ./labs/lab3-hosted-multi-agent-handoff/hosted
python ./test_local.py --offline
```

The offline suite checks all three classifier outcomes, the documented ambiguous keyword result, decision
parsing/finalization, structured reviewer output, packet fields, citations, recommendation detection, PII
redaction and profile minimization. The local/deployed smoke path runs S3 through pending, revise and approve.
The workshop regression suite also checks hosted entry-point imports, agent construction and middleware replies, and runs the coordinator's
pending, revise, approve and decline paths through a real workflow with an offline packet writer.
It also runs the complete streaming specialist graph through the file-backed service, including compliance
reflection and advisor revision, and verifies that only the final packet is emitted as `output`.

## References
- Learn: [Orchestrate a multi-agent solution using the Microsoft Agent Framework](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/) (module 8), [Build agent-driven workflows using Microsoft Foundry](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/) (module 6)
- Agent Framework workflows, request_info and checkpoints: https://learn.microsoft.com/en-us/agent-framework/workflows/
- Base repo reused: `agent-framework/workflows/5-credit-limit-with-human-input.ipynb` (request_info loop), `agent-framework/workflows/6-*` (executor shapes), `hosted-agents/README.md` (deploy, RBAC)
