# Lab 4: Hosted multi-agent handoff

| | |
|---|---|
| Goal | Run intake, parallel specialists, compliance reflection and advisor packet creation inside a hosted agent; approve, revise or decline on the next HTTP turn |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab3/hosted.json` and knowledge configuration |
| Notebooks | [Lab 4A](lab4a_walkthrough.ipynb), then [Lab 4B](lab4b_walkthrough.ipynb) in a fresh kernel |
| Produces | `artifacts/lab4/handoff_packets/S1.json`, `S2.json`, `S3.json`, `hosted.json`, `sessions/` |
| Learn alignment | Agent Framework orchestration, Foundry workflows and human collaboration |

Open the paired notebooks in this folder using the dev-container `/usr/local/bin/python`
kernel. They play participant and advisor against the local product on port
8088, writes evidence and manages process cleanup. Foundry runs the same
`hosted/main.py` as `healthcare-marketplace-triage-hosted` after explicit notebook deployment.

## Two independently runnable halves

| Half | Scope | Durable checkpoint |
|---|---|---|
| 4A (30 min) | Graph construction, specialist fan-out, bounded compliance reflection, model classification; stops at pending approval | `artifacts/lab4/part_a.json`, immutable `pending_cases.json`/`pending_sessions.json`, classification/compliance evidence and persisted sessions |
| 4B (30 min) | Resume A's S3 revision and S2 restart path, approve existing packets, deploy and verify final approval | `artifacts/lab4/part_b.json` and original `hosted.json`/`handoff_packets/` |

4B imports definitions, not 4A's notebook, and does not repeat intake or specialist calls.
Missing, changed, or differently scoped A evidence blocks B before advisor/deployment actions.
Do not delete pending sessions between halves; rerunning A is required after changing its evidence or Azure context.
B compares live session packets/status to A's immutable snapshot before sending any advisor decision.
On ordinary B replay, previously approved packets are accepted only with matching case identity, safety, and persisted recovery provenance; intake is not repeated.
Rerunning an A action invalidates both completion checkpoints; rerunning B invalidates its checkpoint until success.
Each risky cell clears its acceptance outcome before execution, and publication requires every intended current gate.
4A fingerprints the hosted Python/package and relevant shared runtime sources actually tested by classification in `orchestration_sources.json`.
4B checks those fingerprints on load and immediately before deployment; removing the classifier or changing tested code requires a new A acceptance run.

## What you'll learn

- Build explicit fan-out/fan-in, structured agent nodes and a bounded compliance gate.
- Produce a Pydantic handoff contract and carry unresolved flags to a human.
- Pause with `ctx.request_info` and resume with an advisor response across HTTP turns.
- Route cases/decisions deterministically before invoking the outer model.
- Recover a pending packet after a local restart, while explaining file-backed limits.

## Technical features taught

| Feature | Object / product location | Why it matters |
|---|---|---|
| Explicit workflow | `WorkflowBuilder` in `hosted/marketplace_workflow.py` | Only the coordinator emits final output; specialist updates are intermediate |
| Custom executors | `Executor`, `@handler`, `WorkflowContext` | Intake, merge, compliance gate and coordinator are testable Python |
| Fan-out/fan-in | Targeted `ctx.send_message` and counting merge | Both specialists run when both lines of business are relevant |
| Agent nodes and schemas | `AgentExecutor`, `ReviewVerdict`, `HandoffPacket` | Review and packet contracts are inspectable, not unstructured prose |
| Bounded reflection | One specialist revision, then unresolved flags | A poor instruction cannot cause an endless loop |
| Human pause/resume | `ctx.request_info`, `@response_handler`, `workflow.run(responses=...)` | Advisor judgment arrives as another request, not blocking terminal input |
| Deterministic HTTP routing | Agent middleware in `hosted/main.py` | Cases and decisions bypass the outer model |
| Pending packet | File-backed `common.session_store` | Local restart recovery only, not shared replica/version continuity |
| Specialist knowledge | Local reviewed documents or Lab 3's MCP KB | Same rules and citations across the workflow |

Adjacent `lab4a_specialist_orchestration.py` and `lab4b_advisor_recovery.py` are cell sources;
internal `lab4_hosted_multi_agent.py` supplies reusable definitions, not an
alternative learner driver. Product files remain editable in the guided exercises.

## Teach (10 min)

Labs 2–3 hosted one agent; this lab hosts a workflow. The Responses envelope
stays the same while a turn runs a graph and returns a packet. Role separation
makes review and ownership explicit, but extra calls alone do not establish
lower cost, faster answers or improved quality.

Intake selects marketplace, accounts or both. Explicit edges fan out; the merge
waits for all selected specialists. The reviewer and deterministic heuristic
may request **one** revision; any unresolved flag travels to the advisor.
That flag is escalation evidence, not automatic acceptance.

The workflow pauses with a request ID. The container retains the paused workflow
in memory and the pending packet in files. The next advisor turn resumes the
workflow; after a local restart, approval/decline can finish from the packet and
revision reruns the packet writer. A different deployed replica cannot read
that local file. Use one replica for this teaching deployment.

Schema validity is not proof of factual accuracy, safety or authorization.
The workshop simulates an advisor; production must authenticate an authorized
advisor before accepting any decision.

## Demo (10 min)

1. Run the S3 notebook scenario and inspect `artifacts/lab4/hosted_local.log`:
   both specialists, merge, review and pause.
2. Send the notebook's revise response about IEP dates, inspect the second
   packet attempt, then send approval.
3. Open `S3.json` and inspect facts/sources, open questions, flags and decision.
4. Run the restart-between-turns notebook exercise for S2. Require
   `resume_path=session_store` and inspect persisted session evidence.
5. Optionally deploy from the notebook and inspect the active version's logs.

## Do (35 min)

1. Run S1–S3 cells. Require marketplace, accounts and both routing respectively;
   no packet may pick a plan.
2. **YOUR TURN: revise instead of approve.** Add the IEP question via the advisor
   response input. The gate requires at least two packet attempts, the question,
   the final decision and packet safety.
3. **YOUR TURN: lose the process, keep the case.** Run the notebook restart gate
   and verify both recovery route and persisted session JSON.
4. **YOUR TURN: make review earn its keep.** Temporarily add a recommendation
   instruction in `hosted/marketplace_specialists.py`. Inspect the rejection,
   single-revision route and safe pending packet in 4A; remove the instruction afterward.
5. **YOUR TURN: model-based classification.** Retain `classify_lob()` as fallback,
   add a structured `LobCall` classifier and run the ambiguous card/prescription
   gate, which requires accounts routing. This is task routing, not a demonstrated cost benefit.
6. Optional deployment: use the notebook action, wait for `active`, record the
   real version in `DEPLOYED_VERSION` and run **Verify the deployed handoff**.

## Checkpoint (5 min)

Share S3's `open_questions`, `compliance_flags` and `advisor_decision`.
Lab 5 evaluates the Lab 3 concierge; these handoff packets are review evidence,
not mandatory input to that evaluation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Missing Lab 3 artifact | Return to its notebook and rerun checkpoint cells |
| Handler annotation failure | Retain runtime-resolved `WorkflowContext` annotations in the product; rerun preparation/readiness |
| `Message` rejects `text` | The pinned SDK uses `contents=[text]` |
| Streaming update mistaken for a packet | Keep final output on the coordinator and specialist output intermediate |
| `no_pending_case` | Reuse the exact session ID; start a new session for a new case |
| Slow turn | Multiple model calls can take minutes; inspect the saved log before retrying |
| Local restart loses a packet | Check the same session directory and session ID; deployed replicas do not share files |
| Persistent compliance flags | Inspect the flagged instruction/section; the bounded gate may escalate rather than repair everything |
| 401/403 or startup failure | Check approved network path, identity roles, active-version logs and propagation |
| Wrong LOB | Run the classifier exercise and inspect its fallback behavior |

## Follow-up and references

Explore workflow checkpointing so the paused workflow itself can survive a
restart, rather than relying only on stored packet recovery. Internal offline
tests validate graph output, reflection and decision contracts but are not
extra learner commands or evidence of Azure readiness.

- [Azure agent learning path](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/)
- [Agent Framework workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/)
