# %% [markdown]
# # Stretch 5: Prompt agents and a declarative workflow (platform-managed), called from the hosted agent
#
# **An optional platform-managed alternative to the code-hosted workflow: choose ownership and lifecycle boundaries, then validate the same intended outcome.**
#
# |  | Details |
# | --- | --- |
# | Goal | Create the concierge and specialist prompt agents plus `healthcare-marketplace-triage-workflow` from `marketplace_triage_workflow.yaml`, run S1 through the workflow, and inspect how the Lab 2 hosted agent can delegate to it. |
# | Inputs | Required `labs/artifacts/lab2/knowledge.json` (knowledge-base MCP endpoint and project connection) |
# | Outputs | `labs/artifacts/stretch5/agents.json`, `workflow.yaml`, and `handoff_packets/S1.json` |
# | Time | 60 min (teach 10, demo 10, do 35, checkpoint 5); build takes about 1 minute and S1 takes 1–2 minutes |
#
# **How to run code**
#
# |  | Command |
# | --- | --- |
# | Run cell by cell | Open `stretch5_walkthrough.ipynb` (this file), or use the `# %%` cells in VS Code. |
# | Build and run S1 | `python stretch5_prompt_agents.py` |
# | Build platform resources only | `python stretch5_prompt_agents.py --build-only` |
# | Reuse existing resources for the demo | `python stretch5_prompt_agents.py --demo-only` |
# | Also run a concierge turn | `python stretch5_prompt_agents.py --concierge-turn` |
#
# **Where this runs.** This notebook runs on your workstation. Everything it creates runs inside the Foundry
# project: prompt agents (`PromptAgentDefinition`) and the workflow agent (`WorkflowAgentDefinition`, preview).
# No container is built here. The last cell shows how the **hosted** agent from Lab 2 gets a `run_triage_workflow`
# tool that calls the workflow agent with `responses.create(..., agent_reference=...)`: see `hosted_tool_snippet.py`.
#
# **Lab path and prerequisites.**
#
# - **Optional stretch:** This lab is not required for Lab 6 or for completing the four core labs.
# - **Required if you choose this stretch:** Complete Lab 2 first. If you joined late, run
#   `python ../catch_up.py --through 2` from this lab folder.
# - **From Lab 1:** Lab 1 introduced a code-hosted Responses agent and explicit source deployment. Stretch 5
#   contrasts that model with platform-managed prompt and workflow agents; it does not build another container.
# - **Optional integration:** Editing and redeploying the Lab 2 hosted agent with `hosted_tool_snippet.py` is an
#   extension after the platform workflow succeeds.
#
# **Checkpoint artifact.** `artifacts/stretch5/agents.json` (every agent name and version, the workflow agent,
# the S1 handoff packet path) and `artifacts/stretch5/handoff_packets/S1.json`.
#
# %% [markdown]
# ## Before the first run (dev-container Bash)
#
# Continue with the dev container, root `.env`, Azure sign-in, and `/usr/local/bin/python` kernel used in the core
# labs. If you have not completed that setup, follow the workshop `SETUP.md` first.
#
# ### **If this notebook is already open in VS Code**
#
# Keep using this notebook and its selected kernel. **Do not run the JupyterLab command below.**
# It starts a separate JupyterLab server and may open a browser tab; it does not connect to the notebook session
# already open in VS Code.
#
# ### Optional: open a separate JupyterLab session in a browser
#
# Run these commands in a Bash terminal—not in a Python code cell—only if you want to open this notebook
# in a separate JupyterLab session:
#
# ```bash
# cd /workspaces/agentic-ai-immersion/build-and-operate-foundry-agents/labs/stretch5-prompt-agents-and-workflows
# python -m jupyter lab stretch5_walkthrough.ipynb
# ```
#
# %% [markdown]
# Shell commands use the container filesystem. Hosted deployment remains an explicit terminal action.
#
# %% Step S5.1 - Imports and environment
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SOURCE_PATH = Path(globals().get("__file__", Path.cwd() / "stretch5_walkthrough.ipynb")).resolve()
ROOT = SOURCE_PATH.parents[2]                   # workshop root (common/ and data/ live here)
sys.path.insert(0, str(ROOT))
from common import foundry_env, guardrails, marketplace_data, resource_names

