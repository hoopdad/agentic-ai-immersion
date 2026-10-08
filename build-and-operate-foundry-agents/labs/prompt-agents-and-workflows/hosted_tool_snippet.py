"""Labs 11-12: the `run_triage_workflow` tool for the hosted agent.

Runs on: inside the hosted container (Labs 5-6 `hosted/main.py`) once you paste it there; this file is also importable
on the workstation for a quick check (`python hosted_tool_snippet.py`).

What it teaches: a hosted (code) agent and a platform-managed workflow agent are not rivals. The hosted agent owns
the participant conversation, session state and the custom Python; when a case needs the governed triage flow
(specialists, compliance review, advisor packet), it delegates with ONE Responses call bound by `agent_reference`
to the workflow agent Labs 11-12 created. The workflow runs on the platform with its own versions and portal graph.

How to wire it into Labs 5-6 hosted/main.py:
    1. copy the block between the markers into main.py after the other @tool functions
    2. register `run_triage_workflow` by adding it to the existing `FUNCTION_TOOLS` list (or by calling
       `FUNCTION_TOOLS.append(run_triage_workflow)` after that list is defined)
    3. add to ROLE_INSTRUCTIONS: "When the participant accepts an advisor handoff, call run_triage_workflow with a
       short case summary (participant id, LOB, what was asked, facts already gathered)."
    4. in a Bash terminal, change to `labs/hosted-knowledge-sessions/hosted/` (Labs 5-6, not Labs 7-8; this is
       the directory containing the `azure.yaml` for the hosted agent you edited), then give the deployment
       the workflow name and redeploy:
           azd env set MARKETPLACE_WORKFLOW_AGENT_NAME healthcare-marketplace-triage-workflow
           azd up
       Alternatively, vendor `artifacts/stretch6/agents.json` next to `main.py` before running `azd up`.
The hosted agent's managed identity needs Azure AI User on the project to call the workflow agent.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from common import guardrails

try:
    from agent_framework import tool
    from pydantic import Field
except ImportError:                              # workstation check without agent_framework / pydantic installed
    def Field(**kwargs):                         # type: ignore[misc]
        return kwargs.get("description")

    def tool(**_kwargs):                         # type: ignore[misc]
        return lambda fn: fn

ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
AGENTS_FILE_CANDIDATES = (HERE / "agents.json", HERE.parents[0] / "artifacts" / "stretch6" / "agents.json")
PACKET_FIELDS = {"case_id", "participant_id", "lob", "summary", "participant_goals", "facts_gathered", "options_discussed",
                 "open_questions", "recommended_next_step_for_advisor", "compliance_flags", "created_at"}

# ---- paste from here into hosted/main.py -----------------------------------------------------------------------


def load_workflow_reference(environ: dict[str, str] | None = None, candidates=None) -> dict | None:
    """Workflow agent name/version from env or artifacts/stretch6/agents.json. None when unavailable."""
    environ = os.environ if environ is None else environ
    candidates = AGENTS_FILE_CANDIDATES if candidates is None else candidates
    name = environ.get("MARKETPLACE_WORKFLOW_AGENT_NAME")
    if name:
        return {"workflow_name": name, "workflow_version": environ.get("MARKETPLACE_WORKFLOW_AGENT_VERSION"), "source": "environment"}
    for path in candidates:
        path = Path(path)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("workflow_name"):
                return {"workflow_name": data["workflow_name"], "workflow_version": data.get("workflow_version"), "source": str(path)}
    return None


WORKFLOW = load_workflow_reference()
_openai_client = None


def openai_client():
    """OpenAI client bound to the Foundry project, created on first use with the container's identity."""
    global _openai_client
    if _openai_client is None:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        project = AIProjectClient(endpoint=ENDPOINT, credential=DefaultAzureCredential(), allow_preview=True)
        _openai_client = project.get_openai_client()
    return _openai_client


def _extract_packet(text: str) -> dict | None:
    """The workflow ends with the advisor-handoff packet as JSON (sometimes fenced)."""
    candidate = text.strip().strip("`")
    for attempt in (candidate, candidate[candidate.find("{"): candidate.rfind("}") + 1]):
        try:
            packet = json.loads(attempt)
        except (ValueError, TypeError):
            continue
        if isinstance(packet, dict) and "participant_id" in packet:
            return packet
    return None


