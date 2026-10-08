# %% [markdown]
# # Lab 3B: Durable sessions and resiliency
#
# Start in a fresh Python 3.14 kernel after Lab 3A. Reuse its knowledge and hosted artifacts:
# there are no Search/index/connection build operations in this half. Prove local process-restart
# continuity, deliberately break persistence, and distinguish shared history from container files.
# Deployment belongs to this half and is an explicit paid operation after the local evidence.
#
# This cell imports session definitions independently without replaying provisioning or knowledge demonstrations.
# %% Step 3.1 - Import session definitions
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path.cwd().resolve()
REPO_ROOT = next(p for p in (HERE, *HERE.parents)
                 if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file())
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
for folder in (WORKSHOP, WORKSHOP / "labs", WORKSHOP / "labs/lab3-hosted-knowledge-sessions"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts
import lab_helpers

ARTIFACTS = WORKSHOP / "labs/artifacts/lab3"
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
CONTINUITY_OK = BROKEN_STORE_OK = SHARED_SCALE_OK = DEPLOYED_CITATION_OK = False
shared_scale = None
lab3 = lab_helpers.load_lab_module("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py")
ENV = foundry_env.load_env()
ARTIFACTS = lab3.ARTIFACTS

# %% [markdown]
# This cell validates the scoped knowledge checkpoint, artifact fingerprint and tested hosted implementation without recreating resources.
# %% Step 3.2 - Validate existing knowledge
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
part_a = notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab3", part="a", context=notebook_parts.scope(ENV))
knowledge = lab_helpers.require_artifact("lab3", "knowledge.json", through=3, caller="lab3B")
hosted = lab_helpers.require_artifact("lab3", "hosted.json", through=3, caller="lab3B")
if (part_a["state"].get("agent_name") != lab3.AGENT_NAME
        or hosted.get("agent_name") != lab3.AGENT_NAME
        or hosted.get("model") != lab_helpers.pick_model(ENV)
        or not ENV.get("AZURE_AI_SEARCH_ENDPOINT")
        or knowledge.get("search_endpoint", "").rstrip("/") != ENV["AZURE_AI_SEARCH_ENDPOINT"].rstrip("/")
        or not knowledge.get("mcp_endpoint")
        or hosted.get("env_for_container", {}).get("MARKETPLACE_KB_MCP_URL") != knowledge.get("mcp_endpoint")
        or part_a["state"].get("citations") != "passed"
        or part_a["state"].get("knowledge_boundary") != "passed"
        or part_a["state"].get("hosted_source_sha256") != hashlib.sha256(
            (lab3.HOSTED_DIR / "main.py").read_bytes()).hexdigest()):
    raise RuntimeError("Lab 3A knowledge/source acceptance no longer matches this configuration.")
if not (lab3.HOSTED_DIR / "common").is_dir():
    raise RuntimeError("Lab 3A's prepared package is missing; restore it in Lab 3A before continuing.")

# %% [markdown]
# This cell inspects the actual session request, stable conversation identifier and restart implementation before exercising them.
# %% Step 3.3 - Inspect the durability boundary
print(inspect.getsource(lab3.ask))
print(inspect.getsource(lab3.demo))
print((WORKSHOP / "common/message_store.py").read_text(encoding="utf-8"))
print(json.dumps(hosted["session_behavior"], indent=2))

# %% [markdown]
# This cell runs the existing resource-backed conversation across two different local processes and asserts retained medication context.
# %% Step 3.4 - Prove process-restart continuity
CONTINUITY_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab3", part="a", context=notebook_parts.scope(ENV))
continuity = lab3.demo(knowledge=knowledge, session_id=f"history-{uuid.uuid4().hex[:8]}", restart=True)
assert continuity["continuity_ok"], "The restarted process did not recall the original medication."
assert len(continuity["pids"]) >= 2, "The demo must actually restart the Python process."
CONTINUITY_OK = True

# %% [markdown]
# This cell deliberately gives the restarted process an empty file store and verifies that the remembered medication disappears.
# %% Step 3.5 - Break persistence deliberately
BROKEN_STORE_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
print(inspect.getsource(lab3.broken_store_acceptance_gate))
lab3.broken_store_acceptance_gate(knowledge)
BROKEN_STORE_OK = True

# %% [markdown]
# Shared history needs either existing Azure Blob with appropriate identity RBAC or the dev-container
# Azurite emulator. Files prove only local process continuity, not scale-out or version-roll durability.
# No container/key/SAS is created here, and local Azurite configuration is never uploaded to Foundry.
#
# This cell tests shared-store replicas when configured and otherwise records an explicit unproven scale-out result.
# %% Step 3.6 - Test shared-store scale-out
SHARED_SCALE_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
shared_scale = "not proven: no shared Blob/Azurite backend"
if ENV.get("MARKETPLACE_BLOB_STORAGE_URL") or ENV.get("MARKETPLACE_AZURITE_CONNECTION_STRING"):
    lab3.scale_out_acceptance_gate(knowledge)
    shared_scale = "passed"
else:
    print("SKIPPED: cross-replica history is NOT proven; configure Blob or Azurite for this exercise.")
SHARED_SCALE_OK = True

# %% [markdown]
# This cell reviews deployment settings and explicitly deploys the already-built knowledge/session package without rebuilding Search.
# %% Step 3.7 - Deploy the session-enabled version
DEPLOYED_CITATION_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab3", part="a", context=notebook_parts.scope(ENV))
if part_a["state"]["hosted_source_sha256"] != hashlib.sha256(
        (lab3.HOSTED_DIR / "main.py").read_bytes()).hexdigest():
    raise RuntimeError("Hosted source changed after checkpoint validation; rerun Lab 3A acceptance.")
print(lab3.deploy_commands(ENV, hosted))
subprocess.run(["bash", "-lc", lab3.deploy_commands(ENV, hosted)], cwd=lab3.HOSTED_DIR, check=True)
subprocess.run(["azd", "ai", "agent", "show", lab3.AGENT_NAME], cwd=lab3.HOSTED_DIR, check=True)

# %% [markdown]
# This cell records the inspected active version and verifies its governed citation without claiming deployment proves session durability.
# %% Step 3.8 - Verify the deployed version
DEPLOYED_CITATION_OK = False
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
DEPLOYED_VERSION = ""  # Enter the active version displayed after deployment.
assert DEPLOYED_VERSION, "Enter the active Foundry version before invoking."
hosted = lab3.record_deployment(DEPLOYED_VERSION)
lab2 = lab_helpers.load_lab_module("lab2-hosted-agent-basics/lab2_hosted_basics.py")
reply = lab2.call_deployed("What proof of payment do you accept for a premium claim?", store=False)
print(reply["text"])
assert "[KB-ACC-001]" in reply["text"], "The deployed answer must cite governed knowledge."
DEPLOYED_CITATION_OK = True

# %% [markdown]
# This cell publishes distinct restart, broken-store, shared-scale and deployment evidence for downstream Lab 4A.
# %% Step 3.9 - Publish session checkpoint
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if not (CONTINUITY_OK and BROKEN_STORE_OK and SHARED_SCALE_OK and DEPLOYED_CITATION_OK):
    raise RuntimeError("Complete session and deployed acceptance successfully before publishing Lab 3B.")
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab3", part="b", context=notebook_parts.scope(ENV),
    evidence=[ARTIFACTS / "knowledge.json", lab3.HOSTED_RECORD, lab3.TRANSCRIPT_PATH],
    state={"restart_continuity": "passed", "broken_store": "passed",
           "shared_scale": shared_scale, "deployed_version": DEPLOYED_VERSION,
           "deployed_citation": "passed"})
print("Retain knowledge.json, hosted.json, sessions and transcripts. Continue with Lab 4A.")