LABS_DIR = SOURCE_PATH.parents[1]               # labs/ (lab_helpers.py, catch_up.py, artifacts/)
sys.path.insert(0, str(LABS_DIR))
import lab_helpers as helpers
import yaml
from azure.ai.projects.models import (
    MCPTool,
    PromptAgentDefinition,
    WorkflowAgentDefinition,
)


def function_tool_is_registered(source: str, tool_name: str) -> bool:
    """Return whether source registers tool_name in FUNCTION_TOOLS."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if any(isinstance(target, ast.Name) and target.id == "FUNCTION_TOOLS" for target in targets) \
                    and isinstance(value, (ast.List, ast.Tuple)) \
                    and any(isinstance(item, ast.Name) and item.id == tool_name for item in value.elts):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "FUNCTION_TOOLS" \
                and node.func.attr == "append" and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Name) and node.args[0].id == tool_name:
            return True
    return False

ENV = foundry_env.load_env()
MODEL = helpers.pick_model(ENV)
LAB = "stretch5"
HERE = SOURCE_PATH.parent
WORKFLOW_TEMPLATE = HERE / "marketplace_triage_workflow.yaml"
CONCIERGE = resource_names.name(resource_names.PROMPT_CONCIERGE, ENV)
TRIAGE = resource_names.name(resource_names.PROMPT_TRIAGE, ENV)
MARKETPLACE = resource_names.name(resource_names.PROMPT_MARKETPLACE, ENV)
ACCOUNTS = resource_names.name(resource_names.PROMPT_ACCOUNTS, ENV)
COMPLIANCE = resource_names.name(resource_names.PROMPT_COMPLIANCE, ENV)
HANDOFF = resource_names.name(resource_names.PROMPT_HANDOFF, ENV)
WORKFLOW = resource_names.name(resource_names.WORKFLOW_TRIAGE, ENV)
PACKET_FIELDS = ["case_id", "participant_id", "lob", "summary", "participant_goals", "facts_gathered", "options_discussed",
                 "open_questions", "recommended_next_step_for_advisor", "compliance_flags", "created_at"]
PACKET_LIST_FIELDS = ("participant_goals", "facts_gathered", "options_discussed", "open_questions", "compliance_flags")
EXPECTED_S1_ACTIONS = ("triage", "marketplace", "compliance", "handoff")

# %% Step S5.2 - Define agent instructions
# a workflow runs on the platform with nobody there to answer a client-side function_call: the caller pre-fetches
# the facts into the TRIAGE CASE header and the agents work from those plus the knowledge base (server-side MCP).
TRIAGE_MODE = """
TRIAGE MODE
- A message starting with "TRIAGE CASE" comes from the triage workflow, not a participant. Facts from systems of
  record are included; do not call function tools unless a fact is missing. Write for the participant, second person.
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
SPECS = {                                        # agent -> (function tools, uses the knowledge MCP tool)
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
        raise SystemExit("[stretch5] artifacts/lab2/knowledge.json has no mcp_endpoint or connection. Run: python catch_up.py --through 2")
    # VERIFY before delivery: project_connection_id takes the connection resource id (else pass connection_name).
    return MCPTool(server_label="healthcare-marketplace-kb", server_url=knowledge["mcp_endpoint"], require_approval="never",
                   project_connection_id=connection_id)


def parse_workflow(text: str) -> dict:
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict) or parsed.get("kind") != "workflow":
        raise ValueError("workflow template must render a top-level kind: workflow mapping")
    trigger = parsed.get("trigger") or {}
    if trigger.get("kind") != "OnConversationStart":
        raise ValueError("workflow trigger must be OnConversationStart")
    actions = trigger.get("actions")
    if not isinstance(actions, list):
        raise TypeError("workflow trigger.actions must be a list")
    return parsed


def render_workflow() -> str:
    text = WORKFLOW_TEMPLATE.read_text(encoding="utf-8").format(triage=TRIAGE, marketplace=MARKETPLACE, accounts=ACCOUNTS,
                                                                 compliance=COMPLIANCE, handoff=HANDOFF)
    parsed = parse_workflow(text)                # fail here, locally, not at create_version
    action_ids = [action.get("id") for action in parsed["trigger"]["actions"]]
    required = ("triage", "route_marketplace", "route_accounts", "compliance", "handoff", "case_closed")
    missing = [action_id for action_id in required if action_id not in action_ids]
    if missing:
        raise ValueError(f"workflow is missing required actions: {', '.join(missing)}")
    return text


