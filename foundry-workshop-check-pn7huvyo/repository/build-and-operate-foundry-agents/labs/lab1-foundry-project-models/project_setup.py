"""Azure CLI-backed provisioning helpers for the project-and-model notebook."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
import re
import subprocess
import time
from typing import Any
from urllib.parse import urlparse

from common import notebook_parts, resource_names

API_VERSION = "2025-06-01"
ARM = "https://management.azure.com"
PROJECT_ENV_KEYS = {
    "FOUNDRY_PROJECT_ENDPOINT", "PROJECT_RESOURCE_ID", "TENANT_ID",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME", "FOUNDRY_MODEL",
    "EMBEDDING_MODEL_DEPLOYMENT_NAME", "AZURE_OPENAI_ENDPOINT",
    "MARKETPLACE_RESOURCE_SUFFIX",
}
OPTIONAL_ENV_KEYS = {
    "AZURE_AI_SEARCH_ENDPOINT", "MARKETPLACE_BLOB_STORAGE_URL",
    "MARKETPLACE_BLOB_STORAGE_CONTAINER", "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "MARKETPLACE_TODAY",
}
ENV_KEYS = PROJECT_ENV_KEYS | OPTIONAL_ENV_KEYS
GUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


class AzureCLI:
    def run(self, *args: str) -> Any:
        if args[0] == "login":
            # Device-code instructions must be visible to the notebook learner.
            result = subprocess.run(
                ["az", *args, "--only-show-errors", "--output", "none"],
                check=False, timeout=300,
            )
            if result.returncode:
                raise RuntimeError("Azure login failed; review Step 1.2 tenant input and rerun Step 1.3 with facilitator assistance.")
            return {}
        result = subprocess.run(
            ["az", *args, "--only-show-errors", "--output", "json"],
            check=False, capture_output=True, text=True, timeout=180,
        )
        if result.returncode:
            # Do not echo bodies or stdout, which can include access tokens.
            raise RuntimeError(f"Azure CLI {args[0]} failed; check login, RBAC, quota and network access.")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def rest(self, method: str, resource_id: str, body: dict | None = None) -> Any:
        url = f"{ARM}{resource_id}?api-version={API_VERSION}"
        args = ["rest", "--method", method, "--url", url]
        if body is not None:
            args += ["--body", json.dumps(body)]
        return self.run(*args)

    def items(self, resource_id: str) -> list[dict]:
        page = self.rest("get", resource_id)
        items = list(page.get("value", []))
        while page.get("nextLink"):
            link = page["nextLink"]
            parsed = urlparse(link)
            if parsed.scheme != "https" or parsed.netloc != "management.azure.com":
                raise RuntimeError("Unexpected ARM pagination endpoint.")
            if not parsed.path.lower().startswith(resource_id.lower()):
                raise RuntimeError("Pagination escaped the selected resource scope.")
            page = self.run("rest", "--method", "get", "--url", link)
            items.extend(page.get("value", []))
        return items


def azure_context(cli: AzureCLI, subscription_id: str = "", tenant_id: str = "") -> dict:
    """Reuse login, require an explicit matching context, and never run account set."""
    for value in (subscription_id, tenant_id):
        if value and not GUID.fullmatch(value):
            raise ValueError("Subscription and tenant inputs must be GUIDs.")
    try:
        current = cli.run("account", "show")
    except RuntimeError:
        args = ["login", "--use-device-code"]
        if tenant_id:
            args += ["--tenant", tenant_id]
        cli.run(*args)
        current = cli.run("account", "show")
    if subscription_id and current["id"].lower() != subscription_id.lower():
        raise RuntimeError("Active subscription differs from the input; review Step 1.2 context inputs and Step 1.3 discovery with your facilitator. The notebook does not switch subscriptions.")
    if tenant_id and current["tenantId"].lower() != tenant_id.lower():
        raise RuntimeError("Active tenant differs from the input; review Step 1.2 tenant input and Step 1.3 discovery with your facilitator.")
    if current.get("state") != "Enabled":
        raise RuntimeError("Selected subscription is not enabled.")
    # Account metadata can exist after a cached credential expires.
    try:
        cli.run("account", "get-access-token", "--subscription", current["id"], "--resource", ARM)
    except RuntimeError:
        cli.run("login", "--use-device-code", "--tenant", current["tenantId"])
        refreshed = cli.run("account", "show")
        if (refreshed["id"].lower(), refreshed["tenantId"].lower()) != (
            current["id"].lower(), current["tenantId"].lower()
        ):
            raise RuntimeError("Login changed Azure context; stop and review Step 1.2 inputs and Step 1.3 discovery with your facilitator.")
        cli.run("account", "get-access-token", "--subscription", current["id"], "--resource", ARM)
    return {"subscription_id": current["id"], "tenant_id": current["tenantId"],
            "subscription_name": current.get("name", "")}


def account_inventory(cli: AzureCLI, context: dict) -> list[dict]:
    accounts = cli.run("cognitiveservices", "account", "list", "--subscription", context["subscription_id"])
    return [{"name": a["name"], "resource_group": a["resourceGroup"],
             "location": a["location"], "id": a["id"]}
            for a in accounts if a.get("kind") == "AIServices"
            and a.get("properties", {}).get("allowProjectManagement") is True]


def verify_account(cli: AzureCLI, context: dict, resource_group: str, account_name: str) -> dict:
    for value in (resource_group, account_name):
        if not value or "/" in value or "?" in value or "#" in value:
            raise ValueError("Provide the approved resource group and Foundry account names from discovery.")
    # ARM ids (not the CLI default subscription) scope every subsequent request.
    resource_id = (f"/subscriptions/{context['subscription_id']}/resourceGroups/{resource_group}"
                   f"/providers/Microsoft.CognitiveServices/accounts/{account_name}")
    account = cli.rest("get", resource_id)
    if account.get("id", "").lower() != resource_id.lower():
        raise RuntimeError("Account response does not match the approved resource scope.")
    props = account.get("properties", {})
    if (account.get("kind") != "AIServices" or props.get("allowProjectManagement") is not True
            or props.get("provisioningState") != "Succeeded"):
        raise RuntimeError("Prerequisite: an approved, successfully provisioned Foundry account with project management enabled.")
    return account


def choose_model(models: list[dict], model_name: str, version: str, sku: str, capacity: int) -> dict:
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
        raise ValueError("Deployment capacity must be a positive integer.")
    candidates = [m for m in models if m.get("format") == "OpenAI" and m.get("name") == model_name]
    if version:
        candidates = [m for m in candidates if m.get("version") == version]
    elif len(candidates) > 1:
        candidates = [m for m in candidates if m.get("isDefaultVersion") is True]
    if len(candidates) != 1 or not candidates[0].get("version"):
        raise ValueError(f"Select an available version of {model_name} from the displayed account model inventory.")
    selected = candidates[0]
    skus = selected.get("skus", [])
    selected_sku = next((s for s in skus if s.get("name") == sku), None)
    if selected_sku is None:
        raise ValueError(f"SKU {sku} is not advertised for {model_name} {selected['version']}; choose from the inventory.")
    limits = selected_sku.get("capacity") or {}
    minimum = limits["minimum"] if limits.get("minimum") is not None else 1
    maximum = limits["maximum"] if limits.get("maximum") is not None else float("inf")
    step = limits["step"] if limits.get("step") is not None else 1
    if step <= 0:
        raise ValueError("The model SKU advertises a nonpositive capacity step.")
    if capacity < minimum or capacity > maximum or (capacity - minimum) % step:
        raise ValueError("Requested capacity does not satisfy the model SKU's advertised limits.")
    return {"sku": {"name": sku, "capacity": capacity},
            "properties": {"model": {"format": "OpenAI", "name": model_name, "version": selected["version"]}}}


def poll_resource(cli: AzureCLI, resource_id: str, timeout: float = 900, interval: float = 5) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        resource = cli.rest("get", resource_id)
        state = resource.get("properties", {}).get("provisioningState")
        if state == "Succeeded":
            return resource
        if state in {"Failed", "Canceled", "Cancelled", "Deleted"}:
            raise RuntimeError(f"Provisioning {resource_id} ended in {state}; inspect Azure activity logs.")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for {resource_id}; no checkpoint was published.")
        time.sleep(interval)


def ensure_project(cli: AzureCLI, account: dict, attendee_suffix: str) -> dict:
    env = {"MARKETPLACE_RESOURCE_SUFFIX": attendee_suffix}
    project_name = resource_names.name("healthcare-marketplace", env, required=True)
    resource_id = account["id"] + "/projects/" + project_name
    existing = next((p for p in cli.items(account["id"] + "/projects")
                     if p["name"].lower() == project_name.lower()), None)
    if existing:
        if existing.get("tags", {}).get("marketplace-resource-suffix") != resource_names.suffix(env, required=True):
            raise RuntimeError("Existing project is not owned by this attendee; refusing to modify it.")
    else:
        cli.rest("put", resource_id, {
            "location": account["location"], "identity": {"type": "SystemAssigned"},
            "tags": {"marketplace-resource-suffix": resource_names.suffix(env, required=True)},
            "properties": {"displayName": project_name, "description": "Healthcare Marketplace workshop"},
        })
    project = poll_resource(cli, resource_id)
    if project.get("id", "").lower() != resource_id.lower():
        raise RuntimeError("Project response escaped the approved account scope.")
    return project


def read_project_handoff(
    path: Path, cli: AzureCLI, subscription_id: str, tenant_id: str, attendee_suffix: str,
) -> tuple[dict, dict, dict, dict]:
    """Read Lab 1A's explicit inputs and revalidate ownership without provisioning."""
    if not path.is_file():
        raise RuntimeError("Complete Lab 1A before opening Lab 1B: missing part_a.json.")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Lab 1A handoff is unreadable; rerun Lab 1A.") from exc
    if not isinstance(record, dict) or not isinstance(record.get("state"), dict):
        raise RuntimeError("Lab 1A handoff must contain explicit project/context inputs.")
    state = record["state"]
    suffix = resource_names.suffix({"MARKETPLACE_RESOURCE_SUFFIX": attendee_suffix}, required=True)
    if not subscription_id or not tenant_id:
        raise ValueError("Enter the facilitator-approved subscription and tenant from Lab 1A.")
    account_id = (f"/subscriptions/{subscription_id}/resourceGroups/{state.get('resource_group', '')}"
                  f"/providers/Microsoft.CognitiveServices/accounts/{state.get('account_name', '')}")
    expected_id = account_id + "/projects/" + resource_names.name(
        "healthcare-marketplace", {"MARKETPLACE_RESOURCE_SUFFIX": suffix}, required=True)
    approved_context = {
        "subscription_id": subscription_id.lower(), "tenant_id": tenant_id.lower(),
        "account_resource_id": account_id.lower(), "project_resource_id": expected_id.lower(),
        "resource_suffix": suffix,
    }
    notebook_parts.read_checkpoint(path, lab="lab1", part="a", context=approved_context)
    if (state.get("subscription_id", "").lower() != subscription_id.lower()
            or state.get("tenant_id", "").lower() != tenant_id.lower()
            or state.get("resource_suffix") != suffix
            or state.get("account_resource_id", "").lower() != account_id.lower()
            or state.get("project_resource_id", "").lower() != expected_id.lower()):
        raise RuntimeError("Lab 1A handoff escaped the approved account/project scope.")
    context = azure_context(cli, subscription_id, tenant_id)
    account = verify_account(cli, context, state["resource_group"], state["account_name"])
    project = cli.rest("get", expected_id)
    if (project.get("id", "").lower() != expected_id.lower()
            or project.get("tags", {}).get("marketplace-resource-suffix") != suffix
            or project.get("properties", {}).get("provisioningState") != "Succeeded"):
        raise RuntimeError("Lab 1A project is missing, not ready, or not owned by this attendee.")
    if endpoints(account, project) != (
            state.get("project_endpoint"), state.get("azure_openai_endpoint")):
        raise RuntimeError("Lab 1A endpoints changed; revalidate the project in Lab 1A.")
    return state, context, account, project


