# Generated lab checkpoints

Walkthrough notebooks write checkpoint metadata, transcripts, evaluation
reports and local session state here. These are execution evidence, not
reviewed reusable intelligence; file existence alone is not an acceptance pass.

Directory names retain the original topic namespaces, not learner lab
numbers. `part_a.json` and `part_b.json` are internal handoff filenames;
follow the numbered [Lab 1-14 prerequisite table](../README.md#sequence-and-artifact-chain).

| Location | Producer | Consumers |
|---|---|---|
| `lab1/part_a.json` … `lab5/part_a.json`, `stretch7/part_a.json` | Labs 1, 3, 5, 7, 9, 13 | Labs 2, 4, 6, 8, 10, 14 respectively restore scoped, fingerprinted metadata |
| `lab1/part_b.json` … `lab5/part_b.json`, `stretch7/part_b.json` | Labs 2, 4, 6, 8, 10, 14 | Accepted product/completion evidence; follow the dependency table rather than assuming the next number consumes it |
| `stretch6/part_a.json`, `stretch6/prompt_agents.json`, `stretch6/prompt_turn.json` | Lab 11 | Terminal comparison evidence only; no downstream consumers |
| `hosted_delegation/part_a.json` | Lab 12 | New independent hosted-to-hosted delegation contract after both Labs 8 and 9; isolated candidate evidence |
| `lab1/project.json` | Lab 2 | Verified project/model references and chat/embedding smoke evidence |
| Repository-root `.env` (outside this folder) | Lab 2 | Configuration persistence for all later notebooks |
| `lab2/hosted.json` | Lab 3 creates local metadata; Lab 4 records deployed acceptance | Lab 4 reuses local handoff; Labs 5, 11 and 13 require Lab 4 acceptance |
| `lab3/knowledge.json`, `hosted.json`, `sessions/` | Lab 5 builds knowledge; Lab 6 records continuity/deployment | Labs 7 and 9; accepted concierge baseline reused by Lab 12 through its prerequisites |
| `lab3/accepted_behavior.json` | Lab 5 | Source-bound transfer of Lab 3's accepted `get_sponsor` function and rule 3 enrollment policy; Lab 6 records retained behavior and hosted source hash |
| `lab4/handoff_packets/`, `hosted.json`, `sessions/` | Lab 8 | Human handoff review; optional Lab 9 metadata; Lab 12's pinned deployed triage reference |
| `lab4/deployed_triage.json`, `handoff_packets/deployed-S2.json` under `lab4/` | Lab 8 | Exact triage name/version/project/protocol and separate deployed invocation evidence for Lab 12; original local packets remain intact |
| `lab5/eval_report.md`, `gate_result.json`, `pipeline.md` | Labs 9-10 | Release review and promotion gates |
| `stretch7/invocations.json`, `claim_reviews/`, `skills_transcript.md` | Labs 13-14 | Structured review and tool-use inspection |

Lab 12 does not consume Lab 11 or reinterpret old `stretch6/part_b.json`,
`agents.json` or prompt graph outputs as hosted delegation acceptance. Rerun
the new Lab 12 against accepted Labs 8 and 9 if legacy evidence is present;
never fabricate or automatically upgrade checkpoints.

Preserve the exact core concierge version and evaluation/release references
from Labs 9-10 when deploying a Lab 12 extension candidate. Changed source,
scope, configuration or measured versions require affected acceptance to be
rerun, not stale PASS reuse. Other topic mappings remain unchanged.
Lab 9's checkpoint binds the measured bundle hash and evaluated target;
evaluation defaults to local mode. Lab 10 validates the exact bundle/results
and rejects candidate source changes rather than rerunning judges. Default
promotion and rollback remain rehearsal, not proof of live deployment.

Local transcripts and file-backed pending-state recovery are local evidence;
deployed acceptance requires an actual invocation of the recorded version.
Lab 12's correlated trace claim requires current caller/callee Azure evidence,
not just local spans. A pending case is not an advisor decision, distributed
resume, or production authorization. Label skipped live/preview checks.

Reopen the producing notebook and rerun required checkpoint cells to regenerate
missing evidence. Do not commit generated outputs, credentials or executed notebooks.
Lab checkpoints contain real resource, configuration or evidence references,
not fabricated completion markers. A checkpoint must match the active project
and attendee scope; its presence never replaces the relevant acceptance checks.
