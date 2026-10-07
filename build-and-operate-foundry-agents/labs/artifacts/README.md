# Generated lab checkpoints

Walkthrough notebooks write checkpoint metadata, transcripts, evaluation
reports and local session state here. These are execution evidence, not
reviewed reusable intelligence; file existence alone is not an acceptance pass.

| Location | Producer | Consumers |
|---|---|---|
| `lab1/` | Foundry project/model setup notebook | Later notebooks also read its persisted repository-root `.env` |
| `lab2/hosted.json` | Hosted basics | Lab 3 |
| `lab3/knowledge.json`, `hosted.json`, `sessions/` | Knowledge and continuity | Labs 4–5 and Stretch 6 |
| `lab4/handoff_packets/`, `hosted.json`, `sessions/` | Multi-agent approval | Human handoff review; optional Lab 5 metadata |
| `lab5/eval_report.md`, `gate_result.json`, `pipeline.md` | Operations | Release review and promotion gates |
| `stretch6/agents.json`, `handoff_packets/` | Platform-managed agents | Hosted workflow delegation |
| `stretch7/invocations.json`, `claim_reviews/`, `skills_transcript.md` | Invocations/Skills | Structured review and tool-use inspection |

Reopen the producing notebook and rerun required checkpoint cells to regenerate
missing evidence. Do not commit generated outputs, credentials or executed notebooks.
