# Stretch 6: Invocations protocol, Foundry Toolbox and Skills

| | |
|---|---|
| Goal | Host a deterministic denied-claims reviewer on Invocations, then add bundled Skills and an optional Foundry Toolbox to a Responses agent. |
| Time | 45-60 min; complete Invocations first |
| Produces | `artifacts/stretch6/invocations.json`, `artifacts/stretch6/claim_reviews/CLM-*.json`, `artifacts/stretch6/skills_transcript.md` |
| Cloud required | No for `--offline`; yes for model-backed local demos and deployment |

The workstation and Foundry run the same `main.py` files. Before either package is deployed, its `prepare.py`
vendors and hashes every imported `common/`, `data/`, and (for Responses) `skills/` file. The package review fails
on stale copies, missing runtime files, credentials, `.azure`, caches, or virtual environments.

## Setup

From the workshop root in dev-container Bash:

```bash
# Reopen the repository in its dev container; dependencies are preinstalled.
python --version  # Python 3.14
# Dependencies were installed by the repository dev-container bootstrap.
```

In VS Code, select `/usr/local/bin/python` as the notebook kernel. Launch the notebook from its own folder:

```bash
cd ./labs/stretch6-invocations-toolbox-skills
python -m jupyter lab ./stretch6_walkthrough.ipynb
```

Or run the driver from `labs`:

```bash
cd ./labs
python ./stretch6-invocations-toolbox-skills/stretch6_invocations.py --offline
```

## Protocol contract

| Dimension | Invocations | Responses |
|---|---|---|
| Route | `POST /invocations` | `POST /responses` |
| Body | `{"message": "{\"claim_ids\":[\"CLM-9003\"]}"}` | `{"input": "...", "stream": false}` |
| Local response | Plain response text containing `ClaimReviewBatch` JSON | OpenAI Responses envelope |
| State | One request with an SDK session context; no learner-managed chat history | Multi-turn response/session flow |
| Best use | Batch jobs, pipelines, nightly reviews | Participant conversations and research |

The Invocations route and local response behavior are taken from the installed
`agent_framework_foundry_hosting.InvocationsHostServer` and `azure.ai.agentserver` code in this workshop
environment. `MARKETPLACE_INVOCATIONS_PATH` exists only for an explicit reverse-proxy override and must be an
absolute URL path.

## Run the deterministic path

```bash
cd ./labs
python ./stretch6-invocations-toolbox-skills/stretch6_invocations.py --offline
python ./stretch6-invocations-toolbox-skills/hosted-invocations/test_local.py --offline
```

The smoke test fails unless every deterministic field matches `claims_review.py` exactly, CLM-9003 carries the
complete KB-ACC-001 accepted-document list, and safety checks pass. It returns a nonzero exit code on malformed or
empty response envelopes.

For the model-backed local Invocations demo, configure the workshop `.env`, omit `--offline`, and inspect
`artifacts/stretch6/hosted-invocations_local.log`. The driver always stops its child server.

## Deterministic package preparation

Each hosted package has the same lifecycle:

```bash
cd ./labs/stretch6-invocations-toolbox-skills/hosted-invocations
python ./prepare.py
python ./prepare.py --check
python ./prepare.py --clean
```

Use `hosted-responses-skills` instead of `hosted-invocations` for the second package. Vendored directories and
`.vendored.json` are generated package inputs; regenerate them before deployment and do not hand-edit them.
`.agentignore` excludes local state and deployment tooling without excluding `common/`, `data/`, or `skills/`.

## YOUR TURN: nightly denials

Change `BATCH` in `stretch6_invocations.py` to `nightly_denial_ids()`. Run the notebook cell immediately below
the heading. `nightly_denials_acceptance_gate()` discovers every denied claim through
`marketplace_data.get_hra_account(...)`, invokes exactly that set, validates deterministic facts, and cleans up its
server in `finally`. In a scheduled environment this request shape fits a Foundry Routine (preview) or pipeline.

## Skills

Run the bundled HRA skill demo:

```bash
cd ./labs
python ./stretch6-invocations-toolbox-skills/stretch6_invocations.py --skills-demo
```

The startup log lists bundled skill names. `read_skill` logs the selected skill and governed source document.

## YOUR TURN: a second skill

Create `skills/debit-card-faq/SKILL.md` from `data/knowledge/debit-card-faq.md`. Set frontmatter
`name: debit-card-faq` and `source_doc: KB-ACC-002`; include declined, blocked, and lost-card procedures plus the
full-card-number safety rule. Run the notebook gate below the heading.

`second_skill_acceptance_gate()` validates the source, rebuilds the package, asks the pharmacy-decline question,
requires a `[KB-ACC-002]` citation and a `read_skill name=debit-card-faq` log entry, and always stops its server.

## Optional Foundry Toolbox preview

The Skills agent runs without Toolbox when both settings are absent. To enable it, set both:

- `TOOLBOX_NAME`
- `TOOLBOX_MCP_URL` as an `https://` MCP endpoint

`TOOLBOX_SCOPE` defaults to `https://ai.azure.com/.default`. Partial configuration fails at startup. Token
acquisition failures explicitly identify local `az login` or hosted managed-identity/RBAC as the next check;
401/403 responses remain errors rather than silently disabling Toolbox. Only public information may go to
`web_search`; participant data never may.

## Print deployment commands

Set `PROJECT_RESOURCE_ID` in the workshop `.env`, then:

```bash
cd ./labs
python ./stretch6-invocations-toolbox-skills/stretch6_invocations.py --deploy
```

This is print-only. It emits separate absolute, quoted Bash blocks for Invocations and Responses. Each block
runs preparation and package review, configures `azd`, initializes the correct protocol, checks the command exit status
after every external command, and stops on failure. Review and paste each block in the intended authenticated
terminal.

## Remaining cloud checks

After deployment, wait for both versions to become active and invoke each through the project. For Toolbox, verify
the preview endpoint, token audience, managed-identity access, and `_ping_available` compatibility against the
provisioned service. These checks cannot be completed by the offline lab validation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Invocations 404 | Confirm the installed host is running and use `/invocations`; set `MARKETPLACE_INVOCATIONS_PATH` only for a known proxy prefix. |
| Response cannot be parsed | Print the HTTP body. The test accepts direct `ClaimReviewBatch` JSON and known text wrappers, but rejects unknown or empty envelopes. |
| Package review says stale | Run `python ./prepare.py` again; do not edit vendored copies. |
| Skills are `none` | Re-run the Responses package preparation and check `SKILL_NAMES`. |
| Toolbox configuration error | Set both `TOOLBOX_NAME` and `TOOLBOX_MCP_URL`, or remove both. |
| Toolbox authentication error or 401/403 | Verify `az login` locally, `TOOLBOX_SCOPE`, hosted managed identity, Toolbox RBAC, and propagation. |
| Region/model preview error | Complete the Invocations half and skip Toolbox; Toolbox and Foundry Skills are preview features. |
