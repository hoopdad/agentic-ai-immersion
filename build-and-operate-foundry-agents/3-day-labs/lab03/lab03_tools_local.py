# %% [markdown]
# # Lab 3: Tools and a locally hosted concierge
#
# **Prerequisites:** Lab 2.
# **Required learning/artifacts:** verified project/model scope in `lab1/project.json` and `part_b.json`.
# **Recommended route:** core Labs 1-10 in order; next Lab 4.
# **Primary delta / lineage:** build the first concierge product with typed tools; deployment is out of scope.
# **Acceptance and recovery:** sponsor facts and an AEP-named recommendation refusal are required, not optional exercises.
# Rerun Lab 2 for scope failures or Steps 3.4-3.8 after source edits. Stop only this notebook's owned process.
# Lab 4 continues this source; Lab 5 transfers only the accepted sponsor tool and enrollment handoff policy.
#
# Start in a fresh dev-container Python 3.14 kernel after Lab 2. Learn the tool boundary,
# inspect the actual agent definition, and test local Responses calls. Local inference calls Azure
# models and incurs charges, but this lab never deploys a hosted agent or creates a cloud version.
# The original driver is an internal helper module, not another notebook to execute.
#
# This cell imports the existing definitions without replaying their notebook demonstrations.
# %% Step 3.1 - Import local definitions
import hashlib
import inspect
import json
from pathlib import Path
import sys

HERE = Path.cwd().resolve()
REPO_ROOT = next(p for p in (HERE, *HERE.parents)
                 if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file())
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
for folder in (WORKSHOP, WORKSHOP / "3-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, marketplace_data, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "3-day-labs/artifacts/lab2"
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
BASELINE_OK = SPONSOR_OK = INSTRUCTION_OK = False
TESTED_SOURCE_SHA256 = None
lab2 = lab_helpers.load_lab_module("hosted-agent-basics/lab2_hosted_basics.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab2.ARTIFACTS

# %% [markdown]
# This cell checks the original Labs 1-2 inference evidence and binds it to this kernel's project, suffix and deployments.
# %% Step 3.2 - Validate project prerequisite
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
project = lab_helpers.require_artifact("lab1", "project.json", through=1, caller="Lab 3")
if project.get("provisioning_state") != "Succeeded" or any(
        project.get("smoke_tests", {}).get(model) != "passed" for model in ("chat", "embedding")):
    raise RuntimeError("Complete Lab 2's model smoke tests before continuing.")
checkpoint_config = {
    "PROJECT_RESOURCE_ID": project.get("project_resource_id"),
    "FOUNDRY_PROJECT_ENDPOINT": project.get("project_endpoint"),
    "TENANT_ID": project.get("tenant_id"),
    "MARKETPLACE_RESOURCE_SUFFIX": project.get("resource_suffix"),
    "AZURE_AI_MODEL_DEPLOYMENT_NAME": project.get("chat_deployment", {}).get("name"),
    "EMBEDDING_MODEL_DEPLOYMENT_NAME": project.get("embedding_deployment", {}).get("name"),
}
if any(not value or value != ENV.get(key) for key, value in checkpoint_config.items()):
    raise RuntimeError("Lab 2 project checkpoint does not match the current configuration.")

# %% [markdown]
# This cell reads the real tool and agent implementation and contrasts authoritative participant data with model-generated prose.
# %% Step 3.3 - Inspect tools and instructions
hosted_source = (lab2.HOSTED_DIR / "main.py").read_text(encoding="utf-8")
print(hosted_source)
profile = marketplace_data.get_participant("P-1001")
window = marketplace_data.get_enrollment_window("P-1001")
account = marketplace_data.get_hra_account("P-1001")
print(json.dumps({"participant": profile, "window": window, "account": account}, indent=2))
assert profile, "The participant fixture must exist before asking the model."

# %% [markdown]
# This cell prepares only the local flat package and displays the Responses client contract that will call it.
# %% Step 3.4 - Prepare local package
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
hosted = lab2.build()
print(json.dumps(hosted, indent=2))
print(inspect.getsource(lab2.post_responses))

# %% [markdown]
# This cell runs the two local baseline scenarios and saves redacted transcripts without deploying.
# %% Step 3.5 - Run local concierge scenarios
BASELINE_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
lab2.demo()
BASELINE_OK = True

# %% [markdown]
# ## YOUR TURN: add a sponsor tool
#
# Edit `../../shared/hosted-agent-basics/hosted/main.py`: wrap `marketplace_data.get_sponsor(sponsor_id)` with `@tool`
# following the existing tools, then append it to `TOOLS`. Save your file before continuing.
# The answer must name Northwind and its $3,600 annual HRA, not invent a recommendation.
#
# This cell vendors your saved tool change and asserts its answer through a fresh local process.
# %% Step 3.6 - Test the sponsor tool
SPONSOR_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
lab2.build()
server = lab2.HostedProcess().start()
try:
    result = lab2.post_responses(
        lab2.LOCAL_BASE, f"{lab_helpers.identity_line('P-1001')} "
        "Who is my plan sponsor and how much is the HRA for the year?")
    print(result["text"])
    assert "Northwind" in result["text"], "The answer must name the sponsor."
    assert "$3,600" in result["text"], "The answer must use the sponsor's annual HRA amount."
    SPONSOR_OK = True
finally:
    server.stop()

# %% [markdown]
# ## YOUR TURN: tighten the instruction boundary
#
# Edit rule 3 of `ROLE_INSTRUCTIONS` in `../../shared/hosted-agent-basics/hosted/main.py` so the advisor handoff always
# names the applicable enrollment window. Save it, then test the recommendation-refusal turn.
#
# This cell starts a fresh local agent and verifies that its S1 refusal names AEP.
# %% Step 3.7 - Test the instruction change
INSTRUCTION_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
hosted = lab2.build()
TESTED_SOURCE_SHA256 = hashlib.sha256((lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest()
server = lab2.HostedProcess().start()
try:
    send = lambda text, **kwargs: lab2.post_responses(lab2.LOCAL_BASE, text, **kwargs)
    turns = lab2.run_scenario("S1", lab2.SCENARIOS["S1"], send)
    lab2.write_transcripts({"S1": turns}, f"local {lab2.LOCAL_BASE}")
    assert "AEP" in turns[1]["agent"], "The recommendation refusal must name AEP."
    INSTRUCTION_OK = True
finally:
    server.stop()

# %% [markdown]
# This cell records local acceptance and the exact tested hosted source so a fresh Lab 4 cannot silently deploy a changed implementation.
# %% Step 3.8 - Publish local checkpoint
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not (BASELINE_OK and SPONSOR_OK and INSTRUCTION_OK):
    raise RuntimeError("Complete all local acceptance cells successfully before publishing Lab 3.")
if TESTED_SOURCE_SHA256 != hashlib.sha256((lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after acceptance; rerun the local tests before publishing.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV),
    evidence=[lab2.TRANSCRIPTS],
    state={"agent_name": hosted["agent_name"], "local_tools": "passed",
           "instruction_boundary": "passed",
           "hosted_source_sha256": TESTED_SOURCE_SHA256})
print("Lab 3 complete. Open lab04_walkthrough.ipynb in a fresh kernel to deploy.")