# %% Step S5.3 - Define prompt-agent and workflow publishing
def build(project=None, overrides: dict[str, str] | None = None) -> dict:
    resource_names.suffix(ENV, required=True)
    knowledge = helpers.require_artifact("lab2", "knowledge.json", through=2, caller="stretch5")
    project = project or foundry_env.get_project_client()
    agents = {}
    for name, (tool_names, uses_kb) in SPECS.items():
        instructions = (overrides or {}).get(name) or INSTRUCTIONS[name] + guardrails.COMPLIANCE_INSTRUCTIONS
        assert instructions.endswith(guardrails.COMPLIANCE_INSTRUCTIONS), "every agent carries the compliance block"
        tools = helpers.function_tools(tool_names) + ([knowledge_tool(knowledge)] if uses_kb else [])
        agent = project.agents.create_version(agent_name=name, definition=PromptAgentDefinition(model=MODEL, instructions=instructions, tools=tools))
        agents[name] = {"agent_version": agent.version, "agent_id": agent.id, "function_tools": tool_names, "knowledge": uses_kb}
        print(f"[stretch5] created prompt agent {name} v{agent.version} (tools: {', '.join(tool_names) or 'none'}{', healthcare-marketplace-kb' if uses_kb else ''})")
    text = render_workflow()
    workflow = project.agents.create_version(agent_name=WORKFLOW, definition=WorkflowAgentDefinition(workflow=text))
    helpers.artifact_path(LAB, "workflow.yaml").write_text(text, encoding="utf-8")
    print(f"[stretch5] created workflow agent {WORKFLOW} v{workflow.version} (preview)")
    info = {"lab": LAB, "model": MODEL, "agents": agents, "workflow_name": workflow.name, "workflow_version": workflow.version,
            "workflow_id": workflow.id, "knowledge_base": knowledge.get("kb_name"), "packet_fields": PACKET_FIELDS,
            "hosted_tool": "hosted_tool_snippet.run_triage_workflow reads workflow_name from this file", "created_at": helpers.now_iso()}
    path = helpers.artifact_path(LAB, "agents.json")
    foundry_env.save_artifact(path, info)
    print(f"[stretch5] saved {path.relative_to(LABS_DIR)}; portal: Agents shows {len(agents)} prompt agents + the workflow graph")
    return info


def create_prompt_version(project, name: str, instructions: str, knowledge: dict | None = None):
    """Create one prompt-agent version with the same tool contract as build()."""
    resource_names.suffix(ENV, required=True)
    tool_names, uses_kb = SPECS[name]
    if not instructions.endswith(guardrails.COMPLIANCE_INSTRUCTIONS):
        instructions += guardrails.COMPLIANCE_INSTRUCTIONS
    tools = helpers.function_tools(tool_names)
    if uses_kb:
        if knowledge is None:
            knowledge = helpers.require_artifact("lab2", "knowledge.json", through=2, caller="stretch5")
        tools.append(knowledge_tool(knowledge))
    return project.agents.create_version(
        agent_name=name,
        definition=PromptAgentDefinition(model=MODEL, instructions=instructions, tools=tools),
    )


# %% Step S5.4 - Build the case header
def gather_facts(participant_id: str, claim_ids: list[str] | None = None, include_accounts: bool = False) -> dict:
    participant = dict(marketplace_data.get_participant(participant_id))
    for hidden in ("dob", "contact_preference"):
        participant.pop(hidden, None)
    prescriptions = (participant.get("preferences") or {}).get("prescriptions") or []
    drug = prescriptions[0].split()[0] if prescriptions else None
    plan_types = ("Medicare Advantage HMO", "Medicare Advantage PPO", "Part D") if participant.get("medicare_eligible") \
        else ("ACA Bronze", "ACA Silver", "ACA Gold")
    candidates = []
    for plan_type in plan_types:                 # two per type so a $0 HMO does not crowd out the PPOs
        candidates += marketplace_data.search_plans(participant.get("county", ""), participant.get("state", "UT"), plan_type=plan_type, drug_name=drug)[:2]
    ids = [p["plan_id"] for p in candidates]
    if participant.get("current_plan_id") and participant["current_plan_id"] not in ids:
        ids.insert(0, participant["current_plan_id"])
    keep = ["plan_id", "carrier", "plan_name", "plan_type", "premium_monthly", "deductible_annual", "max_out_of_pocket",
            "star_rating", "network_type", "drug_coverage", "formulary_tier_examples"]
    facts = {"participant": participant, "sponsor": marketplace_data.get_sponsor(participant.get("sponsor_id", "")),
             "enrollment_window": marketplace_data.get_enrollment_window(participant_id, today=ENV.get("MARKETPLACE_TODAY")),
             "plan_candidates": [{k: p[k] for k in keep if k in p} for p in marketplace_data.compare_plans(ids).get("plans", [])],
             "note": "doctor networks are NOT in the data"}
    if include_accounts or claim_ids:
        facts["hra_account"] = marketplace_data.get_hra_account(participant_id)
        facts["claims"] = [marketplace_data.get_claim_status(claim_id) for claim_id in (claim_ids or [])]
    return facts


