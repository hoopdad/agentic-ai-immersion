# %% [markdown]
# # Lab 1B: Deploy models, verify inference, and publish configuration
#
# Start in a fresh Python 3.14 kernel after Lab 1A. This half reads its handoff and checks
# the current approved Azure context and live project ownership; it never creates a project.
# Model deployments belong to the shared account: review quota, SKU capacity and charges first.
#
# This cell imports helpers and locates the durable Lab 1A handoff.
# %% Step 1.1 - Import model helpers
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

HERE = Path.cwd().resolve()
REPO_ROOT = next(p for p in (HERE, *HERE.parents)
                 if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file())
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
LAB_DIR = WORKSHOP / "labs/lab1-foundry-project-models"
for folder in (WORKSHOP, LAB_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, notebook_parts, resource_names
import project_setup

CLI = project_setup.AzureCLI()
ARTIFACTS = WORKSHOP / "labs/artifacts/lab1"
ARTIFACT = ARTIFACTS / "project.json"
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
SMOKE_TESTS = {}
SMOKE_TARGET = None

# %% [markdown]
# This cell records independently approved scope inputs and optional downstream settings rather than trusting a cached environment.
# %% Step 1.2 - Edit approved context and downstream inputs
SUBSCRIPTION_ID = ""  # Approved subscription GUID displayed by Lab 1A.
TENANT_ID = ""  # Approved tenant GUID displayed by Lab 1A.
ATTENDEE_SUFFIX = ""  # Your suffix, not another attendee's.
AZURE_AI_SEARCH_ENDPOINT = ""
MARKETPLACE_BLOB_STORAGE_URL = ""  # Existing account URL, never SAS or a connection string.
MARKETPLACE_BLOB_STORAGE_CONTAINER = ""
APPLICATIONINSIGHTS_CONNECTION_STRING = ""
MARKETPLACE_TODAY = "2026-10-06"

# %% [markdown]
# This cell reads the checkpoint, rechecks current identity and live project ownership, and lists account model capabilities without writes.
# %% Step 1.3 - Validate handoff and discover models
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
HANDOFF, CONTEXT, ACCOUNT, PROJECT = project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
SUFFIX = HANDOFF["resource_suffix"]
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
PROJECT_CONTEXT = {
    "subscription_id": CONTEXT["subscription_id"].lower(), "tenant_id": CONTEXT["tenant_id"].lower(),
    "account_resource_id": ACCOUNT["id"].lower(), "project_resource_id": PROJECT["id"].lower(),
    "resource_suffix": SUFFIX,
}
part_a = notebook_parts.read_checkpoint(
    ARTIFACTS / "part_a.json", lab="lab1", part="a", context=PROJECT_CONTEXT)
MODELS = CLI.items(ACCOUNT["id"] + "/models")
print(json.dumps([m for m in MODELS if m.get("format") == "OpenAI"
                  and (m.get("name", "").startswith("gpt-")
                       or m.get("name") == "text-embedding-3-large")], indent=2))

# %% [markdown]
# This cell selects live model versions and advertised SKUs and displays the cost-bearing deployment plan.
# %% Step 1.4 - Review the model plan
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
CHAT_MODEL = "gpt-5.4-mini"
CHAT_VERSION = ""
CHAT_SKU = "GlobalStandard"
CHAT_CAPACITY = 10
EMBEDDING_VERSION = ""
EMBEDDING_SKU = "Standard"
EMBEDDING_CAPACITY = 1
APPROVE_PROVISIONING = False
CHAT_SPEC = project_setup.choose_model(MODELS, CHAT_MODEL, CHAT_VERSION, CHAT_SKU, CHAT_CAPACITY)
EMBEDDING_SPEC = project_setup.choose_model(
    MODELS, "text-embedding-3-large", EMBEDDING_VERSION, EMBEDDING_SKU, EMBEDDING_CAPACITY)
CHAT_NAME = resource_names.name("marketplace-chat", {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)
EMBEDDING_NAME = resource_names.name("marketplace-embedding", {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)
print(json.dumps({"context": CONTEXT, "account_id": ACCOUNT["id"],
                  "chat": {"name": CHAT_NAME, **CHAT_SPEC},
                  "embedding": {"name": EMBEDDING_NAME, **EMBEDDING_SPEC}}, indent=2))

# %% [markdown]
# This cell invalidates old smoke evidence, revalidates the owned project read-only, and provisions only the two compatible model deployments.
# %% Step 1.5 - Deploy models
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if APPROVE_PROVISIONING is not True:
    raise RuntimeError("Review Step 1.4 and set APPROVE_PROVISIONING=True before proceeding.")
HANDOFF, CONTEXT, ACCOUNT, PROJECT = project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
CHAT = project_setup.ensure_deployment(CLI, ACCOUNT, CHAT_NAME, CHAT_SPEC)
EMBEDDING = project_setup.ensure_deployment(CLI, ACCOUNT, EMBEDDING_NAME, EMBEDDING_SPEC)
print(json.dumps({"project_id": PROJECT["id"], "chat": CHAT["name"],
                  "embedding": EMBEDDING["name"], "provisioning": "Succeeded"}, indent=2))

# %% [markdown]
# This cell resets smoke evidence before testing chat text and a 3072-dimensional embedding with Entra credentials.
# %% Step 1.6 - Smoke-test both models
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
TESTED_TARGET = project_setup.smoke_target(
    PROJECT["id"], PROJECT_ENDPOINT, OPENAI_ENDPOINT, CONTEXT["tenant_id"],
    CHAT_NAME, CHAT_SPEC, EMBEDDING_NAME, EMBEDDING_SPEC)
SMOKE_TESTS = project_setup.smoke_test(CLI, OPENAI_ENDPOINT, CHAT_NAME, EMBEDDING_NAME)
SMOKE_TARGET = TESTED_TARGET

# %% [markdown]
# This cell publishes the original `.env` and project artifact contracts only when smoke evidence matches this exact live target.
# %% Step 1.7 - Publish verified configuration
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
HANDOFF, CONTEXT, ACCOUNT, PROJECT = project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
CURRENT_TARGET = project_setup.smoke_target(
    PROJECT["id"], PROJECT_ENDPOINT, OPENAI_ENDPOINT, CONTEXT["tenant_id"],
    CHAT_NAME, CHAT_SPEC, EMBEDDING_NAME, EMBEDDING_SPEC)
if (SMOKE_TESTS.get("chat") != "passed" or SMOKE_TESTS.get("embedding") != "passed"
        or SMOKE_TARGET != CURRENT_TARGET):
    raise RuntimeError("Run Step 1.6 for this exact project, endpoints and deployment plan before publishing.")
OUTPUT_ENV = {
    "FOUNDRY_PROJECT_ENDPOINT": PROJECT_ENDPOINT, "PROJECT_RESOURCE_ID": PROJECT["id"],
    "TENANT_ID": CONTEXT["tenant_id"], "AZURE_AI_MODEL_DEPLOYMENT_NAME": CHAT_NAME,
    "FOUNDRY_MODEL": CHAT_NAME, "EMBEDDING_MODEL_DEPLOYMENT_NAME": EMBEDDING_NAME,
    "AZURE_OPENAI_ENDPOINT": OPENAI_ENDPOINT, "MARKETPLACE_RESOURCE_SUFFIX": SUFFIX,
}
OPTIONAL_INPUTS = {
    "AZURE_AI_SEARCH_ENDPOINT": AZURE_AI_SEARCH_ENDPOINT,
    "MARKETPLACE_BLOB_STORAGE_URL": MARKETPLACE_BLOB_STORAGE_URL,
    "MARKETPLACE_BLOB_STORAGE_CONTAINER": MARKETPLACE_BLOB_STORAGE_CONTAINER,
    "APPLICATIONINSIGHTS_CONNECTION_STRING": APPLICATIONINSIGHTS_CONNECTION_STRING,
    "MARKETPLACE_TODAY": MARKETPLACE_TODAY,
}
OUTPUT_ENV.update({key: value.strip() for key, value in OPTIONAL_INPUTS.items() if value.strip()})
project_setup.write_env(REPO_ROOT / ".env", OUTPUT_ENV)
ENV = foundry_env.load_env()
if any(ENV.get(key) != value for key, value in OUTPUT_ENV.items()):
    raise RuntimeError("Downstream load_env did not retain the verified configuration.")
CHECKPOINT = {
    "schema_version": 1, "verified_at": datetime.now(timezone.utc).isoformat(),
    "subscription_id": CONTEXT["subscription_id"], "tenant_id": CONTEXT["tenant_id"],
    "account_resource_id": ACCOUNT["id"], "project_resource_id": PROJECT["id"],
    "project_endpoint": PROJECT_ENDPOINT, "azure_openai_endpoint": OPENAI_ENDPOINT,
    "resource_suffix": SUFFIX, "chat_deployment": {"name": CHAT_NAME, **CHAT_SPEC},
    "embedding_deployment": {"name": EMBEDDING_NAME, **EMBEDDING_SPEC},
    "provisioning_state": "Succeeded", "smoke_tests": SMOKE_TESTS,
}
foundry_env.save_artifact(ARTIFACT, CHECKPOINT)
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab1", part="b", context=notebook_parts.scope(ENV),
    evidence=[ARTIFACT], state={"smoke_tests": SMOKE_TESTS, "project_resource_id": PROJECT["id"]})
print(f"Verified checkpoint: {ARTIFACT.relative_to(REPO_ROOT)}")

# %% [markdown]
# ## Checkpoint
#
# Both deployments succeeded and passed inference tests. Lab 2A reads the original `project.json`
# and root `.env`; this is not certification of hosted infrastructure, Search, Blob or telemetry.
