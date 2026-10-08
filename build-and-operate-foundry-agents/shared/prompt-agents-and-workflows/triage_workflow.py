"""Lab 12's MAF graph: runs in the notebook or in the existing concierge container."""
from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Never

from agent_framework import SupportsAgentRun, Workflow, WorkflowBuilder, WorkflowContext, executor
from agent_framework.foundry import FoundryAgent
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

from common import guardrails, marketplace_data

PACKET_FIELDS = [
    "case_id", "participant_id", "lob", "summary", "participant_goals", "facts_gathered",
    "options_discussed", "open_questions", "recommended_next_step_for_advisor", "compliance_flags", "created_at",
]
PACKET_LIST_FIELDS = ("participant_goals", "facts_gathered", "options_discussed", "open_questions", "compliance_flags")
ROLES = ("triage", "marketplace", "accounts", "compliance", "handoff")
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass
class TriageCase:
    """One message carries the original facts and each step's work to the next executor."""

    header: str
    case_id: str
    participant_id: str
    route: str = ""
    triage_summary: str = ""
    marketplace_draft: str = "NO_MARKETPLACE_QUESTION"
    accounts_draft: str = "NO_ACCOUNTS_QUESTION"
    review: str = ""


def case_from_header(header: str) -> TriageCase:
    values = {}
    for field in ("case_id", "participant_id"):
        matches = re.findall(rf"^{field}:\s*(\S+)\s*$", header, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"TRIAGE CASE must contain exactly one {field} line.")
        values[field] = matches[0]
    return TriageCase(header=header, **values)


def extract_packet(messages: list[str]) -> dict | None:
    for text in reversed(messages):
        candidate = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            packet = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(packet, dict) and "participant_id" in packet:
            return packet
    return None


def validate_packet(packet: dict, expected: dict | None = None) -> list[str]:
    problems = [f"missing field {field}" for field in PACKET_FIELDS if field not in packet]
    extras = sorted(set(packet) - set(PACKET_FIELDS))
    if extras:
        problems.append(f"unexpected fields: {', '.join(extras)}")
    if packet.get("lob") not in ("marketplace", "accounts", "both"):
        problems.append("lob must be marketplace|accounts|both")
    for field in PACKET_LIST_FIELDS:
        if field in packet and not isinstance(packet[field], list):
            problems.append(f"{field} must be a list")
    if isinstance(packet.get("facts_gathered"), list):
        for index, fact in enumerate(packet["facts_gathered"]):
            if not isinstance(fact, dict) or set(fact) != {"fact", "source"} \
                    or not all(isinstance(fact.get(key), str) and fact[key].strip() for key in ("fact", "source")):
                problems.append(f"facts_gathered[{index}] must contain non-empty fact and source strings only")
    for field in ("case_id", "participant_id", "summary", "recommended_next_step_for_advisor", "created_at"):
        if field in packet and (not isinstance(packet[field], str) or not packet[field].strip()):
            problems.append(f"{field} must be a non-empty string")
    if isinstance(packet.get("created_at"), str):
        try:
            created_at = datetime.fromisoformat(packet["created_at"].replace("Z", "+00:00"))
            if created_at.utcoffset() is None or created_at.utcoffset().total_seconds() != 0:
                problems.append("created_at must include a UTC offset of zero")
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
    if guardrails.contains_recommendation(" ".join(str(packet.get(field, "")) for field in
                                                   ("summary", "options_discussed", "recommended_next_step_for_advisor"))):
        problems.append("recommendation wording found in packet")
    return problems


