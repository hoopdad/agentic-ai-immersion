# Lab 2: Hosted agent basics

| | |
|---|---|
| Goal | Build the Healthcare Marketplace concierge, test Responses locally, deploy the same product package and invoke its active hosted version |
| Time | 60 min: teach 10, demo 10, do 35, checkpoint 5 |
| Starts from | `artifacts/lab1/project.json` and Lab 1's verified project/model configuration persisted to the root `.env` |
| Notebooks | [Lab 2A](lab2a_walkthrough.ipynb): tools/local agent; [Lab 2B](lab2b_walkthrough.ipynb): deployment/invocation |
| Produces | `artifacts/lab2/part_a.json`, `part_b.json`, `hosted.json`, `transcripts.md`, `hosted_local.log` |
| Learn alignment | Agent Framework, custom tools, Foundry agent development |

Open 2A then 2B with the dev container's `/usr/local/bin/python` kernel.
Each half can start in a fresh kernel. **2A** manages local processes on port 8088
and the tool/instruction exercises only; it never deploys. **2B** validates the
scope-bound local checkpoint, transcript fingerprint and tested source, imports
the original driver's definitions without replaying demos, then explicitly deploys
and invokes the active version.
`hosted/main.py` is the deployable product, not another learner entry point.

## What you'll learn

- Build an `Agent` on `FoundryChatClient` with three typed tools and shared compliance instructions.
- Serve the Responses protocol locally and call the hosted agent-specific OpenAI endpoint.
- Explain deployment versus invocation RBAC, readiness, logs and immutable versions.
- Change a tool or instruction, verify its acceptance evidence and ship a new version.

## Technical features taught

| Feature | Object / product location | Why it matters |
|---|---|---|
| Entra model access | `FoundryChatClient`, `DefaultAzureCredential` in `hosted/main.py` | Developer identity locally, dedicated agent identity in Azure; no keys |
| Typed read-only tools | `Agent`, `@tool`, `Annotated` parameters | Participant, window and HRA facts come from systems of record |
| Shared policy | `guardrails.COMPLIANCE_INSTRUCTIONS` | Licensing and data-minimization boundaries travel with every agent |
| Responses hosting | `ResponsesHostServer` | Same Python product runs locally and in Foundry |
| Model transcript policy | `default_options={"store": False}` | Agent-owned history is introduced in Lab 3 |
| Flat pinned package | `hosted/prepare.py`, `requirements.txt` | Remote build must receive all imported code/data without local credentials |
| Notebook process lifecycle | `lab2a_tools_local.py` uses internal `lab2_hosted_basics.py` helpers | Start, test, inspect logs and stop through notebook cells |
| Source deployment and version invocation | `azd` managed by notebook actions; named OpenAI client | Foundry builds, versions and scales the product |

## Teach (10 min)

A hosted agent is your code run by Foundry. A flat package is uploaded, pinned
dependencies are restored, an identity and protocol endpoint are provisioned,
and a version is recorded. No learner-built Docker image is required.

Responses fits conversations; Invocations fits a structured request/response
(Stretch 7). Local credentials resolve to your signed-in identity; deployed
credentials resolve to the agent identity. Both need an approved network path.
Foundry Project Manager deploys; Foundry Agent Consumer or Foundry User invokes.

Versions are immutable, including failed versions retained for audit. Wait for
`active` before invocation. Model right-sizing means qualifying the least-cost
configuration against the same gate; this lab uses one configured deployment
and does not measure tier savings.

Typed tools constrain fact access. Shared policy forbids plan recommendations
and unnecessary sensitive data. Agents retrieve and explain; licensed advisors
retain judgment. Passing sample checks is not production compliance certification.

## Demo (10 min)

1. Run preparation and local conversation cells. Inspect S1 enrollment facts and
   its refusal to pick a plan, then S2 account facts.
2. Open `artifacts/lab2/hosted_local.log` and identify model, tools and readiness.
3. Run the notebook deployment action only after local checks pass. Inspect the
   active version and logs in Foundry.
4. Enter the inspected active version in the notebook's `DEPLOYED_VERSION` input
   and run **Test the deployed version**.

## Do (35 min)

1. Run local S1/S2 cells and inspect `transcripts.md`; require the advisor offer
   without a named preferred plan.
2. Use notebook-managed local requests for P-1005 to inspect the ACA enrollment window.
3. **YOUR TURN: add `get_sponsor`.** Edit `hosted/main.py` using the other typed
   tools as the pattern and register it. Restart through the notebook. The gate
   requires Northwind and the $3,600 annual HRA for P-1001, plus safety checks.
4. In **2A**, **YOUR TURN: tighten an instruction.** Require the enrollment window
   in the advisor offer, rerun local checks and publish the local checkpoint.
5. In **2B**, deploy, wait for `active`, record the real version and invoke the
   deployed endpoint. Stop if deployment fails.
6. Compare its evidence with
   the local transcript.

## Checkpoint (5 min)

Share the S1 refusal/advisor answer and the `deployed` block of
`artifacts/lab2/hosted.json`. Lab 3 consumes this checkpoint. If a cloud build is
still queued, distinguish local acceptance from deployed readiness.
`part_a.json` certifies local acceptance only; `part_b.json` records the explicit
active-version inference pass. Keep the original `hosted.json` for Lab 3A.
If the product source changes between halves, rerun 2A acceptance rather than
deploying untested code. Adjacent paired Python sources are authoring inputs,
not terminal learner alternatives.
Acceptance/deployment reruns invalidate prior same-part success before attempting
the operation; rerunning 2A also removes 2B's marker. A failed rerun cannot publish
old success values from the current kernel.
The import/setup cell clears markers immediately, before validating predecessors,
and resets cached acceptance flags; it does not remove cloud resources.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Missing project/model configuration | Rerun Lab 1's verification/persistence cells, then restart this kernel |
| Missing `common` or stale package | Rerun notebook package preparation after product/shared-code edits |
| 401 or 403 | Check notebook authentication, subscription, tenant and separate deploy/invoke roles; allow propagation |
| Approved-private-endpoint error | Use the administrator-approved network path; extra RBAC does not bypass isolation |
| Failed version / dependency resolution | Inspect version error and package review; retain the flat layout and checked-in component pins |
| `424 session_not_ready` | Inspect version/session logs for readiness or startup failure before redeploying |
| Long wait followed by storage failure | Separate model 429 retries from Foundry response storage; the notebook's single-turn `store=False` call isolates inference |
| Model not found | Verify Lab 1's deployment name against the project |
| Port already occupied | Stop the identified notebook-managed local process before rerunning readiness |

Model-side `store=False` and Foundry response persistence are separate. A
single-turn inference pass does not prove multi-turn `previous_response_id`
storage works. Remote calls disable automatic client retries and use bounded
timeouts; server-side model retries can still occur.

## Follow-up and references

Add streaming in the notebook request exercise and inspect server-sent events.
Internal cell-source authoring and helper regression tests are not learner run paths.

- [Azure agent learning path](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/)
- [Hosted agents concepts](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents)
