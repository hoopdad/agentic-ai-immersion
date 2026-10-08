"""Lab 12: paste the marked async tool into Labs 5-6 hosted/main.py.

Add run_triage_workflow to FUNCTION_TOOLS and add this instruction to ROLE_INSTRUCTIONS:
"When the participant accepts an advisor handoff, call run_triage_workflow with a TRIAGE CASE
summary containing case_id, participant_id, participant_message and verified facts."

The notebook packages triage_workflow.py and triage_agents.json beside main.py before deployment.
The graph runs INSIDE the existing concierge container; the pinned prompt-agent turns run in Foundry.
The container identity needs Azure AI User on the project. No workflow agent or extra service is created.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Annotated

from agent_framework import tool
from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---- paste from here into hosted/main.py ----
from triage_workflow import run_case


@tool(approval_mode="never_require")
async def run_triage_workflow(
    case_text: Annotated[str, Field(description=(
        "TRIAGE CASE summary: separate case_id and participant_id lines, participant_message, "
        "verified facts and the questions for a licensed advisor. Do not include sensitive identifiers."
    ))],
) -> dict:
    """Run the MAF triage graph in this process and return its validated advisor packet."""
    references = Path(__file__).resolve().parent / "triage_agents.json"
    if not references.is_file():
        return {
            "status": "unavailable",
            "error": "Lab 12's triage_agents.json is missing. Package the MAF graph and prompt references, then redeploy.",
        }
    info = json.loads(references.read_text(encoding="utf-8"))
    result = await run_case(info, case_text, os.environ["FOUNDRY_PROJECT_ENDPOINT"])
    return {
        "status": "completed", "runtime": "microsoft-agent-framework",
        "packet": result["packet"], "actions": result["actions"],
        "note": "This packet is for the licensed advisor. Summarize it without repeating internal fields.",
    }
# ---- paste until here ----