def case_header(scenario: dict) -> tuple[str, str]:
    case_id = f"{scenario['id']}-{helpers.now_iso()[:10].replace('-', '')}-{scenario['participant_id']}"
    header = "\n".join([f"TRIAGE CASE {case_id}", f"case_id: {case_id}", f"participant_id: {scenario['participant_id']}", "channel: chat",
                        f"participant_message: \"{scenario['message']}\"",
                        f"routing_hint: {scenario['routing_hint']}" if scenario.get("routing_hint") else "",
                        "facts (systems of record, verified by the caller):",
                        json.dumps(gather_facts(scenario["participant_id"], scenario.get("claim_ids"),
                                                include_accounts=scenario.get("include_accounts", False)), default=str)])
    return case_id, header


# %% Step S5.5 - Stream a workflow case
def run_case(openai_client, workflow_name: str, header: str) -> dict:
    conversation = openai_client.conversations.create()
    actions, messages, errors = [], [], []
    try:
        stream = openai_client.responses.create(
            input=header,
            conversation=conversation.id,
            stream=True,
            extra_body=helpers.agent_reference(workflow_name),
        )
        action_positions: dict[str, int] = {}
        for event in stream:
            if event.type in ("response.output_item.added", "response.output_item.done"):
                item = event.item
                data = item.model_dump() if hasattr(item, "model_dump") else {}
                if item.type == "workflow_action":
                    action = {k: data[k] for k in ("action_id", "kind", "status", "agent_name") if data.get(k) is not None}
                    key = str(action.get("action_id") or f"{action.get('kind')}:{action.get('agent_name')}")
                    if key in action_positions:
                        actions[action_positions[key]].update(action)
                    else:
                        action_positions[key] = len(actions)
                        actions.append(action)
                    print(f"[stretch5]   workflow_action {action}")
                    if str(action.get("status", "")).lower() in ("failed", "error", "cancelled"):
                        errors.append(f"workflow action {key} ended with status {action['status']}")
                elif item.type == "message" and event.type.endswith("done"):
                    messages.append("".join(getattr(p, "text", "") or "" for p in (getattr(item, "content", None) or [])))
                    print(f"[stretch5]   message {len(messages)}: {messages[-1][:120].replace(chr(10), ' ')}")
                elif item.type == "function_call":
                    errors.append(f"unanswered function_call {getattr(item, 'name', '?')} (client tools cannot run in a workflow)")
            elif event.type in ("response.failed", "error"):
                errors.append(str(event)[:300])
    except Exception as exc:                     # noqa: BLE001
        errors.append(f"workflow stream failed: {type(exc).__name__}: {str(exc)[:240]}")
    finally:
        try:
            openai_client.conversations.delete(conversation_id=conversation.id)
        except Exception as exc:                 # noqa: BLE001
            errors.append(f"conversation cleanup failed: {type(exc).__name__}: {str(exc)[:160]}")
    return {"conversation_id": conversation.id, "actions": actions, "messages": messages, "errors": errors}


def extract_packet(messages: list[str]) -> dict | None:
    for text in reversed(messages):
        candidate = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        for attempt in (candidate, candidate[candidate.find("{"): candidate.rfind("}") + 1]):
            try:
                packet = json.loads(attempt)
            except (ValueError, TypeError):
                continue
            if isinstance(packet, dict) and "participant_id" in packet:
                return packet
    return None