def ensure_deployment(cli: AzureCLI, account: dict, deployment_name: str, desired: dict) -> dict:
    resource_id = account["id"] + "/deployments/" + deployment_name
    existing = next((d for d in cli.items(account["id"] + "/deployments")
                     if d["name"].lower() == deployment_name.lower()), None)
    if existing:
        compatible_deployment(existing, desired)
    else:
        cli.rest("put", resource_id, desired)
    result = poll_resource(cli, resource_id)
    if result.get("id", "").lower() != resource_id.lower():
        raise RuntimeError("Deployment response escaped the approved account scope.")
    compatible_deployment(result, desired)
    return result


def compatible_deployment(existing: dict, desired: dict) -> None:
    actual_model = existing.get("properties", {}).get("model", {})
    expected_model = desired["properties"]["model"]
    if (any(actual_model.get(k) != v for k, v in expected_model.items())
            or any(existing.get("sku", {}).get(k) != v for k, v in desired["sku"].items())):
        raise RuntimeError("Existing deployment has incompatible model/version/SKU/capacity; refusing to overwrite it.")


def endpoints(account: dict, project: dict) -> tuple[str, str]:
    project_name = project["id"].rsplit("/", 1)[-1]
    foundry = [v.rstrip("/") for v in project.get("properties", {}).get("endpoints", {}).values()
               if isinstance(v, str) and urlparse(v).scheme == "https"
               and urlparse(v).hostname and urlparse(v).hostname.endswith(".services.ai.azure.com")
               and urlparse(v).path.rstrip("/") == f"/api/projects/{project_name}"
               and not urlparse(v).query and not urlparse(v).fragment and not urlparse(v).username]
    if not foundry:
        # Some ARM responses expose the account base endpoint rather than the project URL.
        # Append only the documented project route, never synthesize an account hostname.
        foundry = [v.rstrip("/") + f"/api/projects/{project_name}"
                   for v in account.get("properties", {}).get("endpoints", {}).values()
                   if isinstance(v, str) and urlparse(v).scheme == "https"
                   and urlparse(v).hostname and urlparse(v).hostname.endswith(".services.ai.azure.com")
                   and urlparse(v).path in {"", "/"} and not urlparse(v).query
                   and not urlparse(v).fragment and not urlparse(v).username]
    openai = [v.rstrip("/") + "/" for v in account.get("properties", {}).get("endpoints", {}).values()
              if isinstance(v, str) and urlparse(v).scheme == "https"
              and urlparse(v).hostname and urlparse(v).hostname.endswith(".openai.azure.com")
              and urlparse(v).path in {"", "/"} and not urlparse(v).query
              and not urlparse(v).fragment and not urlparse(v).username]
    if len(set(foundry)) != 1 or len(set(openai)) != 1:
        raise RuntimeError("Azure did not return unambiguous Foundry project and Azure OpenAI endpoints; inspect the resource, do not guess URLs.")
    return foundry[0], openai[0]


