# %% [markdown]
# # Lab 11: Prompt versus hosted
#
# **Prerequisites:** Lab 4 (learning and accepted deployed Responses evidence).
# **Recommended route:** finish core Labs 1-10, then this optional 10-15 minute comparison.
#
# Lab 4 owns Python, packaging, hosting and tool execution. Here Foundry owns one minimal
# `PromptAgentDefinition` and its immutable instruction version; no container is deployed.
# This is a terminal branch: no later lab consumes its agent or evidence. No knowledge,
# six-agent ensemble, MAF graph or portal edit/restore is required.
# Publishing one version, pinning this terminal name endpoint and invoking it calls Azure and may incur charges.
# [Prompt API](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/prompt-agent)
# and [version routing](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent)
# are checked against the installed root SDK pins; no project-wide routing is changed.
#
# This cell restores the accepted Lab 4 scope without replaying deployment.
# %% Step 11.1 - Restore the hosted comparison
# ruff: noqa: F704
from pathlib import Path
import sys

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/3-day-labs/lab11/lab11_prompt_agents.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/3-day-labs/lab11/lab11_prompt_agents.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "3-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("prompt-agents-and-workflows/stretch6_prompt_agents.py")
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    accepted = {}
    hosted_checkpoint = notebook_parts.read_checkpoint(
        lab_helpers.artifact_path("lab2", "part_b.json"), lab="lab2", part="b",
        context=notebook_parts.scope(driver.ENV),
    )
    assert hosted_checkpoint["state"].get("deployed_inference") == "passed", "Rerun Lab 4 deployed inference."
    print(hosted_checkpoint["state"])
    print(driver.INSTRUCTIONS)

# %% [markdown]
# ## YOUR TURN: predict ownership and the boundary
#
# Before running, explain which runtime would execute your Python tool in Lab 4
# and why this tool-free Prompt Agent cannot look up participant-specific facts.
# Edit the question below, asking for a plan choice; predict an advisor handoff rather
# than a recommendation. Do not add participant PII, tools, knowledge or another agent.
#
# This cell publishes one version and invokes that exact Prompt Agent once.
# %% Step 11.2 - Publish and invoke one Prompt Agent
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    accepted.pop("comparison", None)
    QUESTION = "Which healthcare plan should I choose, and who can help me decide?"
    info = await driver.publish_and_invoke(driver.ENV, QUESTION)
    checks = lab_helpers.guardrail_report(info["text"])
    assert checks["no_recommendation"] and checks["no_pii"], checks
    assert "advisor" in info["text"].lower(), "The choice boundary requires an advisor."
    print(info["text"])
    lab_helpers.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "prompt_agents.json"), {
        key: info[key] for key in ("agent_name", "agent_version", "agent_id", "terminal")
    })
    lab_helpers.foundry_env.save_artifact(lab_helpers.artifact_path("stretch6", "prompt_turn.json"), {
        "question": QUESTION, "text": info["text"], "response_id": info["response_id"], "checks": checks,
    })
    accepted["comparison"] = True

# %% [markdown]
# This cell publishes terminal comparison evidence without changing any hosted or release reference.
# %% Step 11.3 - Save the terminal comparison
if "__file__" not in globals():
    lab_helpers.artifact_path("stretch6", "part_a.json").unlink(missing_ok=True)
    assert accepted.get("comparison"), "Complete the one-version, one-turn comparison first."
    part_a = notebook_parts.write_checkpoint(
        lab_helpers.artifact_path("stretch6", "part_a.json"), lab="stretch6", part="a",
        context=notebook_parts.scope(driver.ENV),
        state={"prompt_comparison": info, "accepted": accepted, "terminal": True},
        evidence=[lab_helpers.artifact_path("stretch6", "prompt_agents.json"),
                  lab_helpers.artifact_path("stretch6", "prompt_turn.json")],
    )
    print("No downstream consumer. Missing or changed evidence: rerun Lab 11; never replay it for Lab 12.")

# %% [markdown]
# Review attendee-owned resources using the workshop cleanup dry run; no notebook-owned
# server was started. Select [Lab 12](../lab12/README.md) only after both Labs 8 and 9,
# or [Lab 13](../lab13/README.md) after Lab 4; neither requires this comparison.
