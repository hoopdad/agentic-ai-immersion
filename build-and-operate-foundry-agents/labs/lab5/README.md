# Lab 5: Governed knowledge and retrieval

Create attendee-scoped Search/Foundry IQ knowledge and verify cited answers.
This folder contains only Lab 5; session continuity is a later lab.

## Prerequisites

Complete [Lab 4](../lab4/README.md). The administrator supplies existing Azure AI
Search with semantic ranker, Foundry IQ support, identity permissions and the
approved network path. Use Lab 2's 3072-dimensional embedding deployment.

Open [Lab 5](lab5_walkthrough.ipynb) in a fresh Python 3.14 dev-container kernel.
Knowledge writes and embedding/retrieval calls are explicit paid cloud actions.

## Product and notebook path

Inspect the shared [knowledge builder](../../shared/hosted-knowledge-sessions/knowledge_base.py),
[hosted product](../../shared/hosted-knowledge-sessions/hosted/main.py) and reviewed
documents under [`data/knowledge`](../../data/knowledge/).

1. Validate Lab 4's scoped deployment evidence.
2. Review indexes, sources and project-connection creation before Step 5.3.
3. Build knowledge and prepare the shared product package.
4. Require a governed premium-claim citation in a fresh knowledge-only conversation.
5. Run **YOUR TURN: unavailable knowledge** in a separate no-retrieval process;
   require honest boundary behavior instead of an invented answer.
6. Publish current retrieval acceptance in Step 5.6.

Creation needs Search service/data-write and project-connection permissions.
Retrieval uses Entra authentication; local and deployed identities each need
effective access. Model identity and deployment alias are distinct.
A citation is not proof of freshness or factual completeness.

## Checkpoint

`../artifacts/lab3/part_a.json` fingerprints `knowledge.json` and binds acceptance
to the current project, suffix, models and tested source. `hosted.json` contains
the prepared product metadata.

[Lab 6](../lab6/README.md) reuses this knowledge without rebuilding Search.
Changed source/evidence requires fresh Lab 5 acceptance.

## Authoring

Edit `lab5_knowledge_retrieval.py` and regenerate `lab5_walkthrough.ipynb`.
