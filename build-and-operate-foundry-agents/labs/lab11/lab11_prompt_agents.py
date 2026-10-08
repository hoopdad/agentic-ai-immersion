# %% [markdown]
# # Lab 11: Platform prompt agents
#
# **Prerequisites:** Lab 6.
#
# Publish prompt agents and run a client-side function-tool turn before inspecting instructions in the portal.
# No workflow agent is created in this lab; Lab 12 uses `FoundryAgent` to connect to these exact versions
# inside a Microsoft Agent Framework Python graph. The model and knowledge tools remain managed by Foundry.
# Publishing versions and executing turns call Azure services and may incur charges.
#
# This cell loads prompt-agent definitions without running the original publishing or workflow exercises.
# %% Step 11.1 - Load platform prompt helpers
from pathlib import Path
import re
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/lab11/lab11_prompt_agents.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/lab11/lab11_prompt_agents.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("prompt-agents-and-workflows/stretch6_prompt_agents.py")

if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted = {}

# %% [markdown]
# This cell publishes only the six platform prompt agents and retains their names, version IDs, and tool contracts.
# %% Step 11.2 - Publish prompt agents only
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("published_prompts", None)
    info = driver.publish_prompt_agents()
    assert "workflow_name" not in info
    assert set(info["agents"]) == set(driver.SPECS)
    assert all(reference.get("agent_id") and reference.get("agent_version") for reference in info["agents"].values())
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "prompt_agents.json"), info)
    accepted["published_prompts"] = True

# %% [markdown]
# This cell demonstrates the concierge's client-side function-tool loop without invoking or creating a workflow.
# %% Step 11.3 - Execute a prompt-agent tool turn
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("function_turn", None)
    assert accepted.get("published_prompts"), "Publish the current prompt references before the tool turn."
    text, calls = driver.run_concierge_turn(
        driver.foundry_env.get_openai_client(),
        lab_helpers.identity_line("P-1001") + " When can I change my Medicare plan?",
    )
    checks = lab_helpers.guardrail_report(text)
    assert calls, "The prompt agent did not exercise the client-side function-tool loop."
    assert checks["no_recommendation"] and checks["no_pii"], checks
    print(text)
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "prompt_turn.json"), {
        "text": text, "calls": calls, "checks": checks,
    })
    accepted["function_turn"] = True

# %% [markdown]
# ## YOUR TURN: change a prompt instruction in the portal
#
# Open the attendee-scoped concierge shown above in Foundry > Agents, add
# `Always greet the participant by first name`, and save the new version.
# The check calls the latest version by name and always restores canonical instructions afterward.
# The restored version ID becomes the durable reference passed to Lab 12.
#
# This cell verifies the portal greeting change and restores the concierge without publishing any workflow.
# %% Step 11.4 - Verify portal instructions
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    accepted.pop("portal", None)
    assert accepted.get("function_turn"), "Complete the current function-tool turn before the portal gate."
    project = driver.foundry_env.get_project_client()
    try:
        portal_text, portal_calls = driver.run_concierge_turn(
            driver.foundry_env.get_openai_client(),
            lab_helpers.identity_line("P-1001") + " When can I change my Medicare plan?",
        )
        portal_checks = lab_helpers.guardrail_report(portal_text)
        assert re.search(r"\bEvelyn\b", portal_text, re.IGNORECASE), "The saved portal version did not greet Evelyn."
        assert portal_checks["no_recommendation"] and portal_checks["no_pii"], portal_checks
    finally:
        restored = driver.create_prompt_version(project, driver.CONCIERGE, driver.INSTRUCTIONS[driver.CONCIERGE])
        info["agents"][driver.CONCIERGE].update(agent_version=restored.version, agent_id=restored.id)
        driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "prompt_agents.json"), info)
    driver.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "portal_evidence.json"), {
        "text": portal_text, "checks": portal_checks, "restored_version": restored.version,
    })
    accepted["portal"] = True

# %% [markdown]
# This cell checkpoints prompt versions and observed evidence for a fresh MAF workflow kernel in Lab 12.
# %% Step 11.5 - Save prompt-agent references
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    lab_helpers.artifact_path("stretch6", "part_b.json").unlink(missing_ok=True)
    assert all(accepted.get(key) for key in ("published_prompts", "function_turn", "portal")), "Complete every current Lab 11 gate."
    part_a = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("stretch6", "part_a.json"), lab="stretch6", part="a", context=notebook_parts.scope(driver.ENV),
        state={"prompt_agents": info, "accepted": accepted},
        evidence=[
            lab_helpers.artifact_path("stretch6", "prompt_agents.json"),
            lab_helpers.artifact_path("stretch6", "prompt_turn.json"),
            lab_helpers.artifact_path("stretch6", "portal_evidence.json"),
        ],
    )
