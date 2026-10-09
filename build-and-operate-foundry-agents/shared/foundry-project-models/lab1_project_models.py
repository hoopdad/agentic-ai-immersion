# %% [markdown]
# # Labs 1-2: Create your Foundry project and deploy models
#
# **Infrastructure prerequisite:** your facilitator must already provide an approved Microsoft
# Foundry account (`AIServices`, project management enabled), resource group, networking, quota,
# and management/data-plane RBAC; this lab does not create an account or shared infrastructure.
# Projects have attendee-owned identities, while model deployments belong to the shared account.
# Use a unique attendee suffix, and agree on deployment SKU/capacity costs before provisioning.
# This lab does not configure Standard Agent capability hosts or grant RBAC.
#
# This original combined source is retained for internal regression compatibility.
# Learners use `lab01_walkthrough.ipynb` then `lab02_walkthrough.ipynb` in Python 3.14;
# do not use Run All before reviewing discovery and the deployment plan.
# Existing Azure CLI login is reused; device login is requested only when credentials are unavailable.
#
# This cell imports the dependency-free provisioning helpers from the notebook or repository folder.
# %% Step 1.1 - Import notebook helpers
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

HERE = Path.cwd().resolve()
REPO_ROOT = next((p for p in (HERE, *HERE.parents)
                  if (p / "build-and-operate-foundry-agents/common/resource_names.py").is_file()), None)
if REPO_ROOT is None:
    raise RuntimeError("Open this notebook inside the repository dev container.")