def _packet_problems(packet: dict | None) -> list[str]:
    if packet is None:
        return ["workflow output did not contain a JSON handoff packet"]
    problems = [f"missing field {field}" for field in sorted(PACKET_FIELDS - set(packet))]
    extras = sorted(set(packet) - PACKET_FIELDS)
    if extras:
        problems.append(f"unexpected fields: {', '.join(extras)}")
    if packet.get("lob") not in ("marketplace", "accounts", "both"):
        problems.append("invalid lob")
    serialized = json.dumps(packet)
    if guardrails.redact_pii(serialized) != serialized:
        problems.append("PII pattern found in packet")
    if guardrails.contains_recommendation(" ".join(str(packet.get(field, "")) for field in
                                                   ("summary", "options_discussed", "recommended_next_step_for_advisor"))):
        problems.append("recommendation wording found in packet")
    return problems


@tool(approval_mode="never_require")
def run_triage_workflow(case_text: Annotated[str, Field(description="Case summary for the advisor: participant id, LOB, what was asked, "
                                                                    "facts already gathered, what needs a licensed advisor")]) -> dict:
    """Send a case through the Healthcare Marketplace triage workflow (platform workflow agent) and return the advisor handoff packet."""
    if not WORKFLOW:
        return {"status": "unavailable",
                "error": "The triage workflow agent is not available in this deployment. Run Labs 11-12 so that "
                         "artifacts/stretch6/agents.json exists (or set MARKETPLACE_WORKFLOW_AGENT_NAME), then redeploy.",
                "next_step": "Tell the participant a licensed benefit advisor will follow up and note the case details."}
    if not ENDPOINT:
        return {"status": "unavailable", "error": "FOUNDRY_PROJECT_ENDPOINT is not set; cannot reach the workflow agent."}
    client = openai_client()
    conversation = client.conversations.create()
    cleanup_error = None
    call_error = None
    text = ""
    try:
        # One Responses call, no streaming: agent_reference binds it to the server-side workflow agent by name
        # (latest version). The workflow does triage -> specialists -> compliance -> packet on the platform.
        response = client.responses.create(input=case_text, conversation=conversation.id,
                                           extra_body={"agent_reference": {"name": WORKFLOW["workflow_name"], "type": "agent_reference"}})
        text = response.output_text or ""
    except Exception as exc:                     # noqa: BLE001  (the model gets a plain explanation, not a stack trace)
        call_error = f"workflow call failed: {type(exc).__name__}: {str(exc)[:200]}"
    finally:
        try:
            client.conversations.delete(conversation_id=conversation.id)
        except Exception as exc:                 # noqa: BLE001
            cleanup_error = f"{type(exc).__name__}: {str(exc)[:160]}"
    if call_error:
        return {"status": "failed", "error": call_error, "cleanup_error": cleanup_error,
                "workflow": WORKFLOW["workflow_name"], "conversation_id": conversation.id}
    packet = _extract_packet(text)
    problems = _packet_problems(packet)
    status = "completed" if not problems and cleanup_error is None else "failed"
    return {"status": status, "workflow": WORKFLOW["workflow_name"], "workflow_version": WORKFLOW.get("workflow_version"),
            "conversation_id": conversation.id, "packet": packet, "packet_problems": problems,
            "cleanup_error": cleanup_error, "output_text": guardrails.redact_pii(text)[:2000],
            "note": "Packet is for the licensed advisor; summarise it for the participant without repeating internal fields."}


# ---- paste until here --------------------------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[stretch6] workflow reference: {WORKFLOW or 'not found (run stretch6_prompt_agents.py or set MARKETPLACE_WORKFLOW_AGENT_NAME)'}")
    print("[stretch6] tool ready:", getattr(run_triage_workflow, "name", None) or run_triage_workflow.__name__)
    if WORKFLOW and ENDPOINT and "--call" in sys.argv:
        result = run_triage_workflow("TRIAGE CASE demo\nparticipant_id: P-1003\nparticipant_message: \"My claim CLM-9003 was denied, "
                                     "why and what do I send?\"\nfacts: claim CLM-9003 denied missing_proof_of_payment")
        print(json.dumps({k: v for k, v in result.items() if k != "output_text"}, indent=2, default=str)[:1500])
