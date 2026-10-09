# Use Case: Healthcare Marketplace Concierge

The labs explore this one use case through related, explicitly separate products.
The format is the Bring-Your-Own-Use-Case spec, reusable for your own scenario.

## Use Case Summary

A retiree or pre-Medicare individual covered by a plan sponsor contacts Healthcare Marketplace by chat or phone. A small
team of agents helps them understand the sponsor's HRA subsidy, compare the individual plans sold in their
county, know their enrollment window, and handle account tasks (balance, claim status, denial reasons, debit
card, premium auto-reimbursement). Whenever a recommendation, an enrollment or a judgment call is needed, the
agents hand the case to a licensed benefit advisor with a structured packet, and the human approves it.
Agents summarize, retrieve, compare and route; humans decide.

## Input

- A participant chat message or a call transcript, plus the stated participant_id and ZIP.
- Systems of record behind the 8 shared tools in `common/marketplace_data.py`: participants, sponsors, plans, HRA
  accounts and claims (`data/*.json`).
- The knowledge base, `data/knowledge/*.md`, in three bounded contexts: marketplace, accounts, universal.
- The workshop date (`MARKETPLACE_TODAY`, default 2026-10-06) so enrollment answers are deterministic.

## Agent Steps

1. `healthcare-marketplace-concierge` verifies identity (participant_id + ZIP), classifies the intent by line of business
   (marketplace, accounts, both) and answers universal questions such as the enrollment window.
2. `marketplace-guide` searches and compares plans in the county and explains plan types and enrollment
   periods from the marketplace context, citing document ids.
3. `accounts-assistant` reads the HRA account and claims, explains denial reasons and accepted documents
   from the accounts context, and can flag a claim for resubmission follow-up.
4. `compliance-reviewer` checks every draft (no recommendation, no PHI, citations present) and asks for one
   revision if needed.
5. `advisor-handoff` writes the packet as strict JSON when a trigger fires (recommendation, enrollment or
   judgment requested). A licensed benefit advisor approves, revises or declines it.

## Output

- A participant-facing reply: plain, neutral, with citations like [KB-ACC-001].
- When triggered, a handoff packet: participant_id, line_of_business, reason_for_handoff, summary,
  options_discussed, open_questions, compliance_flags, knowledge_refs, created_at.
- Traces, a PII-redacted tool audit log, eval results over `golden_questions.jsonl`.

## Behavior Rules

MUST:
- Verify identity with participant_id and ZIP before sharing any account, claim or plan detail.
- Present plan comparisons as neutral facts, side by side, without ranking.
- Cite the knowledge document id after any statement drawn from it; say so when the knowledge base is silent.
- Offer the advisor handoff and produce the packet whenever a recommendation, enrollment or judgment is asked.
- Redact SSN, MBI, phone, email and card numbers from anything stored.
- Use short sentences and plain language.

MUST NOT:
- Recommend a specific plan, say which plan to choose, rank plans as "best", or enroll anyone.
- Ask for, repeat or store a full SSN, Medicare Beneficiary Identifier, card number or bank details.
- Give medical advice, guarantee coverage or cost, or predict annual spend.
- Answer from memory when a tool or knowledge document exists for the question.
- Leave the Healthcare Marketplace domain.

## Domain Context and Personas

Healthcare Marketplace is the organization's Individual Marketplace: individual health insurance for retirees and others not on a
group plan, with licensed benefit advisors, online decision support, HRA administration and 80+ carriers,
delivered through call centers. Two lines of business share the participant: Marketplace (Medicare
Advantage, Medigap, Part D, ACA) and Accounts (HRA, claims, payments, debit cards). Some participants are
accounts only, some broker only, some both.

Personas: the participant (a sponsor's retiree with a concrete worry: a drug cost, a denied claim, a 65th
birthday); the licensed benefit advisor (the only person who may recommend or enroll); the human call-center
agent (verifies, explains, routes); compliance and privacy (own the rules, read the eval reports); the
engineer building it.

The roles below describe the specialist triage design taught in hosted Labs 7-8,
not a requirement to instantiate every role in every lab. Labs 1-2 provision
project/models; Labs 3-6 build the concierge; Labs 9-10 measure and gate its
pinned knowledge-enabled version. Lab 11 is a short optional single-prompt
comparison after Lab 4, with no downstream consumers. MAF orchestration does
not depend on Prompt Agents.

