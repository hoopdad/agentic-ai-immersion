# Lab 3: Typed tools and local testing

Build and test the Healthcare Marketplace concierge over the Responses protocol.
This folder contains only Lab 3; it does not deploy a hosted version.

## Prerequisites

Complete [Lab 2](../lab2/README.md), including verified model configuration.
The administrator must confirm hosted-agent enablement and identity access for
the learner project before the deployment path.

Open [Lab 3](lab3_walkthrough.ipynb) with a fresh Python 3.14 dev-container kernel.
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
Source changes require fresh acceptance before [Lab 4](../lab4/README.md).

## Authoring

Edit `lab3_tools_local.py` and regenerate `lab3_walkthrough.ipynb`.
The original combined driver remains in `shared/hosted-agent-basics`.
