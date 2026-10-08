# %% [markdown]
# # Labs 11-12: Foundry prompt agents with Microsoft Agent Framework workflows
#
# **Technology focus.** This lab uses Microsoft Foundry (`PromptAgentDefinition`; versioned prompt agents)
# and Microsoft Agent Framework (`FoundryAgent`; `WorkflowBuilder`; async hosted `@tool`).
#
# Internal helpers for the numbered notebooks. Lab 11 publishes prompt definitions; Lab 12 connects to
# those pinned versions and runs the Python graph in `triage_workflow.py`. There is no YAML workflow,
# workflow-agent publication, or additional hosted service.
#
# **How to run.** Execute this notebook's cells in order using the numbered Lab 11 and Lab 12 notebooks.
#
# ## Before the first run
#
# Complete Lab 6 in the Python 3.14 dev container and retain its knowledge and hosted artifacts.
#
# This cell loads shared helpers and the attendee-scoped prompt-agent definitions.
# %% Step S6.1 - Imports and environment
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/shared/prompt-agents-and-workflows/stretch6_prompt_agents.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/shared/prompt-agents-and-workflows/stretch6_prompt_agents.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs", SOURCE_PATH.parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, guardrails, marketplace_data, resource_names
import lab_helpers as helpers
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from triage_workflow import PACKET_FIELDS, SOURCE_SHA256, run_case, validate_packet

ENV = foundry_env.load_env()
MODEL = helpers.pick_model(ENV)
LAB = "stretch6"
LABS_DIR = ROOT / "labs"
HERE = SOURCE_PATH.parent
CONCIERGE = resource_names.name(resource_names.PROMPT_CONCIERGE, ENV)
TRIAGE = resource_names.name(resource_names.PROMPT_TRIAGE, ENV)
MARKETPLACE = resource_names.name(resource_names.PROMPT_MARKETPLACE, ENV)
ACCOUNTS = resource_names.name(resource_names.PROMPT_ACCOUNTS, ENV)
COMPLIANCE = resource_names.name(resource_names.PROMPT_COMPLIANCE, ENV)
HANDOFF = resource_names.name(resource_names.PROMPT_HANDOFF, ENV)
EXPECTED_S1_ACTIONS = ("triage", "marketplace", "compliance", "handoff")


def function_tool_is_registered(source: str, tool_name: str) -> bool:
    """Accept a FUNCTION_TOOLS list item or an explicit append."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "FUNCTION_TOOLS" for target in targets) \
                    and isinstance(node.value, (ast.List, ast.Tuple)) \
                    and any(isinstance(item, ast.Name) and item.id == tool_name for item in node.value.elts):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "FUNCTION_TOOLS" \
                and node.func.attr == "append" and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Name) and node.args[0].id == tool_name:
            return True
    return False


# %% [markdown]
# This cell defines bounded prompts, existing function-tool contracts and server-side knowledge access.
# %% Step S6.2 - Define prompt agents
TRIAGE_MODE = """
TRIAGE MODE
- A message starting with "TRIAGE CASE" comes from the MAF workflow, not a participant. The caller has verified
  the included system-of-record facts. Use them first; call function tools only when a fact is missing.
- Write for the participant, second person.
"""
INSTRUCTIONS = {
    CONCIERGE: """You are "Healthcare Marketplace Concierge", the front door for Healthcare Marketplace, the organization's Individual Marketplace.
- Confirm identity with participant_id and ZIP code only, then look the participant up with get_participant.
- Enrollment timing: get_enrollment_window (window name, dates, what it allows). Account basics: get_hra_account.
- Plan comparisons are done by a Marketplace specialist; you have no plan tool, say so and offer to connect them.
- Recommendation, enrollment or judgment call: offer a licensed benefit advisor handoff.
- Call a tool before stating any fact. Under 120 words. End with one next step.

""",
    TRIAGE: """You are "Healthcare Marketplace Concierge" in triage mode. You receive one TRIAGE CASE (participant words + verified facts).
