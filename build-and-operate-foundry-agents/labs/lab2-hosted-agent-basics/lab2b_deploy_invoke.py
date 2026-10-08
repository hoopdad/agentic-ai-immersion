# %% [markdown]
# # Lab 2B: Deploy and invoke your hosted version
#
# Start in a fresh Python 3.14 kernel after Lab 2A. This half validates its local acceptance
# checkpoint and imports definitions only: it does not rerun local scenarios or their exercises.
# Deployment creates a paid Foundry hosted version. You need Project Manager to deploy and
# Agent Consumer or Foundry User to invoke; identity/network failures require administrator help.
#
# This cell initializes helper definitions and configuration independently of the Lab 2A kernel.
# %% Step 2.1 - Import deployment definitions
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
for folder in (WORKSHOP, WORKSHOP / "labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts
import lab_helpers

lab2 = lab_helpers.load_lab_module("lab2-hosted-agent-basics/lab2_hosted_basics.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab2.ARTIFACTS

# %% [markdown]
# This cell rejects missing, differently scoped, changed-evidence or changed-source handoffs before any deployment.
# %% Step 2.2 - Validate local checkpoint
part_a = notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV))
hosted = lab_helpers.require_artifact("lab2", "hosted.json", through=2, caller="lab2B")
if (part_a["state"].get("agent_name") != lab2.AGENT_NAME
        or hosted.get("agent_name") != lab2.AGENT_NAME
        or hosted.get("project_endpoint") != ENV["FOUNDRY_PROJECT_ENDPOINT"]
        or hosted.get("model") != lab_helpers.pick_model(ENV)
        or part_a["state"].get("local_tools") != "passed"
        or part_a["state"].get("instruction_boundary") != "passed"
        or part_a["state"].get("hosted_source_sha256") != hashlib.sha256(
            (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest()):
    raise RuntimeError("Lab 2A source or hosted definition changed; rerun its local acceptance cells.")
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)

# %% [markdown]
# This cell displays the exact tested agent implementation and the validated deployment command for scope and cost review.
# %% Step 2.3 - Review source and deployment plan
print((lab2.HOSTED_DIR / "main.py").read_text(encoding="utf-8"))
print(lab2.deploy_commands(ENV))
print(inspect.getsource(lab2.call_deployed))

# %% [markdown]
# This cell explicitly uploads the saved source package and displays the created hosted version's status.
# %% Step 2.4 - Deploy the hosted agent
subprocess.run(["bash", "-lc", lab2.deploy_commands(ENV)], cwd=lab2.HOSTED_DIR, check=True)
subprocess.run(["azd", "ai", "agent", "show", lab2.AGENT_NAME], cwd=lab2.HOSTED_DIR, check=True)

# %% [markdown]
# Wait for active status in Foundry; enter the actual version rather than assuming version 1.
# A 403 can mean network path or RBAC; a 424 means startup is not ready; inspect the version logs.
# This single-turn check uses `store=False`; it tests inference/tools, not persisted response storage.
#
# This cell selects an explicitly inspected active version and verifies its Responses inference endpoint.
# %% Step 2.5 - Invoke the active version
DEPLOYED_VERSION = ""  # Enter the active version shown after deployment.
assert DEPLOYED_VERSION, "Enter the active Foundry version before invoking."
hosted = lab2.record_deployment(DEPLOYED_VERSION)
result = lab2.call_deployed(
    "Hi, this is P-1005, ZIP 84010. What is my enrollment window?", store=False)
print(result["text"])
assert result["text"].strip(), "The deployed agent returned an empty answer."

# %% [markdown]
# This cell publishes deployed acceptance while preserving the original hosted.json contract consumed by Lab 3A.
# %% Step 2.6 - Publish deployment checkpoint
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab2", part="b", context=notebook_parts.scope(ENV),
    evidence=[lab2.HOSTED_RECORD],
    state={"agent_name": lab2.AGENT_NAME, "deployed_version": DEPLOYED_VERSION,
           "deployed_inference": "passed"})
print("Keep artifacts/lab2/hosted.json. Continue with lab3a_walkthrough.ipynb.")