def validate_packet(packet: dict, expected: dict | None = None) -> list[str]:
    problems = [f"missing field {f}" for f in PACKET_FIELDS if f not in packet]
    extras = sorted(set(packet) - set(PACKET_FIELDS))
    if extras:
        problems.append(f"unexpected fields: {', '.join(extras)}")
    if packet.get("lob") not in ("marketplace", "accounts", "both"):
        problems.append(f"lob must be marketplace|accounts|both, got {packet.get('lob')!r}")
    for field in PACKET_LIST_FIELDS:
        if field in packet and not isinstance(packet[field], list):
            problems.append(f"{field} must be a list")
    if isinstance(packet.get("facts_gathered"), list):
        for index, fact in enumerate(packet["facts_gathered"]):
            if not isinstance(fact, dict) or set(fact) != {"fact", "source"} or not all(isinstance(fact.get(k), str) and fact[k].strip() for k in ("fact", "source")):
                problems.append(f"facts_gathered[{index}] must contain non-empty fact and source strings only")
    for field in ("case_id", "participant_id", "summary", "recommended_next_step_for_advisor", "created_at"):
        if field in packet and (not isinstance(packet[field], str) or not packet[field].strip()):
            problems.append(f"{field} must be a non-empty string")
    if isinstance(packet.get("created_at"), str):
        try:
            created_at = datetime.fromisoformat(packet["created_at"].replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                problems.append("created_at must include a UTC offset")
        except ValueError:
            problems.append("created_at must be ISO 8601")
    for field in ("participant_goals", "options_discussed", "open_questions", "compliance_flags"):
        if isinstance(packet.get(field), list) and not all(isinstance(value, str) for value in packet[field]):
            problems.append(f"{field} must contain strings only")
    for field, value in (expected or {}).items():
        if packet.get(field) != value:
            problems.append(f"{field} must remain {value!r}, got {packet.get(field)!r}")
    text = json.dumps(packet)
    if guardrails.redact_pii(text) != text:
        problems.append("PII pattern found in packet")
    if guardrails.contains_recommendation(" ".join(str(packet.get(f, "")) for f in ("summary", "options_discussed", "recommended_next_step_for_advisor"))):
        problems.append("recommendation wording found in packet")
    return problems


def validate_action_order(actions: list[dict], expected: tuple[str, ...], forbidden: tuple[str, ...] = ()) -> list[str]:
    action_ids = [str(action.get("action_id")) for action in actions if action.get("action_id")]
    problems = []
    cursor = -1
    for action_id in expected:
        try:
            position = action_ids.index(action_id, cursor + 1)
        except ValueError:
            problems.append(f"missing or out-of-order workflow action {action_id}")
            continue
        cursor = position
    for action_id in forbidden:
        if action_id in action_ids:
            problems.append(f"unexpected workflow action {action_id}")
    return problems


def run_concierge_turn(openai_client, user_text: str) -> tuple[str, list[dict]]:
    conversation = openai_client.conversations.create()
    try:
        return helpers.run_turn(openai_client, CONCIERGE, conversation.id, user_text, log_prefix="[stretch5]")
    finally:
        openai_client.conversations.delete(conversation_id=conversation.id)


# %% Step S5.6 - Define the workflow demo
S1 = {"id": "S1", "title": "AEP shopper", "participant_id": "P-1001", "routing_hint": "marketplace",
      "message": "I am on the Contoso Advantage Choice HMO. Is there a plan with a lower cost for my atorvastatin where I could keep "
                 "my cardiologist, Dr. Osei? And when am I allowed to switch?"}


def demo(info: dict | None = None, concierge_turn: bool = False) -> dict:
    info = info or helpers.require_artifact(LAB, "agents.json", through=5, caller="stretch5")
    openai_client = foundry_env.get_openai_client()
    if concierge_turn:                           # the Lab-1 style loop: platform runs the model, we run the tools
        text, _calls = run_concierge_turn(
            openai_client,
            helpers.identity_line("P-1001") + " When can I change my Medicare plan?",
        )
        print(f"[stretch5] {CONCIERGE}> {text[:300]}\n[stretch5] checks: {helpers.fmt_checks(helpers.guardrail_report(text))}")
    case_id, header = case_header(S1)
    print(f"[stretch5] S1 {S1['title']} ({S1['participant_id']}) case {case_id} -> {info['workflow_name']} v{info['workflow_version']}")
    run = run_case(openai_client, info["workflow_name"], header)
    packet = extract_packet(run["messages"])
    problems = list(run["errors"])
    problems += validate_action_order(run["actions"], EXPECTED_S1_ACTIONS, forbidden=("accounts",))
    problems += ["no JSON packet found"] if packet is None else validate_packet(
        packet,
        expected={"case_id": case_id, "participant_id": S1["participant_id"], "lob": "marketplace"},
    )
    packet_saved = packet is not None and not problems
    if packet_saved:
        path = helpers.artifact_path(LAB, "handoff_packets", "S1.json")
        foundry_env.save_artifact(path, packet)
        print(f"[stretch5] saved {path.relative_to(LABS_DIR)} (lob={packet.get('lob')}, flags={len(packet.get('compliance_flags') or [])})")
    print(f"[stretch5] actions={len(run['actions'])} messages={len(run['messages'])} problems={problems or 'none'} errors={run['errors'] or 'none'}")
    print("[stretch5] portal: Agents > healthcare-marketplace-triage-workflow shows the graph; the conversation shows the actions in order")
    print("[stretch5] next: read hosted_tool_snippet.py, the @tool that lets the hosted agent call this workflow")
    info["last_run"] = {"case_id": case_id, "conversation_id": run["conversation_id"], "packet_saved": packet_saved,
                        "problems": problems, "actions": len(run["actions"]), "finished_at": helpers.now_iso()}
    foundry_env.save_artifact(helpers.artifact_path(LAB, "agents.json"), info)
    if problems:
        raise RuntimeError("Stretch 5 demo acceptance failed:\n- " + "\n- ".join(problems))
    return info


# %% [markdown]
# ## Publish the agents and run the baseline
#
# Run the next cell before the exercises. `build()` publishes new versions of the concierge, four specialists,
# and the workflow agent to Foundry, then `demo()` runs S1 through that published workflow. After it completes,
# **Agents > healthcare-marketplace-concierge** exists in the portal for the first YOUR TURN.
# %% Step S5.7 - Publish agents and run the baseline
if "__file__" not in globals():
    _info = build()
    demo(_info)

# %% [markdown]
# ## YOUR TURN (5 min): change an instruction in the portal
#
# In Foundry, open **Agents > healthcare-marketplace-concierge**, add `Always greet the participant by first name`
# to the instructions, and save the new version. Run the next cell. It calls the latest version by name, verifies
# that P-1001 is greeted as Evelyn without recommendation or PII leakage, deletes the test conversation, and
# restores the canonical concierge instructions in `finally`.
# %% Step S5.8 - Inspect portal instructions
if "__file__" not in globals():
    _project = foundry_env.get_project_client()
    _client = foundry_env.get_openai_client()
    try:
        _text, _calls = run_concierge_turn(
            _client,
            helpers.identity_line("P-1001") + " When can I change my Medicare plan?",
        )
        _checks = helpers.guardrail_report(_text)
        print(_text)
        assert re.search(r"\bEvelyn\b", _text, re.IGNORECASE), "The latest portal version did not greet P-1001 as Evelyn."
        assert _checks["no_recommendation"] and _checks["no_pii"], f"Safety checks failed: {_checks}"
    finally:
        _restored = create_prompt_version(_project, CONCIERGE, INSTRUCTIONS[CONCIERGE])
        print(f"[stretch5] restored {CONCIERGE} as v{_restored.version}")

# %% [markdown]
# ## YOUR TURN (5 min): break the router on purpose
#
# Run the next cell. It simulates an upstream classifier bug by changing S1's authoritative `routing_hint` to
# `accounts`, runs the existing workflow, and verifies that the wrong branch ran. No agent versions are created or
# changed. Every temporary conversation is deleted by `run_case`. A completed workflow on the wrong branch is a
# failed business outcome, even when its output is well formed.
# %% Step S5.9 - Test a broken router
if "__file__" not in globals():
    _client = foundry_env.get_openai_client()
    _info = helpers.require_artifact(LAB, "agents.json", through=5, caller="stretch5")
    _broken_s1 = {**S1, "routing_hint": "accounts"}
    _case_id, _header = case_header(_broken_s1)
    _run = run_case(_client, _info["workflow_name"], _header)
    assert not _run["errors"], f"Workflow errors: {_run['errors']}"
    _order_problems = validate_action_order(
        _run["actions"],
        ("triage", "accounts", "compliance", "handoff"),
        forbidden=("marketplace",),
    )
    assert not _order_problems, f"Broken router did not run the expected path: {_order_problems}"
    _packet = extract_packet(_run["messages"])
    assert _packet is not None, "The broken-router run did not return a packet."
    assert _packet.get("open_questions"), "The broken route did not leave the marketplace questions open."
    print("[stretch5] expected failure observed: an incorrect routing hint sent S1 to accounts")

# %% [markdown]
# ## YOUR TURN (10 min): wire and verify hosted delegation
#
# Paste the marked block from `hosted_tool_snippet.py` into Lab 2 `hosted/main.py`, add
# `run_triage_workflow` to the existing `FUNCTION_TOOLS` list, and add the instruction shown in that file. Calling
# `FUNCTION_TOOLS.append(run_triage_workflow)` after the list is defined is also valid. Do not create another
# hosted package for this stretch.
#
# After the acceptance cell passes, open a Bash terminal at the workshop root and redeploy from Lab 2's hosted
# directory, not Lab 3. This is the directory containing the `azure.yaml` for the hosted agent you edited:
#
# ```bash
# cd labs/lab2-hosted-knowledge-sessions/hosted
# azd env set MARKETPLACE_WORKFLOW_AGENT_NAME healthcare-marketplace-triage-workflow
# azd up
# ```
#
# `azd env set` stores the workflow name in the active azd environment used by `azd up`. Alternatively, vendor
# `artifacts/stretch5/agents.json` next to `main.py` before running `azd up`.
#
# Before redeploying Lab 2, run the next cell from this notebook. It exercises the exact delegation function,
# verifies the Lab 2 source has the function and tool registration, validates the returned packet, and relies on
# the tool's `finally` block to delete its temporary conversation. Success prints a clear `PASSED` message and
# confirms that Lab 2 is ready to deploy.
# %% Step S5.10 - Test hosted delegation
if "__file__" not in globals():
    import hosted_tool_snippet as _hosted_tool

    _lab2_main = LABS_DIR / "lab2-hosted-knowledge-sessions" / "hosted" / "main.py"
    _lab2_source = _lab2_main.read_text(encoding="utf-8")
    assert "def run_triage_workflow(" in _lab2_source, f"Paste the hosted tool into {_lab2_main}."
    assert function_tool_is_registered(_lab2_source, "run_triage_workflow"), \
        "Add run_triage_workflow to the FUNCTION_TOOLS list."
    _hosted_tool.WORKFLOW = _hosted_tool.load_workflow_reference()
    _hosted_tool._openai_client = None
    _result = _hosted_tool.run_triage_workflow(
        "TRIAGE CASE hosted-gate-P-1005\ncase_id: hosted-gate-P-1005\nparticipant_id: P-1005\n"
        "participant_message: \"Which ACA plan should I pick?\"\nfacts: participant requested a licensed advisor"
    )
    assert _result.get("status") == "completed", _result
    assert _result.get("packet"), "Hosted delegation returned no handoff packet."
    assert not validate_packet(
        _result["packet"],
        expected={"case_id": "hosted-gate-P-1005", "participant_id": "P-1005", "lob": "marketplace"},
    )
    print(
        "[stretch5] PASSED hosted delegation: "
        f"workflow={_result.get('workflow', _hosted_tool.WORKFLOW['workflow_name'])}, "
        f"case_id={_result['packet']['case_id']}, participant_id={_result['packet']['participant_id']}, "
        f"lob={_result['packet']['lob']}; Lab 2 is ready to deploy"
    )

# %% [markdown]
# ## Script-only entry point - skip in Jupyter
#
# **Running this notebook cell by cell? Skip the next cell.** The earlier cells provide the notebook path.
# The next cell is only the command-line entry point for running this lab's `.py` file as one program.
# Its command-line invocation is guarded in the generated notebook; running the cell does not launch the lab.
# For script mode instead, run `python stretch5_prompt_agents.py --help` in a Bash terminal from this lab's folder and choose the desired options.

# %% Step S5.11 - Script-only entry point (skip in Jupyter)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--demo-only", action="store_true", help="reuse artifacts/stretch5/agents.json")
    parser.add_argument("--concierge-turn", action="store_true", help="also run one function-call turn on healthcare-marketplace-concierge")
    args = parser.parse_args()
    if args.demo_only:
        demo(concierge_turn=args.concierge_turn)
    else:
        info = build()
        if not args.build_only:
            demo(info, concierge_turn=args.concierge_turn)