You have no tools and never invent facts. Reply in exactly this shape:
ROUTE: marketplace | accounts | both
INTENT: one sentence.
PARTICIPANT_GOALS:
- one per line
NEEDS_ADVISOR: yes | no, followed by the reason
CASE:
(copy the TRIAGE CASE below this line unchanged)
Routing: marketplace = plans, premiums, formularies, networks, enrollment periods, ACA, turning 65; accounts = HRA,
claims, denials, proof of payment, debit card, auto-reimbursement. Route from participant_message only: supporting
facts do not create an intent. Use both only when the participant explicitly asks about both areas; never use both
merely because account or plan facts are present. When unsure, choose the area of the participant's stated question.
If routing_hint is present, copy it exactly into ROUTE.
Never answer the participant yourself.

""",
    MARKETPLACE: """You are "Marketplace Guide" for Healthcare Marketplace. You educate about Medicare Advantage, Medigap, Part D and ACA
plans and compare them neutrally.
- knowledge_base_retrieve (server side): call it FIRST for how plans, enrollment periods, subsidies or comparisons
  work; cite the doc id, for example [KB-MKT-002].
- search_plans / compare_plans / get_enrollment_window when facts are missing from the case.
- Comparisons: compact table (plan, carrier, type, premium, deductible, max out of pocket, stars, network, drug
  coverage, named drug tier), then neutral trade-offs. Never rank, never "best". Doctor networks: the participant
  must confirm with the carrier or an advisor.
- In TRIAGE MODE reply exactly NO_MARKETPLACE_QUESTION when the case has no marketplace part.
""" + TRIAGE_MODE,
    ACCOUNTS: """You are "Accounts Assistant" for Healthcare Marketplace: HRA balance, claim status, denial reasons, accepted proof of
payment, debit card, premium auto-reimbursement.
- knowledge_base_retrieve FIRST for rules and documents; cite [KB-ACC-001] style doc ids.
- get_hra_account, get_claim_status, list_eligible_expenses when facts are missing from the case.
- Denied claim: reason in plain words, the exact document that fixes it, offer to flag for resubmission.
- Quote numbers from tools or case facts only. Card: last 4 digits at most. Plan choice questions go to the
  Marketplace specialist or a licensed advisor. Under 150 words, one next step.
- In TRIAGE MODE reply exactly NO_ACCOUNTS_QUESTION when the case has no accounts part.
""" + TRIAGE_MODE,
    COMPLIANCE: """You are "Compliance Reviewer" for Healthcare Marketplace. You review drafts (MARKETPLACE DRAFT, ACCOUNTS DRAFT) in a
COMPLIANCE REVIEW REQUEST against the COMPLIANCE RULES and the case facts. Ignore drafts that read NO_*_QUESTION.
Check: rule 1 recommendation or ranking; rule 2 missing advisor handoff when asked to choose or enroll; rule 3 PII;
rules 4 and 5 uncited or unsupported facts; rule 6 medical advice, guarantees, "doctor is in network".
Reply exactly:
COMPLIANCE REVIEW
verdict: pass | revise
flags:
- rule <n>: <what and where>   (or "- none")
revised_reply:
<one merged participant-facing reply with every flagged sentence fixed, citations kept>

""",
    HANDOFF: """You are "Advisor Handoff" for Healthcare Marketplace. From a BUILD HANDOFF PACKET message (triage summary, case facts,
drafts, COMPLIANCE REVIEW) write ONE JSON object and nothing else, no fences. Fields, all required:
case_id, participant_id, lob (marketplace|accounts|both), summary (2-4 sentences), participant_goals [str],
facts_gathered [{"fact","source"}] (source = tool name, KB doc id or "participant statement"), options_discussed [str]
(neutral, never a preference), open_questions [str], recommended_next_step_for_advisor (a process step, never a
plan choice), compliance_flags [str] (copy from the review, [] when none), created_at (ISO 8601 UTC).
Set lob from the triage ROUTE, not from supporting facts that the participant did not ask about.
Never include a date of birth, SSN, Medicare number or card number. Use only facts present in the input.

