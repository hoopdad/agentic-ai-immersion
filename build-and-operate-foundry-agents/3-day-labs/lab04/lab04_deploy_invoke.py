# %% [markdown]
# # Lab 4: Deploy and invoke your hosted version
#
# **Prerequisites:** Lab 3.
# **Required learning/artifacts:** scoped local acceptance, transcript and unchanged Lab 3 source in `lab2/part_a.json`.
# **Recommended route:** core Labs 1-10 in order; next Lab 5. Optional Labs 11 and 13 may branch here.
# **Primary delta / lineage (continue):** deploy the same tested concierge, retaining its sponsor and handoff edits.
# **Acceptance and recovery:** require an actual invocation of the fixed selected version, not just a queued build.
# Changed source requires Lab 3 acceptance again; for startup errors inspect logs, then rerun Steps 4.4-4.6.
# Branches share port 8088, quota and source; run one notebook at a time and review resource cleanup.
#
# Start in a fresh Python 3.14 kernel after Lab 3. This lab validates its local acceptance
# checkpoint and imports definitions only: it does not rerun local scenarios or their exercises.
# Deployment creates a paid Foundry hosted version. You need Project Manager to deploy and
# Agent Consumer or Foundry User to invoke; identity/network failures require administrator help.
#
# This cell initializes helper definitions and configuration independently of the Lab 3 kernel.
# %% Step 4.1 - Import deployment definitions
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
for folder in (WORKSHOP, WORKSHOP / "3-day-labs"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "3-day-labs/artifacts/lab2"
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
INFERENCE_OK = False
lab2 = lab_helpers.load_lab_module("hosted-agent-basics/lab2_hosted_basics.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab2.ARTIFACTS

# %% [markdown]
# This cell rejects missing, differently scoped, changed-evidence or changed-source handoffs before any deployment.
# %% Step 4.2 - Validate local checkpoint
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
    raise RuntimeError("Lab 3 source or hosted definition changed; rerun its local acceptance cells.")

# %% [markdown]
# This cell displays the exact tested agent implementation and the validated deployment command for scope and cost review.
# %% Step 4.3 - Review source and deployment plan
print((lab2.HOSTED_DIR / "main.py").read_text(encoding="utf-8"))
print(lab2.deploy_commands(ENV))
print(inspect.getsource(lab2.call_deployed))

# %% [markdown]
# This cell explicitly uploads the saved source package and displays the created hosted version's status.
# %% Step 4.4 - Deploy the hosted agent
INFERENCE_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab2", part="a", context=notebook_parts.scope(ENV))
if part_a["state"]["hosted_source_sha256"] != hashlib.sha256(
        (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after checkpoint validation; rerun Lab 3 acceptance.")
subprocess.run(["bash", "-lc", lab2.deploy_commands(ENV)], cwd=lab2.HOSTED_DIR, check=True)
subprocess.run(["azd", "ai", "agent", "show", lab2.AGENT_NAME], cwd=lab2.HOSTED_DIR, check=True)

# %% [markdown]
# Wait for active status in Foundry; pin 100% of traffic to that version in the
# version selector, then enter it below (this cell reads routing; it does not change it).
# A 403 can mean network path or RBAC; a 424 means startup is not ready; inspect the version logs.
# This single-turn check uses `store=False`; it tests inference/tools, not persisted response storage.
#
# This cell selects an explicitly inspected active version and verifies its Responses inference endpoint.
# %% Step 4.5 - Invoke the active version
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
# This cell publishes deployed acceptance while preserving the original hosted.json contract consumed by Lab 5.
# %% Step 4.6 - Publish deployment checkpoint
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not INFERENCE_OK:
    raise RuntimeError("Complete the deployed inference check successfully before publishing Lab 4.")
if part_a["state"]["hosted_source_sha256"] != hashlib.sha256(
        (lab2.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Lab 3 source changed after deployment; repeat Labs 3-4 acceptance.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab2", part="b", context=notebook_parts.scope(ENV),
    evidence=[lab2.HOSTED_RECORD],
    state={"agent_name": lab2.AGENT_NAME, "deployed_version": DEPLOYED_VERSION,
           "deployed_inference": "passed", "version_routing": "fixed-100-percent",
           "hosted_source_sha256": part_a["state"]["hosted_source_sha256"]})
print("Keep artifacts/lab2/hosted.json. Continue with lab05_walkthrough.ipynb.")
