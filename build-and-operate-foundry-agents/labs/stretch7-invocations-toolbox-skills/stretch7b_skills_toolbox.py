# %% [markdown]
# # Stretch 7B: Skills and optional Toolbox
#
# Start a fresh kernel after Stretch 7A and keep its batch evidence without replaying Invocations.
# Build the conversational Skills host, verify governed skill use, and deploy only the Responses package.
# Toolbox is an optional administrator-provided preview endpoint, not an unvalidated resource created by this notebook.
# Local skill turns and Azure deployment may incur charges.
#
# This cell loads A's batch checkpoint and Skills definitions without building or invoking the batch host.
# %% Step S7.1 - Load the completed batch prerequisite
from pathlib import Path
import os
import subprocess
import sys
from urllib.parse import urlsplit

SOURCE_PATH = Path(__file__).resolve() if "__file__" in globals() else next(
    parent / "build-and-operate-foundry-agents/labs/stretch7-invocations-toolbox-skills/stretch7b_skills_toolbox.py"
    for parent in (Path.cwd(), *Path.cwd().parents)
    if (parent / "build-and-operate-foundry-agents/labs/stretch7-invocations-toolbox-skills/stretch7b_skills_toolbox.py").is_file()
)
ROOT = SOURCE_PATH.parents[2]
for folder in (ROOT, ROOT / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import lab_helpers
from common import notebook_parts

driver = lab_helpers.load_lab_module("stretch7-invocations-toolbox-skills/stretch7_invocations.py")

if "__file__" not in globals():
    part_a = notebook_parts.read_checkpoint(
        driver.ARTIFACTS / "part_a.json", lab="stretch7", part="a", context=notebook_parts.scope(driver.ENV),
    )
    assert part_a["state"]["nightly"]["reviews"] > 0

# %% [markdown]
# This cell validates optional Toolbox inputs and local skill selection while leaving empty SKILL_NAMES to include every local skill.
# %% Step S7.2 - Configure governed Skills and Toolbox
def validate_config(toolbox_name: str, toolbox_url: str, skill_names: str) -> dict[str, str]:
    name, url = toolbox_name.strip(), toolbox_url.strip()
    if bool(name) != bool(url):
        raise ValueError("Configure both TOOLBOX_NAME and TOOLBOX_MCP_URL, or leave both blank.")
    if url:
        endpoint = urlsplit(url)
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password \
                or endpoint.query or endpoint.fragment:
            raise ValueError("TOOLBOX_MCP_URL must be an HTTPS endpoint without credentials or query strings.")
    selected = [item.strip() for item in skill_names.split(",") if item.strip()]
    available = {path.parent.name for path in driver.SKILLS_SRC.glob("*/SKILL.md")}
    if set(selected) - available:
        raise ValueError("SKILL_NAMES must name local workshop skills: " + ", ".join(sorted(set(selected) - available)))
    return {"TOOLBOX_NAME": name, "TOOLBOX_MCP_URL": url, "SKILL_NAMES": ",".join(selected)}


if "__file__" not in globals():
    TOOLBOX_NAME = ""  # Optional administrator-provided Toolbox name.
    TOOLBOX_MCP_URL = ""  # Optional HTTPS MCP endpoint without credentials.
    SKILL_NAMES = ""  # Blank automatically includes every local workshop skill.
    config = validate_config(TOOLBOX_NAME, TOOLBOX_MCP_URL, SKILL_NAMES)
    os.environ.update(config)
    driver.ENV.update(config)

# %% [markdown]
# This cell prepares only the conversational package and verifies its first governed skill answer without invoking batch processing.
# %% Step S7.3 - Exercise the first governed skill
if "__file__" not in globals():
    record = driver.build(protocols=("responses_skills",))
    skill_text = driver.skills_demo()
    assert "[KB-ACC-001]" in skill_text, "The skill answer must cite its governed source."
    checks = lab_helpers.guardrail_report(skill_text)
    assert checks["no_recommendation"] and checks["no_pii"], checks
    first_skill_log = (driver.ARTIFACTS / "hosted-responses-skills_local.log").read_text(encoding="utf-8", errors="replace")
    assert "read_skill name=" in first_skill_log, "The model did not read a local skill."

# %% [markdown]
# ## YOUR TURN: add a second local skill
#
# Create `skills/debit-card-faq/SKILL.md` from `data/knowledge/debit-card-faq.md`.
# Set frontmatter `name: debit-card-faq` and `source_doc: KB-ACC-002`; cover declined, blocked,
# and lost cards and explicitly say `Never read, request or record the full card number`.
# Leave `SKILL_NAMES` blank to include newly added local skills automatically, or include this name in your explicit selection.
#
# This cell rebuilds only the Skills host and requires the debit-card answer to cite its source and actually read the new skill.
# %% Step S7.4 - Verify the second skill
if "__file__" not in globals():
    second_skill_text = driver.second_skill_acceptance_gate(protocols=("responses_skills",))
    second_checks = lab_helpers.guardrail_report(second_skill_text)
    assert second_checks["no_recommendation"] and second_checks["no_pii"], second_checks
    driver.foundry_env.save_artifact(driver.ARTIFACTS / "skills_evidence.json", {
        "first": skill_text, "second": second_skill_text, "checks": second_checks,
        "toolbox": config["TOOLBOX_NAME"] or None,
        "toolbox_executed": False,  # Configuration alone is not proof of a Toolbox tool invocation.
        "second_skill_source": driver.validate_second_skill_source().read_text(encoding="utf-8"),
    })

# %% [markdown]
# This cell deploys only the Responses Skills package using validated configuration and records completed deployment-command evidence.
# %% Step S7.5 - Deploy Skills and optional Toolbox configuration
if "__file__" not in globals():
    from deployment import bash_deploy_block
    settings = dict(config)
    settings["SKILL_NAMES"] = settings["SKILL_NAMES"] or ",".join(
        sorted(path.parent.name for path in driver.SKILLS_SRC.glob("*/SKILL.md"))
    )
    settings = {key: value for key, value in settings.items() if value}
    command = bash_deploy_block(
        driver.SKILLS_HOST_DIR, driver.SKILLS_AGENT, "responses", driver.ENV,
        settings=settings, check_package=True,
    )
    subprocess.run(["bash", "-lc", command], cwd=driver.SKILLS_HOST_DIR, check=True)
    subprocess.run(["azd", "ai", "agent", "show", driver.SKILLS_AGENT], cwd=driver.SKILLS_HOST_DIR, check=True)
    part_b = notebook_parts.write_checkpoint(
        driver.ARTIFACTS / "part_b.json", lab="stretch7", part="b", context=notebook_parts.scope(driver.ENV),
        state={"skills": record["agents"]["responses_skills"], "deployment_command_completed": True},
        evidence=[
            driver.RECORD, driver.ARTIFACTS / "skills_transcript.md",
            driver.ARTIFACTS / "skills_evidence.json",
        ],
    )