| Role | Name in code | LOB | Tools | Knowledge context |
|---|---|---|---|---|
| Front door and router | `healthcare-marketplace-concierge` | universal | get_participant, get_enrollment_window | universal |
| Plan education and comparison | `marketplace-guide` | marketplace | search_plans, compare_plans, get_enrollment_window | marketplace |
| Reimbursement account help | `accounts-assistant` | accounts | get_hra_account, get_claim_status, list_eligible_expenses | accounts |
| Policy check on drafts | `compliance-reviewer` | universal | none (reviews text) | universal |
| Case packet for the human | `advisor-handoff` | universal | none (writes JSON) | universal |

## Product lineage and optional boundaries

The guided route is core Labs 1-10 in order, then selected extensions.
Labs 3-4 locally test and deploy the same typed-tool Responses concierge.
Labs 5-6 extend accepted tools/policy with retrieval and declared history.
Labs 7-8 branch into a distinct hosted triage service with parallel specialists
and explicit simulated advisor decisions. Lab 8 recovers file-backed pending
cases after a local restart; this does not establish cross-replica, version-roll
or cross-service recovery, or production advisor authorization.

Lab 12 requires **both Labs 8 and 9** and introduces the network/identity
boundary: an isolated concierge extension candidate calls the pinned triage
service. It reuses that service's graph, not a prompt ensemble or second graph.
The caller may relay a pending status but never manufacture or automatically
forward an advisor decision. Bound waits, surface remote errors and retain
case/session correlation; do not blindly retry state-changing requests.
Preserve the exact core concierge evaluation/release version from Labs 9-10;
extension changes need fresh evaluation before a release claim.

Lab 13 requires Lab 4 and branches into a stateless structured Invocations
batch product. Lab 14 requires Lab 13 and preserves its accepted batch evidence
while introducing a distinct Responses Skills service, with optional preview
Toolbox. It does not turn Invocations into a session service. Dependency branches
are choices, not parallel runtime instructions: local products share port 8088,
editable source and Azure quota.

## Scenarios

- S1 "AEP shopper": P-1001 Evelyn Marsh, 68, Salt Lake County, on MA-CONTOSO-HMO-01, wants a lower drug cost
  for atorvastatin and to keep her cardiologist. Expected: comparison table (two MA PPOs list atorvastatin as
  Tier 1), enrollment window (AEP), no recommendation, advisor handoff offered.
- S2 "Denied claim": P-1003 Harold Bing, 72, Utah County, CLM-9003 denied `missing_proof_of_payment`.
  Expected: denial explained from [KB-ACC-001], accepted proof listed, offer to flag for resubmission, no
  PHI beyond what is needed.
- S3 "Pre-Medicare, both LOBs": P-1005 Rosa Delgado, 63, Davis County, sponsor HRA, needs ACA plan education,
  her HRA balance and an answer about turning 65 next year. Expected: both specialists, ACA open enrollment
  and the Medicare IEP explained, packet created because she asked "which one should I pick".

## Preferences

- Tone: plain, warm, no filler. Short sentences.
- Every agent's instructions end with `guardrails.COMPLIANCE_INSTRUCTIONS`, verbatim.
- Human-in-the-loop design: packets wait for an explicit simulated advisor decision;
  production authorization and real systems-of-record approvals are not established by the exercise.
- Inspect traces, redacted audit logs and evaluation evidence; a portal visibility
  claim requires a current Azure observation, not an offline PASS.
- Entra-only authentication, no keys, no hardcoded endpoints.

## Synthetic Data Requirements

See `data/README.md`: 6 participants (4 Medicare-eligible, 2 pre-Medicare), 2 sponsors, 20 plan-year-2027
plans across four Utah counties, 6 HRA accounts with paid, pending and denied claims, 9 knowledge docs in
three contexts, 18 golden questions, 3 call transcripts. All fictional; notebook fact checks and
internal offline validation assert the scenario facts.
Offline validation does not establish live hosted deployment, Azure telemetry
ingestion, preview availability, distributed recovery or regulatory compliance.
Label unrun live checks and optional preview skips explicitly.

## Why this use case for the organization

It is the customer's actual front door. Both lines of business the attendees represent are call-center based
and share one participant, one telephony stack and one advisor workforce, and the ask was for agents that
talk to each other across both LOBs, set up "the standard way" in Foundry: observable and governed. The
concierge exercises all of it: cross-LOB routing, systems of record behind tools, a knowledge base split the
way the customer stores its documentation, and a regulatory landscape (PII and PHI everywhere, licensing
rules, CMS marketing rules, HIPAA) that makes human-in-the-loop the operating model, not a demo feature. If
the agents behave here, the pattern transfers to the rest of Benefits Delivery and Outsourcing.