def smoke_test(cli: AzureCLI, openai_endpoint: str, chat: str, embedding: str) -> dict:
    common = ["rest", "--method", "post", "--resource", "https://cognitiveservices.azure.com"]
    reply = cli.run(*common, "--url", openai_endpoint + "openai/v1/chat/completions",
                    "--body", json.dumps({"model": chat, "messages": [
                        {"role": "user", "content": "Say hello in one short sentence."}]}))
    choices = reply.get("choices", [])
    text = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Chat smoke test returned no assistant text.")
    vectors = cli.run(*common, "--url", openai_endpoint + "openai/v1/embeddings",
                      "--body", json.dumps({"model": embedding, "input": "Healthcare marketplace"}))
    data = vectors.get("data", [])
    vector = data[0].get("embedding") if data else None
    if not isinstance(vector, list) or len(vector) != 3072 or not all(
        isinstance(v, (float, int)) and not isinstance(v, bool) for v in vector
    ):
        raise RuntimeError("Embedding smoke test did not return the default 3072-dimensional text-embedding-3-large vector.")
    print(f"Chat: {text}\nEmbedding dimensions: {len(vector)}")
    return {"chat": "passed", "embedding": "passed", "embedding_dimensions": len(vector)}


def smoke_target(project_id: str, project_endpoint: str, openai_endpoint: str, tenant_id: str,
                 chat_name: str, chat_spec: dict, embedding_name: str, embedding_spec: dict) -> str:
    """Snapshot the exact tested target, without retaining references to mutable specs."""
    return json.dumps({
        "project_id": project_id, "project_endpoint": project_endpoint,
        "openai_endpoint": openai_endpoint, "tenant_id": tenant_id,
        "chat": {"name": chat_name, "spec": chat_spec},
        "embedding": {"name": embedding_name, "spec": embedding_spec},
    }, sort_keys=True)


