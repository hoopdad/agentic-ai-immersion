# Lab 3: Typed tools and local testing

Build and test the Healthcare Marketplace concierge over the Responses protocol.
This folder contains only Lab 3; it does not deploy a hosted version.

## Prerequisites

Complete [Lab 2](../lab02/README.md), including verified model configuration.
The administrator must confirm hosted-agent enablement and identity access for
the learner project before the deployment path.

Open [Lab 3](lab03_walkthrough.ipynb) with a fresh Python 3.14 dev-container kernel.
Local model calls use Azure and incur charges.

## Product to inspect and edit

The shared [agent product](../../shared/hosted-agent-basics/hosted/main.py)
defines `Agent`, `FoundryChatClient`, typed `@tool` functions and
`ResponsesHostServer`. Edit this original file, not a generated vendored copy.
Lab 4 deploys the same tested product.

## Notebook path and YOUR TURN

1. Bind Lab 2's project/model evidence to this kernel and inspect tools/policy.
2. Prepare the flat pinned package and run local S1/S2 conversations.
3. Add and register `get_sponsor` in the shared product. Step 3.6 must report
   Northwind and the $3,600 annual HRA for P-1001, with safety checks.
4. Tighten the advisor-refusal instruction to include the enrollment window.
   Step 3.7 starts a fresh process and requires AEP in the S1 answer.
5. Publish local acceptance in Step 3.8.

Notebook lifecycle controls own readiness, port 8088, logs and cleanup.
Inspect the identified process/log on failure; do not stop unrelated processes.
Typed tools provide facts, while shared policy prohibits recommendations and
unnecessary participant data. Sample PASS is not compliance certification.

## Checkpoint

`../artifacts/lab2/part_a.json` binds local acceptance, transcript evidence and
tested product source. `hosted.json` is local metadata, not deployed readiness.
Source changes require fresh acceptance before [Lab 4](../lab04/README.md).

## Learning contract and recovery

- **Required:** Lab 2's accepted `project.json`/`part_b.json` and verified identity/model scope.
- **Recommended route:** core Labs 1-10 in order; next Lab 4.
- **Primary delta / lineage:** first typed-tools concierge; local acceptance, not deployment.
- **Acceptance:** sponsor facts and enrollment-window handoff edits are required exercises,
  alongside refusal of recommendations. Lab 4 continues this product. Lab 5 extends
  only the accepted sponsor implementation and enrollment policy into its knowledge product.
- **Recovery:** restore Lab 2 for configuration errors; rerun Steps 3.4-3.8 after edits.
  Stop only the process owned by this notebook and review attendee cloud cleanup.

## SDK/documentation baseline

Root lock pins: `agent-framework==1.9.0`, `azure-ai-projects==2.2.0`,
`agent-framework-foundry-hosting==1.0.0a260618`, `azure-identity==1.25.3`,
`openai==2.44.0`. Hosted requirements remain matching minimal subsets; no upgrade is required.
Current [hosted-agent concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
and [project client reference](https://learn.microsoft.com/en-us/python/api/azure-ai-projects/azure.ai.projects.aiprojectclient)
define the notebook/product boundary. Cloud acceptance remains an approved live rehearsal.

## Authoring

Edit `lab03_tools_local.py` and regenerate `lab03_walkthrough.ipynb`.
The original combined driver remains in `shared/hosted-agent-basics`.
