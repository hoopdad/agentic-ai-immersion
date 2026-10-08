# Generated lab checkpoints

Walkthrough notebooks write checkpoint metadata, transcripts, evaluation
reports and local session state here. These are execution evidence, not
reviewed reusable intelligence; file existence alone is not an acceptance pass.

| Location | Producer | Consumers |
|---|---|---|
| `lab1/part_a.json` … `lab5/part_a.json`, `stretch6/part_a.json`, `stretch7/part_a.json` | Each [A walkthrough](../README.md) | Corresponding B walkthrough in a fresh kernel; validated project/attendee scope and handoff metadata |
| `lab1/part_b.json` … `lab5/part_b.json`, `stretch6/part_b.json`, `stretch7/part_b.json` | Each [B walkthrough](../README.md) | Completion evidence alongside the unchanged cumulative artifacts below |
| `lab1/project.json` | Foundry project/model setup notebook | Verified project/model references and chat/embedding smoke evidence |
| Repository-root `.env` (outside this folder) | Foundry project/model setup notebook | Configuration persistence for all later notebooks |
| `lab2/hosted.json` | Hosted basics | Lab 3 |
| `lab3/knowledge.json`, `hosted.json`, `sessions/` | Knowledge and continuity | Labs 4–5 and Stretch 6 |
| `lab4/handoff_packets/`, `hosted.json`, `sessions/` | Multi-agent approval | Human handoff review; optional Lab 5 metadata |
| `lab5/eval_report.md`, `gate_result.json`, `pipeline.md` | Operations | Release review and promotion gates |
| `stretch6/agents.json`, `handoff_packets/` | Platform-managed agents | Hosted workflow delegation |
| `stretch7/invocations.json`, `claim_reviews/`, `skills_transcript.md` | Invocations/Skills | Structured review and tool-use inspection |

Reopen the producing notebook and rerun required checkpoint cells to regenerate
missing evidence. Do not commit generated outputs, credentials or executed notebooks.
Half checkpoints contain real resource, configuration or evidence references,
not fabricated completion markers. A checkpoint must match the active project
and attendee scope; its presence never replaces the relevant acceptance checks.
