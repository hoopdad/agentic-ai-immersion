# %% [markdown]
# # Stretch 6B: Workflows and hosted delegation
#
# Start a fresh kernel after Stretch 6A and reuse its existing prompt-agent names and IDs.
# Create the workflow only, verify routing, and connect the hosted concierge to the published workflow.
# Workflow turns and hosted deployment call Azure services and may incur charges.
#
# This cell loads A's published references and workflow definitions without republishing prompt agents.
# %% Step S6.1 - Load existing prompt-agent references
from pathlib import Path
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/stretch6-prompt-agents-and-workflows/stretch6b_workflows_delegation.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/stretch6-prompt-agents-and-workflows/stretch6b_workflows_delegation.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py")

if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted = {}
    part_a = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("stretch6", "part_a.json"), lab="stretch6", part="a", context=notebook_parts.scope(driver.ENV),
    )
    prompt_info = part_a["state"]["prompt_agents"]
    assert set(prompt_info["agents"]) == set(driver.SPECS)
    assert all(reference.get("agent_id") and reference.get("agent_version") for reference in prompt_info["agents"].values())

# %% [markdown]
# This cell creates only the workflow agent over A's published prompt names and runs its accepted marketplace path.
# %% Step S6.2 - Publish and execute the workflow
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("workflow", None)
    info = driver.publish_workflow(prompt_info)
    info = driver.demo(info)
    assert info["agents"] == prompt_info["agents"], "The workflow phase changed published prompt references."
    accepted["workflow"] = True

# %% [markdown]
# This cell sends an intentionally wrong routing hint and verifies the accounts branch leaves marketplace questions unresolved.
# %% Step S6.3 - Detect a routing failure
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("routing", None)
    assert accepted.get("workflow"), "Complete the current workflow gate before testing routing."
    case_id, header = driver.case_header({**driver.S1, "routing_hint": "accounts"})
    run = driver.run_case(driver.foundry_env.get_openai_client(), info["workflow_name"], header)
    assert not run["errors"], run["errors"]
    problems = driver.validate_action_order(
        run["actions"], ("triage", "accounts", "compliance", "handoff"), forbidden=("marketplace",)
    )
    assert not problems, problems
    packet = driver.extract_packet(run["messages"])
    assert packet and packet.get("open_questions"), "Wrong routing must leave the marketplace questions open."
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "routing_evidence.json"), {
        "case_id": case_id, "expected_failure_observed": True, "actions": run["actions"],
    })
    accepted["routing"] = True

# %% [markdown]
# ## YOUR TURN: wire hosted delegation
#
# Paste the marked block and instruction from `hosted_tool_snippet.py` into Lab 3 `hosted/main.py`
# and add `run_triage_workflow` to `FUNCTION_TOOLS` (a list item or `.append`).
# Keep the existing hosted package: delegation is a tool boundary, not another hosted service.
#
# This cell checks the saved tool registration and exercises the exact delegation function against the existing workflow.
# %% Step S6.4 - Verify hosted delegation
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("delegation", None)
    assert accepted.get("routing"), "Complete the current routing gate before hosted delegation."
    import hosted_tool_snippet as hosted_tool
    source = (ROOT / "labs/lab3-hosted-knowledge-sessions/hosted/main.py").read_text(encoding="utf-8")
    assert "def run_triage_workflow(" in source, "Paste the hosted delegation function into Lab 3."
    assert driver.function_tool_is_registered(source, "run_triage_workflow"), "Register the delegation tool."
    hosted_tool.WORKFLOW = hosted_tool.load_workflow_reference()
    hosted_tool._openai_client = None
    result = hosted_tool.run_triage_workflow(
        "TRIAGE CASE hosted-gate-P-1005\ncase_id: hosted-gate-P-1005\nparticipant_id: P-1005\n"
        'participant_message: "Which ACA plan should I pick?"\nfacts: participant requested a licensed advisor'
    )
    assert result.get("status") == "completed" and result.get("packet"), result
    assert not driver.validate_packet(result["packet"], expected={
        "case_id": "hosted-gate-P-1005", "participant_id": "P-1005", "lob": "marketplace",
    })
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "delegation_evidence.json"), result)
    accepted["delegation"] = True

# %% [markdown]
# This cell deploys the edited Lab 3 package with its workflow reference only after routing and delegation acceptance pass.
# %% Step S6.5 - Deploy hosted delegation
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("deployment", None)
    assert all(accepted.get(key) for key in ("workflow", "routing", "delegation")), "Complete every current B gate before deployment."
    from deployment import bash_deploy_block
    lab3 = lab_helpers.load_lab_module("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py")
    prepare = lab_helpers.load_lab_module("lab3-hosted-knowledge-sessions/hosted/prepare.py")
    prepare.vendor()
    hosted = lab_helpers.require_artifact("lab3", "hosted.json", through=3, caller="stretch6b")
    settings = {**hosted.get("env_for_container", {}), "MARKETPLACE_WORKFLOW_AGENT_NAME": info["workflow_name"]}
    command = bash_deploy_block(lab3.HOSTED_DIR, lab3.AGENT_NAME, "responses", driver.ENV, settings, check_package=True)
    subprocess.run(["bash", "-lc", command], cwd=lab3.HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", lab3.AGENT_NAME], cwd=lab3.HOSTED_DIR, check=True)
    accepted["deployment"] = True
    part_b = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("stretch6", "part_b.json"), lab="stretch6", part="b", context=notebook_parts.scope(driver.ENV),
        state={"workflow": info, "delegation": result, "accepted": accepted},
        evidence=[
            lab_helpers.artifact_path("stretch6", "agents.json"),
            lab_helpers.artifact_path("stretch6", "workflow.yaml"),
            lab_helpers.artifact_path("stretch6", "handoff_packets", "S1.json"),
            lab_helpers.artifact_path("stretch6", "routing_evidence.json"),
            lab_helpers.artifact_path("stretch6", "delegation_evidence.json"),
        ],
    )
