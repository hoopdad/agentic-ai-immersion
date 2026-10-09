# %% [markdown]
# # Lab 4: Build, test, deploy, and invoke a hosted agent
#
# **Prerequisites:** Lab 2. No separate Lab 3 notebook or checkpoint is required.
# **One-day route:** Lab 1 -> Lab 2 -> Lab 4 -> Lab 7 team capstone.
# This condensed lab includes Lab 3's real local acceptance before Lab 4's deployment.
# Edit the isolated product in `../products/hosted-agent-basics/hosted/main.py`.
# Preserve sponsor facts, the enrollment-window refusal, and source fingerprints.
# Local model calls and hosted deployment incur charges; review each explicit action.
# Recovery: rerun the local gates after source changes, never fabricate their checkpoint.
#
# This cell imports the existing definitions without replaying their notebook demonstrations.
# %% Step 4.1 - Import local definitions
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

HERE = Path.cwd().resolve()
REPO_ROOT = next(p for p in (HERE, *HERE.parents)
                 if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file())
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
for folder in (WORKSHOP, WORKSHOP / "1-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, marketplace_data, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "1-day-labs/artifacts/lab2"
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
BASELINE_OK = SPONSOR_OK = INSTRUCTION_OK = False
TESTED_SOURCE_SHA256 = None
lab2 = lab_helpers.load_lab_module("hosted-agent-basics/lab2_hosted_basics.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab2.ARTIFACTS

# %% [markdown]
# This cell checks the original Labs 1-2 inference evidence and binds it to this kernel's project, suffix and deployments.
# %% Step 4.2 - Validate project prerequisite
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
project = lab_helpers.require_artifact("lab1", "project.json", through=1, caller="Lab 4")
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
# %% Step 4.3 - Inspect tools and instructions
hosted_source = (lab2.HOSTED_DIR / "main.py").read_text(encoding="utf-8")
print(hosted_source)
profile = marketplace_data.get_participant("P-1001")
window = marketplace_data.get_enrollment_window("P-1001")
account = marketplace_data.get_hra_account("P-1001")
print(json.dumps({"participant": profile, "window": window, "account": account}, indent=2))
assert profile, "The participant fixture must exist before asking the model."

# %% [markdown]
# This cell prepares only the local flat package and displays the Responses client contract that will call it.
# %% Step 4.4 - Prepare local package
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
hosted = lab2.build()
print(json.dumps(hosted, indent=2))
print(inspect.getsource(lab2.post_responses))

# %% [markdown]
# This cell runs the two local baseline scenarios and saves redacted transcripts without deploying.
# %% Step 4.5 - Run local concierge scenarios
BASELINE_OK = False
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
lab2.demo()
BASELINE_OK = True

# %% [markdown]
# ## YOUR TURN: add a sponsor tool
#
# Edit `../products/hosted-agent-basics/hosted/main.py`: wrap `marketplace_data.get_sponsor(sponsor_id)` with `@tool`
# following the existing tools, then append it to `TOOLS`. Save your file before continuing.
# The answer must name Northwind and its $3,600 annual HRA, not invent a recommendation.
#
# This cell vendors your saved tool change and asserts its answer through a fresh local process.
# %% Step 4.6 - Test the sponsor tool
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
# Edit rule 3 of `ROLE_INSTRUCTIONS` in `../products/hosted-agent-basics/hosted/main.py` so the advisor handoff always
# names the applicable enrollment window. Save it, then test the recommendation-refusal turn.
#
# This cell starts a fresh local agent and verifies that its S1 refusal names AEP.
# %% Step 4.7 - Test the instruction change
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
# %% Step 4.8 - Publish local checkpoint
(ARTIFACTS / "part_a.json").unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not (BASELINE_OK and SPONSOR_OK and INSTRUCTION_OK):
    raise RuntimeError("Complete all local acceptance cells successfully before publishing this local phase.")
if TESTED_SOURCE_SHA256 != hashlib.sha256((lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after acceptance; rerun the local tests before publishing.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV),
    evidence=[lab2.TRANSCRIPTS],
    state={"agent_name": hosted["agent_name"], "local_tools": "passed",
           "instruction_boundary": "passed",
           "hosted_source_sha256": TESTED_SOURCE_SHA256})
print("Local acceptance passed. Continue below to deploy this exact source.")

# %% [markdown]
# This cell validates the just-tested local phase before deployment; it does not rerun cloud setup.
# %%
# Step 4.9 - Validate local checkpoint
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
part_a = notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV))
hosted = lab_helpers.require_artifact("lab2", "hosted.json", through=2, caller="Lab 4")
if (part_a["state"].get("agent_name") != lab2.AGENT_NAME
        or hosted.get("agent_name") != lab2.AGENT_NAME
        or hosted.get("project_endpoint") != ENV["FOUNDRY_PROJECT_ENDPOINT"]
        or hosted.get("model") != lab_helpers.pick_model(ENV)
        or part_a["state"].get("local_tools") != "passed"
        or part_a["state"].get("instruction_boundary") != "passed"
        or part_a["state"].get("hosted_source_sha256") != hashlib.sha256(
            (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest()):
    raise RuntimeError("Local source or hosted definition changed; rerun the local acceptance cells above.")

# %% [markdown]
# This cell displays the exact tested agent implementation and the validated deployment command for scope and cost review.

# %%
# Step 4.10 - Review source and deployment plan
print((lab2.HOSTED_DIR / "main.py").read_text(encoding="utf-8"))
print(lab2.deploy_commands(ENV))
print(inspect.getsource(lab2.call_deployed))

# %% [markdown]
# This cell explicitly uploads the saved source package and displays the created hosted version's status.

# %%
# Step 4.11 - Deploy the hosted agent
INFERENCE_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV))
if part_a["state"]["hosted_source_sha256"] != hashlib.sha256(
        (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after checkpoint validation; rerun this lab's local phase acceptance.")
subprocess.run(["bash", "-lc", lab2.deploy_commands(ENV)], cwd=lab2.HOSTED_DIR, check=True)
subprocess.run(["azd", "ai", "agent", "show", lab2.AGENT_NAME], cwd=lab2.HOSTED_DIR, check=True)

# %% [markdown]
# Wait for active status in Foundry; pin 100% of traffic to that version in the
# version selector, then enter it below (this cell reads routing; it does not change it).
# A 403 can mean network path or RBAC; a 424 means startup is not ready; inspect the version logs.
# This single-turn check uses `store=False`; it tests inference/tools, not persisted response storage.
#
# This cell selects an explicitly inspected active version and verifies its Responses inference endpoint.

# %%
# Step 4.12 - Invoke the active version
INFERENCE_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
DEPLOYED_VERSION = ""  # Enter the active version shown after deployment.
assert DEPLOYED_VERSION, "Enter the active Foundry version before invoking."
lab2.require_pinned_version(lab2.AGENT_NAME, DEPLOYED_VERSION)
hosted = lab2.record_deployment(DEPLOYED_VERSION)
result = lab2.call_deployed(
    f"{lab_helpers.identity_line('P-1001')} Who is my sponsor and how much is the annual HRA?", store=False)
print(result["text"])
assert "Northwind" in result["text"] and "$3,600" in result["text"], (
    "The deployed version must retain the accepted sponsor tool, not merely return nonempty prose."
)
lab2.require_pinned_version(lab2.AGENT_NAME, DEPLOYED_VERSION)
INFERENCE_OK = True

# %% [markdown]
# This cell publishes deployed acceptance while preserving the original hosted.json contract available to the optional extension.

# %%
# Step 4.13 - Publish deployment checkpoint
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not INFERENCE_OK:
    raise RuntimeError("Complete the deployed inference check successfully before publishing Lab 4.")
if part_a["state"]["hosted_source_sha256"] != hashlib.sha256(
        (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Local source changed after deployment; repeat this lab's local and deployed acceptance.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab2", part="b", context=notebook_parts.scope(ENV),
    evidence=[lab2.HOSTED_RECORD],
    state={"agent_name": lab2.AGENT_NAME, "deployed_version": DEPLOYED_VERSION,
           "deployed_inference": "passed", "version_routing": "fixed-100-percent",
           "hosted_source_sha256": part_a["state"]["hosted_source_sha256"]})
print("Keep artifacts/lab2/hosted.json. Continue with lab07_walkthrough.ipynb to build and host a multi-agent team.")