""",
}
SPECS = {
    CONCIERGE: (["get_participant", "get_enrollment_window", "get_hra_account"], False),
    TRIAGE: ([], False),
    MARKETPLACE: (["search_plans", "compare_plans", "get_enrollment_window"], True),
    ACCOUNTS: (["get_hra_account", "get_claim_status", "list_eligible_expenses"], True),
    COMPLIANCE: ([], False),
    HANDOFF: ([], False),
}


def knowledge_tool(knowledge: dict) -> MCPTool:
    connection_id = (knowledge.get("connection") or {}).get("connection_id")
    if not knowledge.get("mcp_endpoint") or not connection_id:
        raise ValueError("Complete Lab 5's knowledge build; knowledge.json needs mcp_endpoint and connection.")
    return MCPTool(
        server_label="healthcare-marketplace-kb", server_url=knowledge["mcp_endpoint"],
        require_approval="never", project_connection_id=connection_id,
    )


def create_prompt_version(project, name: str, instructions: str, knowledge: dict | None = None):
    resource_names.suffix(ENV, required=True)
    tool_names, uses_kb = SPECS[name]
    if not instructions.endswith(guardrails.COMPLIANCE_INSTRUCTIONS):
        instructions += guardrails.COMPLIANCE_INSTRUCTIONS
    tools = helpers.function_tools(tool_names)
    if uses_kb:
        knowledge = knowledge or helpers.require_artifact("lab3", "knowledge.json", through=3, caller=LAB)
        tools.append(knowledge_tool(knowledge))
    return project.agents.create_version(
        agent_name=name, definition=PromptAgentDefinition(model=MODEL, instructions=instructions, tools=tools),
    )


def publish_prompt_agents(project=None, overrides: dict[str, str] | None = None) -> dict:
    resource_names.suffix(ENV, required=True)
    knowledge = helpers.require_artifact("lab3", "knowledge.json", through=3, caller=LAB)
    project = project or foundry_env.get_project_client()
    agents = {}
    for name, (tool_names, uses_kb) in SPECS.items():
        agent = create_prompt_version(project, name, (overrides or {}).get(name) or INSTRUCTIONS[name], knowledge)
        agents[name] = {"agent_version": agent.version, "agent_id": agent.id, "function_tools": tool_names, "knowledge": uses_kb}
        print(f"[stretch6] created prompt agent {name} v{agent.version}")
    return {
        "lab": LAB, "model": MODEL, "agents": agents, "knowledge_base": knowledge.get("kb_name"),
        "packet_fields": PACKET_FIELDS, "created_at": helpers.now_iso(),
    }


def prepare_workflow(prompt_info: dict) -> dict:
    """Save the existing prompt references for the local MAF graph; no Azure operations."""
    if set(prompt_info.get("agents", {})) != set(SPECS):
        raise ValueError("Complete Lab 11 before preparing the MAF workflow.")
    info = {
        **prompt_info, "runtime": "microsoft-agent-framework", "graph_sha256": SOURCE_SHA256,
        "roles": {"triage": TRIAGE, "marketplace": MARKETPLACE, "accounts": ACCOUNTS,
                  "compliance": COMPLIANCE, "handoff": HANDOFF},
    }
    foundry_env.save_artifact(helpers.artifact_path(LAB, "agents.json"), info)
    return info


def source_fingerprints() -> dict[str, str]:
    hosted = ROOT / "shared/hosted-knowledge-sessions/hosted"
    paths = [HERE / "triage_workflow.py", HERE / "hosted_tool_snippet.py",
             hosted / "main.py", hosted / "triage_workflow.py", hosted / "triage_agents.json"]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def require_hosted_concierge() -> dict:
    return helpers.require_artifact("lab3", "hosted.json", through=3, caller=LAB)


# %% [markdown]
# This cell defines the authoritative case facts and acceptance checks shared with Lab 12.
# %% Step S6.3 - Define cases and acceptance
def gather_facts(participant_id: str, claim_ids: list[str] | None = None, include_accounts: bool = False) -> dict:
    participant = dict(marketplace_data.get_participant(participant_id))
    for hidden in ("dob", "contact_preference"):
        participant.pop(hidden, None)
    prescriptions = (participant.get("preferences") or {}).get("prescriptions") or []
    drug = prescriptions[0].split()[0] if prescriptions else None
    plan_types = ("Medicare Advantage HMO", "Medicare Advantage PPO", "Part D") if participant.get("medicare_eligible") \
        else ("ACA Bronze", "ACA Silver", "ACA Gold")
    candidates = []
    for plan_type in plan_types:
        candidates += marketplace_data.search_plans(
            participant.get("county", ""), participant.get("state", "UT"), plan_type=plan_type, drug_name=drug,
        )[:2]
    ids = [plan["plan_id"] for plan in candidates]
    if participant.get("current_plan_id") and participant["current_plan_id"] not in ids:
        ids.insert(0, participant["current_plan_id"])
    keep = ["plan_id", "carrier", "plan_name", "plan_type", "premium_monthly", "deductible_annual", "max_out_of_pocket",
            "star_rating", "network_type", "drug_coverage", "formulary_tier_examples"]
    facts = {
        "participant": participant, "sponsor": marketplace_data.get_sponsor(participant.get("sponsor_id", "")),
        "enrollment_window": marketplace_data.get_enrollment_window(participant_id, today=ENV.get("MARKETPLACE_TODAY")),
        "plan_candidates": [{key: plan[key] for key in keep if key in plan}
                            for plan in marketplace_data.compare_plans(ids).get("plans", [])],
        "note": "doctor networks are NOT in the data",
    }
    if include_accounts or claim_ids:
        facts["hra_account"] = marketplace_data.get_hra_account(participant_id)
        facts["claims"] = [marketplace_data.get_claim_status(claim_id) for claim_id in (claim_ids or [])]
    return facts


def case_header(scenario: dict) -> tuple[str, str]:
    case_id = f"{scenario['id']}-{helpers.now_iso()[:10].replace('-', '')}-{scenario['participant_id']}"
    header = "\n".join([
        f"TRIAGE CASE {case_id}", f"case_id: {case_id}", f"participant_id: {scenario['participant_id']}", "channel: chat",
        f"participant_message: \"{scenario['message']}\"",
        f"routing_hint: {scenario['routing_hint']}" if scenario.get("routing_hint") else "",
        "facts (systems of record, verified by the caller):",
        json.dumps(gather_facts(scenario["participant_id"], scenario.get("claim_ids"),
                               include_accounts=scenario.get("include_accounts", False)), default=str),
    ])
    return case_id, header


def validate_action_order(actions: list[dict], expected: tuple[str, ...], forbidden: tuple[str, ...] = ()) -> list[str]:
    action_ids = [action["action_id"] for action in actions]
    problems = [] if action_ids == list(expected) else [f"Expected executor order {list(expected)}, received {action_ids}"]
    problems += [f"unexpected workflow action {action_id}" for action_id in forbidden if action_id in action_ids]
    return problems


def run_concierge_turn(openai_client, user_text: str) -> tuple[str, list[dict]]:
    conversation = openai_client.conversations.create()
    try:
        return helpers.run_turn(openai_client, CONCIERGE, conversation.id, user_text, log_prefix="[stretch6]")
    finally:
        openai_client.conversations.delete(conversation_id=conversation.id)


S1 = {
    "id": "S1", "title": "AEP shopper", "participant_id": "P-1001", "routing_hint": "marketplace",
    "message": "I am on the Contoso Advantage Choice HMO. Is there a plan with a lower cost for my atorvastatin where I could keep "
               "my cardiologist, Dr. Osei? And when am I allowed to switch?",
}


async def demo(info: dict) -> dict:
    case_id, header = case_header(S1)
    run = await run_case(info, header, ENV["FOUNDRY_PROJECT_ENDPOINT"])
    problems = validate_action_order(run["actions"], EXPECTED_S1_ACTIONS, forbidden=("accounts",))
    problems += validate_packet(run["packet"], expected={
        "case_id": case_id, "participant_id": S1["participant_id"], "lob": "marketplace",
    })
    if problems:
        raise RuntimeError("Lab 12 acceptance failed:\n- " + "\n- ".join(problems))
    foundry_env.save_artifact(helpers.artifact_path(LAB, "handoff_packets", "S1.json"), run["packet"])
    info = {**info, "last_run": {"case_id": case_id, "actions": run["actions"], "finished_at": helpers.now_iso()}}
    foundry_env.save_artifact(helpers.artifact_path(LAB, "agents.json"), info)
    return info
