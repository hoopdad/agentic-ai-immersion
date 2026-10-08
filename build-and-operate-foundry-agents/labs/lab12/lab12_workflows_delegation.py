# %% [markdown]
# # Lab 12: Microsoft Agent Framework workflows and hosted delegation
#
# **Prerequisites:** Lab 11.
#
# Start a fresh kernel after Lab 11 and reuse its existing prompt-agent names and versions.
# MAF owns the Python graph; Foundry still owns the prompt definitions, model and knowledge tools.
# First run the graph in this notebook, then package it inside the existing Lab 6 concierge.
# No Foundry workflow agent, YAML definition, new model or extra hosted service is needed.
# Graph construction is local. Prompt-agent turns and hosted deployment call Azure and may incur charges.
#
# Read [MAF workflow concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/?pivots=programming-language-python).
#
# This cell loads Lab 11's checkpoint without republishing prompt agents or calling Azure.
# %% Step 12.1 - Load existing prompt-agent references
# ruff: noqa: F704
# Jupyter supports top-level await; this file is notebook authoring input, not a terminal driver.
from pathlib import Path
import inspect
import shutil
import subprocess
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab12/lab12_workflows_delegation.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab12/lab12_workflows_delegation.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("prompt-agents-and-workflows/stretch6_prompt_agents.py")
import triage_workflow

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
# ## Read the graph, then run it
#
# A `TriageCase` carries the original facts, route and drafts between steps.
# Each `@executor` is one step: it calls a pinned `FoundryAgent`, records the result,
# and uses `ctx.send_message(case)` to forward that case along an edge.
# `WorkflowBuilder.add_edge(..., condition=...)` chooses the next specialist from the route.
# Only handoff uses `ctx.yield_output(packet)`; intermediate drafts are not final answers.
#
# The paths are `triage -> marketplace -> compliance -> handoff`,
# `triage -> accounts -> compliance -> handoff`, or
# `triage -> marketplace -> accounts -> compliance -> handoff` for both areas.
# Both specialists run sequentially here to keep the graph easy to follow;
# Labs 7-8 already teach parallel fan-out/fan-in.
#
# Inspect the displayed source in `../../shared/prompt-agents-and-workflows/triage_workflow.py`.
# `run_case` connects `FoundryAgent` to Lab 11's exact `agent_version` and supplies the
# already-declared Python function tools. Foundry executes the knowledge MCP tool;
# MAF executes local functions in this notebook (later, inside the concierge container).
# `store=False` avoids creating durable model transcripts for these one-shot case runs.
#
# This cell displays the real graph and streams executor completion events while running the S1 marketplace case.
# %% Step 12.2 - Inspect and execute the MAF graph
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("workflow", None)
    print(inspect.getsource(triage_workflow.TriageCase))
    print(inspect.getsource(triage_workflow.build_workflow))
    info = driver.prepare_workflow(prompt_info)
    info = await driver.demo(info)
    assert info["agents"] == prompt_info["agents"], "The graph changed published prompt references."
    accepted["workflow"] = True

# %% [markdown]
# This cell sends an intentionally wrong routing hint and verifies the accounts branch leaves marketplace questions unresolved.
# %% Step 12.3 - Detect a routing failure
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("routing", None)
    assert accepted.get("workflow"), "Complete the current workflow gate before testing routing."
    case_id, header = driver.case_header({**driver.S1, "routing_hint": "accounts"})
    run = await driver.run_case(info, header, driver.ENV["FOUNDRY_PROJECT_ENDPOINT"])
    problems = driver.validate_action_order(
        run["actions"], ("triage", "accounts", "compliance", "handoff"), forbidden=("marketplace",)
    )
    assert not problems, problems
    packet = run["packet"]
    assert packet.get("open_questions"), "Wrong routing must leave the marketplace questions open."
    assert not driver.validate_packet(packet, expected={
        "case_id": case_id, "participant_id": driver.S1["participant_id"], "lob": "accounts",
    })
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "routing_evidence.json"), {
        "case_id": case_id, "expected_failure_observed": True, "actions": run["actions"],
    })
    accepted["routing"] = True