def build_workflow(agents: dict[str, SupportsAgentRun]) -> Workflow:
    """Use explicit executors so the case, conditional edges and final output are easy to inspect."""

    @executor(id="triage")
    async def triage(case: TriageCase, ctx: WorkflowContext[TriageCase]) -> None:
        response = await agents["triage"].run(case.header)
        case.triage_summary = response.text
        routes = re.findall(r"^ROUTE:\s*(marketplace|accounts|both)\s*$", response.text, re.MULTILINE)
        if len(routes) != 1:
            raise ValueError("Triage must return exactly one ROUTE: marketplace | accounts | both line.")
        case.route = routes[0]
        await ctx.send_message(case)

    @executor(id="marketplace")
    async def marketplace(case: TriageCase, ctx: WorkflowContext[TriageCase]) -> None:
        response = await agents["marketplace"].run(case.header + "\nTRIAGE SUMMARY\n" + case.triage_summary)
        case.marketplace_draft = response.text
        await ctx.send_message(case)

    @executor(id="accounts")
    async def accounts(case: TriageCase, ctx: WorkflowContext[TriageCase]) -> None:
        response = await agents["accounts"].run(case.header + "\nTRIAGE SUMMARY\n" + case.triage_summary)
        case.accounts_draft = response.text
        await ctx.send_message(case)

    @executor(id="compliance")
    async def compliance(case: TriageCase, ctx: WorkflowContext[TriageCase]) -> None:
        request = (
            "COMPLIANCE REVIEW REQUEST\n" + case.header
            + "\nMARKETPLACE DRAFT\n" + case.marketplace_draft
            + "\nACCOUNTS DRAFT\n" + case.accounts_draft
        )
        response = await agents["compliance"].run(request)
        case.review = response.text
        await ctx.send_message(case)

    @executor(id="handoff")
    async def handoff(case: TriageCase, ctx: WorkflowContext[Never, dict]) -> None:
        request = (
            "BUILD HANDOFF PACKET\n" + case.header
            + "\nTRIAGE SUMMARY\n" + case.triage_summary
            + "\nMARKETPLACE DRAFT\n" + case.marketplace_draft
            + "\nACCOUNTS DRAFT\n" + case.accounts_draft
            + "\nCOMPLIANCE REVIEW\n" + case.review
        )
        response = await agents["handoff"].run(request)
        packet = extract_packet([response.text])
        if packet is None:
            raise ValueError("Handoff returned no JSON packet.")
        problems = validate_packet(packet, expected={
            "case_id": case.case_id, "participant_id": case.participant_id, "lob": case.route,
        })
        if problems:
            raise ValueError("Handoff packet rejected:\n- " + "\n- ".join(problems))
        await ctx.yield_output(packet)

    builder = WorkflowBuilder(start_executor=triage, output_from=[handoff], name="healthcare-marketplace-triage")
    builder.add_edge(triage, marketplace, condition=lambda case: case.route in ("marketplace", "both"))
    builder.add_edge(triage, accounts, condition=lambda case: case.route == "accounts")
    # A both-area case visits each specialist once, sequentially; Labs 7-8 teach parallel fan-out/fan-in.
    builder.add_edge(marketplace, accounts, condition=lambda case: case.route == "both")
    builder.add_edge(marketplace, compliance, condition=lambda case: case.route == "marketplace")
    builder.add_edge(accounts, compliance)
    builder.add_edge(compliance, handoff)
    return builder.build()


async def run_workflow(workflow: Workflow, header: str) -> dict:
    actions = []
    packets = []
    async for event in workflow.run(case_from_header(header), stream=True):
        if event.type == "executor_completed":
            actions.append({"action_id": event.executor_id})
            print(f"[MAF] completed: {event.executor_id}")
        elif event.type == "output":
            packets.append(event.data)
    if len(packets) != 1:
        raise RuntimeError(f"Expected exactly one advisor packet, received {len(packets)}.")
    return {"actions": actions, "packet": packets[0]}


async def run_case(info: dict, header: str, project_endpoint: str) -> dict:
    """Connect to pinned Lab 11 prompt versions, then run a fresh graph for this case."""
    if info.get("runtime") != "microsoft-agent-framework" or set(info.get("roles", {})) != set(ROLES):
        raise ValueError("Use Lab 12's MAF agents.json, not a legacy Foundry workflow reference.")
    if info.get("graph_sha256") != SOURCE_SHA256 \
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The MAF graph changed. Restart the kernel and repeat Lab 12 before invoking or deploying it.")
    tools = {
        "marketplace": [marketplace_data.search_plans, marketplace_data.compare_plans, marketplace_data.get_enrollment_window],
        "accounts": [marketplace_data.get_hra_account, marketplace_data.get_claim_status, marketplace_data.list_eligible_expenses],
    }
    async with AsyncExitStack() as stack:
        credential = await stack.enter_async_context(DefaultAzureCredential())
        project = await stack.enter_async_context(AIProjectClient(endpoint=project_endpoint, credential=credential))
        agents = {}
        for role in ROLES:
            name = info["roles"][role]
            version = info["agents"][name]["agent_version"]
            if not isinstance(version, str) or not version:
                raise ValueError(f"Missing prompt version for {role}; complete Lab 11.")
            agents[role] = await stack.enter_async_context(FoundryAgent(
                project_client=project, agent_name=name, agent_version=version,
                tools=tools.get(role, []), default_options={"store": False},
            ))
        return await run_workflow(build_workflow(agents), header)