WORKSHOP = REPO_ROOT / "build-and-operate-foundry-agents"
LAB_DIR = WORKSHOP / "shared/foundry-project-models"
for folder in (WORKSHOP, LAB_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
from common import foundry_env, resource_names
import project_setup

CLI = project_setup.AzureCLI()
LAB = "lab1"
ARTIFACT = WORKSHOP / "3-day-labs/artifacts/lab1/project.json"

# %% [markdown]
# This cell records your approved Azure context, attendee suffix and optional administrator-supplied downstream configuration without switching subscriptions.
# %% Step 1.2 - Edit context inputs
SUBSCRIPTION_ID = ""  # Blank discovers the already-active subscription; inspect the next cell.
TENANT_ID = ""  # Blank discovers its tenant; fill both GUIDs to enforce facilitator-approved context.
RESOURCE_GROUP = ""  # Fill after account discovery.
FOUNDRY_ACCOUNT_NAME = ""  # Existing approved Foundry account, never a new account.
ATTENDEE_SUFFIX = ""  # Unique 1-16 lowercase letters/numbers/hyphens, e.g. jd-4821.
AZURE_AI_SEARCH_ENDPOINT = ""  # Administrator-supplied existing Search endpoint; blank preserves existing value.
MARKETPLACE_BLOB_STORAGE_URL = ""  # Existing account URL, never a connection string or SAS token.
MARKETPLACE_BLOB_STORAGE_CONTAINER = ""  # Existing approved history container; no container is created here.
APPLICATIONINSIGHTS_CONNECTION_STRING = ""  # Administrator-supplied telemetry configuration; never an access token.
MARKETPLACE_TODAY = "2026-10-06"  # Fixed workshop fixture date (YYYY-MM-DD), not the current calendar date.

# %% [markdown]
# This cell displays the authenticated subscription, tenant and existing project-enabled Foundry accounts for your review.
# %% Step 1.3 - Discover approved account
CONTEXT = project_setup.azure_context(CLI, SUBSCRIPTION_ID, TENANT_ID)
print(json.dumps(CONTEXT, indent=2))
print(json.dumps(project_setup.account_inventory(CLI, CONTEXT), indent=2))
print("Review these IDs with your facilitator, fill Step 1.2, then rerun Steps 1.2-1.3.")

# %% [markdown]
# This cell verifies the selected existing account and displays its live model versions, capabilities and deployment SKUs.
# %% Step 1.4 - Inspect available models
CONTEXT = project_setup.azure_context(CLI, SUBSCRIPTION_ID, TENANT_ID)
SUFFIX = resource_names.suffix({"MARKETPLACE_RESOURCE_SUFFIX": ATTENDEE_SUFFIX}, required=True)
ACCOUNT = project_setup.verify_account(CLI, CONTEXT, RESOURCE_GROUP, FOUNDRY_ACCOUNT_NAME)
MODELS = CLI.items(ACCOUNT["id"] + "/models")
print(json.dumps([m for m in MODELS if m.get("format") == "OpenAI"
                  and (m.get("name", "").startswith("gpt-") or m.get("name") == "text-embedding-3-large")], indent=2))

# %% [markdown]
# This cell selects versions and SKUs from the live inventory and prints the attendee-scoped deployment plan before any writes.
# %% Step 1.5 - Edit and review the model plan
CHAT_MODEL = "gpt-5.4-mini"  # Change to an available chat-completions model if necessary.
CHAT_VERSION = ""  # Choose the displayed version; blank uses only an unambiguous/default live version.
CHAT_SKU = "GlobalStandard"  # Must occur in the selected model's advertised skus.
CHAT_CAPACITY = 10  # Capacity units are SKU/model-specific; check quota and costs with the facilitator.
EMBEDDING_VERSION = ""  # No historical model version is hardcoded.
EMBEDDING_SKU = "Standard"
EMBEDDING_CAPACITY = 1
APPROVE_PROVISIONING = False  # Set True only after reviewing subscription, account, model plan and charges.

CHAT_SPEC = project_setup.choose_model(MODELS, CHAT_MODEL, CHAT_VERSION, CHAT_SKU, CHAT_CAPACITY)
EMBEDDING_SPEC = project_setup.choose_model(
    MODELS, "text-embedding-3-large", EMBEDDING_VERSION, EMBEDDING_SKU, EMBEDDING_CAPACITY)
CHAT_NAME = resource_names.name("marketplace-chat", {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)
EMBEDDING_NAME = resource_names.name("marketplace-embedding", {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)
print(json.dumps({"context": CONTEXT, "account_id": ACCOUNT["id"], "attendee_suffix": SUFFIX,
                  "chat": {"name": CHAT_NAME, **CHAT_SPEC},
                  "embedding": {"name": EMBEDDING_NAME, **EMBEDDING_SPEC}}, indent=2))

# %% [markdown]
# This cell creates or safely reuses your project and two compatible account-level deployments and waits for successful provisioning.
# %% Step 1.6 - Provision project and models
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
if APPROVE_PROVISIONING is not True:
    raise RuntimeError("Review Step 1.5, set APPROVE_PROVISIONING=True and rerun it before proceeding.")
CURRENT_CONTEXT = project_setup.azure_context(CLI, CONTEXT["subscription_id"], CONTEXT["tenant_id"])
ACCOUNT = project_setup.verify_account(CLI, CURRENT_CONTEXT, RESOURCE_GROUP, FOUNDRY_ACCOUNT_NAME)
PROJECT = project_setup.ensure_project(CLI, ACCOUNT, SUFFIX)
CHAT = project_setup.ensure_deployment(CLI, ACCOUNT, CHAT_NAME, CHAT_SPEC)
EMBEDDING = project_setup.ensure_deployment(CLI, ACCOUNT, EMBEDDING_NAME, EMBEDDING_SPEC)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
print(json.dumps({"project_id": PROJECT["id"], "project_endpoint": PROJECT_ENDPOINT,
                  "chat": CHAT["name"], "embedding": EMBEDDING["name"],
                  "provisioning": "Succeeded"}, indent=2))

# %% [markdown]
# This cell calls both deployed models with Azure CLI Entra credentials and confirms assistant text plus a 3072-dimensional embedding.
# %% Step 1.7 - Hello-world and embedding smoke tests
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
project_setup.azure_context(CLI, CONTEXT["subscription_id"], CONTEXT["tenant_id"])
TESTED_TARGET = project_setup.smoke_target(
    PROJECT["id"], PROJECT_ENDPOINT, OPENAI_ENDPOINT, CONTEXT["tenant_id"],
    CHAT_NAME, CHAT_SPEC, EMBEDDING_NAME, EMBEDDING_SPEC)
SMOKE_TESTS = project_setup.smoke_test(CLI, OPENAI_ENDPOINT, CHAT_NAME, EMBEDDING_NAME)
SMOKE_TARGET = TESTED_TARGET

# %% [markdown]
# This cell saves verified noncredential outputs to the root environment and project checkpoint while preserving unrelated configuration.
# %% Step 1.8 - Publish the downstream handoff
ARTIFACT.unlink(missing_ok=True)
CURRENT_TARGET = project_setup.smoke_target(
    PROJECT["id"], PROJECT_ENDPOINT, OPENAI_ENDPOINT, CONTEXT["tenant_id"],
    CHAT_NAME, CHAT_SPEC, EMBEDDING_NAME, EMBEDDING_SPEC)
if (SMOKE_TESTS.get("chat") != "passed" or SMOKE_TESTS.get("embedding") != "passed"
        or SMOKE_TARGET != CURRENT_TARGET):
    raise RuntimeError("Run Step 1.7 successfully for this exact project, endpoints and deployment plan before publishing.")
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
    "resource_suffix": SUFFIX,
    "chat_deployment": {"name": CHAT_NAME, **CHAT_SPEC},
    "embedding_deployment": {"name": EMBEDDING_NAME, **EMBEDDING_SPEC},
    "provisioning_state": "Succeeded", "smoke_tests": SMOKE_TESTS,
}
foundry_env.save_artifact(ARTIFACT, CHECKPOINT)
print(f"Verified checkpoint: {ARTIFACT.relative_to(REPO_ROOT)}")
print("Root .env contains approved project/model outputs and optional configuration; Azure credentials were not persisted.")
MISSING_LATER_INPUTS = [key for key in (
    "AZURE_AI_SEARCH_ENDPOINT", "MARKETPLACE_BLOB_STORAGE_URL",
    "MARKETPLACE_BLOB_STORAGE_CONTAINER", "APPLICATIONINSIGHTS_CONNECTION_STRING",
) if not ENV.get(key)]
if MISSING_LATER_INPUTS:
    print("Later lab dependencies still need administrator-supplied inputs in Step 1.2: "
          + ", ".join(MISSING_LATER_INPUTS))

# %% [markdown]
# ## Acceptance evidence and next lab
#
# The published project checkpoint means the project and both model deployments reached `Succeeded`,
# the chat returned text, the embedding returned 3072 dimensions, and downstream `load_env()` sees
# the verified endpoints and deployment names; it does not certify hosted-agent infrastructure readiness.
# Keep `3-day-labs/artifacts/lab1/project.json` for the hosted-agent lab's prerequisite check.
#
# **Later explicit inputs:** Search endpoint, Blob storage URL/container and Application Insights
# connection string must come from facilitator-approved infrastructure and can be entered in Step 1.2;
# this notebook persists only nonblank inputs, preserves blank-input existing values and never guesses
# or provisions these dependencies, while the workshop date defaults to `2026-10-06`.
# Optional inputs are not included in the project checkpoint, and model smoke tests do not verify them.
# Account-level deployment quota/cost is shared: never delete another attendee's resources, and arrange
# cleanup of your project and the two displayed deployment names with the facilitator after the workshop.