def write_env(path: Path, values: dict[str, str]) -> None:
    """Replace only workshop output keys; leave unrelated lines intact."""
    if not values.keys() <= ENV_KEYS:
        raise ValueError("Only noncredential workshop output keys can be persisted.")
    if any(not isinstance(v, str) or any(c in v for c in "\r\n\"\\$`") for v in values.values()):
        raise ValueError("Unsafe environment value.")
    for key in ("AZURE_AI_SEARCH_ENDPOINT", "MARKETPLACE_BLOB_STORAGE_URL"):
        if values.get(key):
            parsed = urlparse(values[key])
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or parsed.query or parsed.fragment):
                raise ValueError(f"{key} must be an HTTPS resource URL without credentials or query parameters.")
    if values.get("MARKETPLACE_TODAY"):
        date.fromisoformat(values["MARKETPLACE_TODAY"])
    if path.is_symlink():
        raise ValueError("Refusing to replace a symlinked .env.")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
    updated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = match.group(1) if match else ""
        if key in values:
            if key not in seen:
                updated.append(f'{key}="{values[key]}"\n')
                seen.add(key)
        else:
            updated.append(line)
    if updated and not updated[-1].endswith("\n"):
        updated[-1] += "\n"
    updated += [f'{key}="{value}"\n' for key, value in values.items() if key not in seen]
    staging = path.with_name(path.name + ".project-setup-new")
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("".join(updated))
        staging.replace(path)
    finally:
        if staging.exists():
            staging.unlink()
    # load_env deliberately preserves exported values, so update this kernel too.
    os.environ.update(values)
