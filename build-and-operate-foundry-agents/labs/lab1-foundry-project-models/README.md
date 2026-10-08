# Lab 1 — Foundry project and models

Open **[Lab 1A](lab1a_walkthrough.ipynb)**, then **[Lab 1B](lab1b_walkthrough.ipynb)**
in the repository Python 3.14 dev container and run cells individually.
Each half starts independently in a fresh kernel; do not run the preceding notebook
inside the next one.

## Prerequisites

Your facilitator supplies an **existing approved Microsoft Foundry account**
(`AIServices`, project management enabled), subscription/tenant, resource group,
network connectivity, model quota and appropriate project/deployment management
and OpenAI inference permissions. This notebook **does not create account
infrastructure**, configure a Standard Agent capability host or assign permissions.
Azure CLI must be installed; existing credentials are reused, with device login
only when unavailable. The notebook never switches subscriptions.

## Notebook path

1. Edit the context inputs, discover and review subscription/tenant and accounts.
2. Fill the approved account/resource group and a unique attendee suffix.
3. In **1A**, review scope/ownership, approve creation of only your project, and save
   `artifacts/lab1/part_a.json` with explicit noncredential context/project inputs.
4. In **1B**, enter your approved subscription, tenant and suffix again. Read the
   handoff and verify current identity, account, live project ownership and endpoints
   without creating or updating the project.
5. Inspect the account's **live model inventory**; select a chat model plus
   `text-embedding-3-large`, their available versions, advertised SKUs and capacity.
6. Review costs/quota and the printed scope, then explicitly approve model provisioning.
7. Create two account-level deployments, waiting
   for `Succeeded`; compatible resources are reused without modifying them, and
   incompatible resources are never overwritten.
8. Confirm hello-world text and a 3072-dimensional embedding, then publish root
   `.env`, `labs/artifacts/lab1/project.json`, and the **1B** `part_b.json` marker.

Each executable cell has its own one-sentence description and visible step ID.
Do not run all cells before reviewing discovery and approving the model plan.
If RBAC, networking, availability or quota fails, stop and consult your
facilitator; no success artifact is published on a failed provisioning rerun.
Provisioning and smoke-test reruns invalidate previous evidence and checkpoints
before starting. Publishing requires fresh passed tests bound to the exact
project, tenant, endpoints, deployment names and model/SKU/capacity specifications.

The root `.env` update preserves unrelated values and writes no Azure access
tokens, passwords or SAS credentials. **1B Step 1.2** also exposes **optional explicit
administrator-supplied inputs**: `AZURE_AI_SEARCH_ENDPOINT`,
`MARKETPLACE_BLOB_STORAGE_URL`, `MARKETPLACE_BLOB_STORAGE_CONTAINER` and
`APPLICATIONINSIGHTS_CONNECTION_STRING`; nonblank values are saved in **1B Step 1.7**,
and blank inputs preserve existing configuration. These resources are not
created or guessed, their readiness is not certified by model smoke tests,
and later dependencies remain administrator-owned.
`MARKETPLACE_TODAY` defaults to the fixed fixture date `2026-10-06`.
None of these optional inputs is copied into the project artifact.
The next hosted-agent notebook consumes the verified project checkpoint.
The adjacent `lab1a_identity_project.py` and `lab1b_models_verify.py` are notebook
authoring sources; `project_setup.py` and the original driver remain internal helpers.

## Checkpoint contract

`labs/artifacts/lab1/project.json` has `schema_version=1`, `verified_at`,
`subscription_id`, `tenant_id`, `account_resource_id`, `project_resource_id`,
`project_endpoint`, `azure_openai_endpoint`, `resource_suffix`,
`provisioning_state="Succeeded"`, `chat_deployment`, `embedding_deployment`,
and `smoke_tests`. Each deployment records `name`, `sku: {name, capacity}` and
`properties.model: {format, name, version}` from the verified live plan.
Smoke evidence is `{chat: "passed", embedding: "passed", embedding_dimensions: 3072}`;
credentials, raw responses and vectors are not saved.

The environment sets `FOUNDRY_PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID`,
`TENANT_ID`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `FOUNDRY_MODEL`,
`EMBEDDING_MODEL_DEPLOYMENT_NAME`, `AZURE_OPENAI_ENDPOINT` and
`MARKETPLACE_RESOURCE_SUFFIX` for downstream `load_env()`.

## Verified official REST references

The notebook uses ARM API version **2025-06-01** and OpenAI **v1** inference;
model versions are never hardcoded:

- [Projects — Create](https://learn.microsoft.com/en-us/rest/api/microsoftfoundry/accountmanagement/projects/create?view=rest-microsoftfoundry-accountmanagement-2025-06-01)
- [Accounts — List Models](https://learn.microsoft.com/en-us/rest/api/aiservices/accountmanagement/accounts/list-models?view=rest-aiservices-accountmanagement-2024-10-01)
  documents the account-scoped inventory route (also in the
  [2025-06-01 accounts API](https://learn.microsoft.com/en-us/rest/api/microsoftfoundry/accountmanagement/accounts?view=rest-microsoftfoundry-accountmanagement-2025-06-01)).
- [Deployments — Create Or Update](https://learn.microsoft.com/en-us/rest/api/microsoftfoundry/accountmanagement/deployments/create-or-update?view=rest-microsoftfoundry-accountmanagement-2025-06-01)
- [OpenAI chat REST](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat)
- [OpenAI v1 API lifecycle](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)
- [Foundry project endpoint format](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/sdk-overview)
  (when ARM returns only the account base URL, the documented project route is
  appended to that returned URL; account hostnames are never synthesized).

Projects and deployments are attendee-scoped through `common/resource_names.py`.
Arrange cleanup of only your project and displayed model deployments with the
facilitator; shared account infrastructure must remain intact.