# %% [markdown]
# ## YOUR TURN: wire hosted delegation
#
# Paste the marked async block from `../../shared/prompt-agents-and-workflows/hosted_tool_snippet.py` into Labs 5-6 `../../shared/hosted-knowledge-sessions/hosted/main.py`
# and add `run_triage_workflow` to `FUNCTION_TOOLS` (a list item or `.append`).
# Add its handoff instruction to `ROLE_INSTRUCTIONS`, before `INSTRUCTIONS` is assembled.
# Keep the existing hosted package: the tool runs the same Python graph in the concierge process.
# It calls the pinned prompt agents, not a platform workflow endpoint.
#
# The next cell packages only the graph source and non-secret prompt references beside `main.py`.
# The container's managed identity needs Azure AI User on the project; no credential files are copied.
# Keep the `case_id` and `participant_id` header lines so the packet can be checked against its input.
#
# This cell packages the graph and prompt references, then awaits the actual saved concierge delegation tool.
# %% Step 12.4 - Verify hosted delegation
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("delegation", None)
    assert accepted.get("routing"), "Complete the current routing gate before hosted delegation."
    hosted_dir = ROOT / "shared/hosted-knowledge-sessions/hosted"
    source = (hosted_dir / "main.py").read_text(encoding="utf-8")
    assert "def run_triage_workflow(" in source, "Paste the hosted delegation function into Labs 5-6."
    assert driver.function_tool_is_registered(source, "run_triage_workflow"), "Register the delegation tool."
    shutil.copy2(ROOT / "shared/prompt-agents-and-workflows/triage_workflow.py", hosted_dir / "triage_workflow.py")
    driver.foundry_env.save_artifact(hosted_dir / "triage_agents.json", info)
    hosted_tool = lab_helpers.load_lab_module("hosted-knowledge-sessions/hosted/main.py")
    result = await hosted_tool.run_triage_workflow(
        "TRIAGE CASE hosted-gate-P-1005\ncase_id: hosted-gate-P-1005\nparticipant_id: P-1005\n"
        'participant_message: "Which ACA plan should I pick?"\nfacts: participant requested a licensed advisor'
    )
    assert result.get("status") == "completed" and result.get("packet"), result
    assert not driver.validate_packet(result["packet"], expected={
        "case_id": "hosted-gate-P-1005", "participant_id": "P-1005", "lob": "marketplace",
    })
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "delegation_evidence.json"), result)
    tested_sources = driver.source_fingerprints()
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "source_evidence.json"), tested_sources)
    accepted["delegation"] = True

# %% [markdown]
# The graph will run inside the existing concierge container after this deployment.
# Prompt references remain pinned; editing a prompt later requires repeating Labs 11-12.
# A local tool PASS is not evidence that a deployed container can authenticate or invoke the agents.
#
# This cell deploys the edited Labs 5-6 package only after graph, routing and delegation acceptance pass.
# %% Step 12.5 - Deploy hosted delegation
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("deployment", None)
    assert all(accepted.get(key) for key in ("workflow", "routing", "delegation")), "Complete every current Lab 12 gate before deployment."
    assert driver.source_fingerprints() == tested_sources, "Graph, prompt references or concierge source changed; rerun the Lab 12 gates."
    from deployment import bash_deploy_block
    lab3 = lab_helpers.load_lab_module("hosted-knowledge-sessions/lab3_hosted_knowledge.py")
    prepare = lab_helpers.load_lab_module("hosted-knowledge-sessions/hosted/prepare.py")
    prepare.vendor()
    hosted = driver.require_hosted_concierge()
    settings = dict(hosted.get("env_for_container", {}))
    settings.pop("MARKETPLACE_WORKFLOW_AGENT_NAME", None)
    settings.pop("MARKETPLACE_WORKFLOW_AGENT_VERSION", None)
    command = bash_deploy_block(lab3.HOSTED_DIR, lab3.AGENT_NAME, "responses", driver.ENV, settings, check_package=True)
    subprocess.run(["bash", "-lc", command], cwd=lab3.HOSTED_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", lab3.AGENT_NAME], cwd=lab3.HOSTED_DIR, check=True)
    accepted["deployment"] = True
    part_b = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("stretch6", "part_b.json"), lab="stretch6", part="b", context=notebook_parts.scope(driver.ENV),
        state={"workflow": info, "delegation": result, "accepted": accepted, "tested_sources": tested_sources},
        evidence=[
            lab_helpers.artifact_path("stretch6", "agents.json"),
            lab_helpers.artifact_path("stretch6", "source_evidence.json"),
            lab_helpers.artifact_path("stretch6", "handoff_packets", "S1.json"),
            lab_helpers.artifact_path("stretch6", "routing_evidence.json"),
            lab_helpers.artifact_path("stretch6", "delegation_evidence.json"),
        ],
    )
