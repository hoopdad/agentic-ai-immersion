# %% [markdown]
# # Lab 1A: Identity, approved account, and your project
#
# Use the Python 3.14 dev-container kernel and run cells individually. The facilitator supplies
# an existing project-enabled Foundry account, networking and RBAC; this half creates only your
# attendee-owned project, not an account, models, capability host, or role assignments.
# Lab 1B can start in a fresh kernel using the explicit noncredential `part_a.json` handoff.
#
# This cell locates the repository and imports the Azure CLI provisioning helpers.
# %% Step 1.1 - Import project helpers
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
from common import foundry_env, resource_names
import project_setup

CLI = project_setup.AzureCLI()
ARTIFACTS = WORKSHOP / "labs/artifacts/lab1"

# %% [markdown]
# This cell records explicit approved identity inputs without switching the active Azure subscription.
# %% Step 1.2 - Edit approved context
SUBSCRIPTION_ID = ""  # Blank initially discovers the active subscription; fill after review.
TENANT_ID = ""  # Fill the approved tenant GUID after discovery.
RESOURCE_GROUP = ""  # Existing facilitator-approved resource group.
FOUNDRY_ACCOUNT_NAME = ""  # Existing Foundry account, never a new account.
ATTENDEE_SUFFIX = ""  # Unique 1-16 lowercase letters/numbers/hyphens.
APPROVE_PROJECT = False  # Set True only after reviewing account, scope and ownership.

# %% [markdown]
# This cell displays the authenticated identity context and project-enabled existing accounts for facilitator review.
# %% Step 1.3 - Discover identity and accounts
CONTEXT = project_setup.azure_context(CLI, SUBSCRIPTION_ID, TENANT_ID)
print(json.dumps(CONTEXT, indent=2))
print(json.dumps(project_setup.account_inventory(CLI, CONTEXT), indent=2))
print("Fill both approved GUIDs and the selected account in Step 1.2, then rerun it.")

# %% [markdown]
# This cell verifies the selected account and prints the attendee-owned project scope before any writes.
# %% Step 1.4 - Review project ownership
if not SUBSCRIPTION_ID or not TENANT_ID:
    raise ValueError("Enter the reviewed subscription and tenant GUIDs in Step 1.2.")
CONTEXT = project_setup.azure_context(CLI, SUBSCRIPTION_ID, TENANT_ID)
SUFFIX = resource_names.suffix({"MARKETPLACE_RESOURCE_SUFFIX": ATTENDEE_SUFFIX}, required=True)
ACCOUNT = project_setup.verify_account(CLI, CONTEXT, RESOURCE_GROUP, FOUNDRY_ACCOUNT_NAME)
print(json.dumps({"context": CONTEXT, "account_id": ACCOUNT["id"],
                  "project_name": resource_names.name("healthcare-marketplace",
                      {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)}, indent=2))

# %% [markdown]
# This cell creates or safely reuses only your owned project and publishes a narrowly scoped noncredential handoff.
# %% Step 1.5 - Create project and save handoff
for name in ("part_a.json", "part_b.json", "project.json"):
    (ARTIFACTS / name).unlink(missing_ok=True)
if APPROVE_PROJECT is not True:
    raise RuntimeError("Review Step 1.4 and set APPROVE_PROJECT=True in Step 1.2.")
CONTEXT = project_setup.azure_context(CLI, SUBSCRIPTION_ID, TENANT_ID)
ACCOUNT = project_setup.verify_account(CLI, CONTEXT, RESOURCE_GROUP, FOUNDRY_ACCOUNT_NAME)
PROJECT = project_setup.ensure_project(CLI, ACCOUNT, SUFFIX)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
HANDOFF = {
    "schema_version": 1, "part": "a", "verified_at": datetime.now(timezone.utc).isoformat(),
    "subscription_id": CONTEXT["subscription_id"], "tenant_id": CONTEXT["tenant_id"],
    "resource_group": RESOURCE_GROUP, "account_name": FOUNDRY_ACCOUNT_NAME,
    "account_resource_id": ACCOUNT["id"], "project_resource_id": PROJECT["id"],
    "resource_suffix": SUFFIX, "project_endpoint": PROJECT_ENDPOINT,
    "azure_openai_endpoint": OPENAI_ENDPOINT,
}
foundry_env.save_artifact(ARTIFACTS / "part_a.json", HANDOFF)
print(json.dumps(HANDOFF, indent=2))

# %% [markdown]
# ## Checkpoint
#
# Keep the displayed subscription, tenant and suffix for Lab 1B. No model deployment or smoke
# evidence exists yet; `.env` and the original `project.json` contract are published only by 1B.
# Never persist CLI tokens, credentials or the full process environment in this handoff.
