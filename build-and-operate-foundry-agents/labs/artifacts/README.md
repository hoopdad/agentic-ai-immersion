# Generated lab checkpoints

Walkthrough notebooks write checkpoint metadata, transcripts, evaluation
reports and local session state here. These are execution evidence, not
reviewed reusable intelligence; file existence alone is not an acceptance pass.

Directory names retain the seven original topic namespaces, not learner lab
numbers. `part_a.json` and `part_b.json` are internal handoff filenames;
follow the numbered [Lab 1-14 prerequisite table](../README.md#sequence-and-artifact-chain).

| Location | Producer | Consumers |
|---|---|---|
| `lab1/part_a.json` … `lab5/part_a.json`, `stretch6/part_a.json`, `stretch7/part_a.json` | Labs 1, 3, 5, 7, 9, 11, 13 | The next numbered lab restores scoped, fingerprinted metadata in a fresh kernel |
| `lab1/part_b.json` … `lab5/part_b.json`, `stretch6/part_b.json`, `stretch7/part_b.json` | Labs 2, 4, 6, 8, 10, 12, 14 | Completion evidence alongside the unchanged cumulative artifacts below |
| `lab1/project.json` | Lab 2 | Verified project/model references and chat/embedding smoke evidence |
| Repository-root `.env` (outside this folder) | Lab 2 | Configuration persistence for all later notebooks |
| `lab2/hosted.json` | Lab 3 creates local metadata; Lab 4 records deployed acceptance | Lab 4 reuses the local handoff; Lab 5 requires deployed evidence |
| `lab3/knowledge.json`, `hosted.json`, `sessions/` | Lab 5 builds knowledge; Lab 6 records continuity/deployment | Labs 7, 9 and 11 |
| `lab4/handoff_packets/`, `hosted.json`, `sessions/` | Lab 8 | Human handoff review; optional Lab 9 metadata |
| `lab5/eval_report.md`, `gate_result.json`, `pipeline.md` | Labs 9-10 | Release review and promotion gates |
| `stretch6/agents.json`, `handoff_packets/` | Lab 12 | Hosted workflow delegation |
| `stretch7/invocations.json`, `claim_reviews/`, `skills_transcript.md` | Labs 13-14 | Structured review and tool-use inspection |

Reopen the producing notebook and rerun required checkpoint cells to regenerate
missing evidence. Do not commit generated outputs, credentials or executed notebooks.
Lab checkpoints contain real resource, configuration or evidence references,
not fabricated completion markers. A checkpoint must match the active project
and attendee scope; its presence never replaces the relevant acceptance checks.
