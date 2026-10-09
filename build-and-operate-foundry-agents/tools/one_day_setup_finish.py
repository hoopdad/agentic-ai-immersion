# %% [markdown]
# The project is now established. Confirm hosted-agent enablement and identity
# access with the administrator; a chat smoke test does not verify hosting.
# This cell discovers chat model versions and advertised SKUs without cloud writes.
# %% Step 1.6 - Discover chat models
MODELS = CLI.items(ACCOUNT["id"] + "/models")
print(json.dumps([m for m in MODELS if m.get("format") == "OpenAI"
                  and m.get("name", "").startswith("gpt-")], indent=2))

# %% [markdown]
# Review the advertised model/version, quota, SKU and cost before approving deployment.
# This cell selects only a chat deployment; the one-day track performs no embedding or RAG setup.
# %% Step 1.7 - Review the chat deployment plan
CHAT_MODEL = "gpt-5.4-mini"
CHAT_VERSION = ""
CHAT_SKU = "GlobalStandard"
CHAT_CAPACITY = 10  # Review shared room capacity with the administrator.
APPROVE_PROVISIONING = False
CHAT_SPEC = project_setup.choose_model(MODELS, CHAT_MODEL, CHAT_VERSION, CHAT_SKU, CHAT_CAPACITY)
CHAT_NAME = resource_names.name("marketplace-chat", {"MARKETPLACE_RESOURCE_SUFFIX": SUFFIX}, required=True)
SMOKE_TESTS = {}
SMOKE_TARGET = None
print(json.dumps({"account_id": ACCOUNT["id"], "chat": {"name": CHAT_NAME, **CHAT_SPEC}}, indent=2))

# %% [markdown]
# This cell rechecks approved identity and project ownership and explicitly provisions only the selected chat model.
# %% Step 1.8 - Deploy the chat model
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT = ARTIFACTS / "project.json"
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
if APPROVE_PROVISIONING is not True:
    raise RuntimeError("Review Step 1.7 and set APPROVE_PROVISIONING=True before proceeding.")
HANDOFF, CONTEXT, ACCOUNT, PROJECT = project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
CHAT = project_setup.ensure_deployment(CLI, ACCOUNT, CHAT_NAME, CHAT_SPEC)
print(json.dumps({"project_id": PROJECT["id"], "chat": CHAT["name"]}, indent=2))

# %% [markdown]
# This cell checks real chat inference with Entra authentication and binds the evidence to the exact deployment plan.
# %% Step 1.9 - Verify chat inference
SMOKE_TESTS = {}
SMOKE_TARGET = None
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
TESTED_TARGET = json.dumps({
    "project_id": PROJECT["id"], "project_endpoint": PROJECT_ENDPOINT,
    "openai_endpoint": OPENAI_ENDPOINT, "tenant_id": CONTEXT["tenant_id"],
    "chat": {"name": CHAT_NAME, "spec": CHAT_SPEC},
}, sort_keys=True)
reply = CLI.run("rest", "--method", "post", "--resource", "https://cognitiveservices.azure.com",
                "--url", OPENAI_ENDPOINT + "openai/v1/chat/completions",
                "--body", json.dumps({"model": CHAT_NAME, "messages": [
                    {"role": "user", "content": "Say hello in one short sentence."}]}))
choices = reply.get("choices", [])
text = choices[0].get("message", {}).get("content") if choices else None
if not isinstance(text, str) or not text.strip():
    raise RuntimeError("Chat smoke test returned no assistant text.")
print(text)
SMOKE_TESTS = {"chat": "passed"}
SMOKE_TARGET = TESTED_TARGET

# %% [markdown]
# This cell publishes chat-only configuration and scoped evidence only after matching the current live project and tested plan.
# %% Step 1.10 - Publish verified setup
ARTIFACT.unlink(missing_ok=True)
(ARTIFACTS / "part_b.json").unlink(missing_ok=True)
HANDOFF, CONTEXT, ACCOUNT, PROJECT = project_setup.read_project_handoff(
    ARTIFACTS / "part_a.json", CLI, SUBSCRIPTION_ID, TENANT_ID, ATTENDEE_SUFFIX)
PROJECT_ENDPOINT, OPENAI_ENDPOINT = project_setup.endpoints(ACCOUNT, PROJECT)
CURRENT_TARGET = json.dumps({
    "project_id": PROJECT["id"], "project_endpoint": PROJECT_ENDPOINT,
    "openai_endpoint": OPENAI_ENDPOINT, "tenant_id": CONTEXT["tenant_id"],
    "chat": {"name": CHAT_NAME, "spec": CHAT_SPEC},
}, sort_keys=True)
if SMOKE_TESTS.get("chat") != "passed" or SMOKE_TARGET != CURRENT_TARGET:
    raise RuntimeError("Run Step 1.9 for this exact project and chat deployment before publishing.")
OUTPUT_ENV = {
    "FOUNDRY_PROJECT_ENDPOINT": PROJECT_ENDPOINT, "PROJECT_RESOURCE_ID": PROJECT["id"],
    "TENANT_ID": CONTEXT["tenant_id"], "AZURE_AI_MODEL_DEPLOYMENT_NAME": CHAT_NAME,
    "FOUNDRY_MODEL": CHAT_NAME, "AZURE_OPENAI_ENDPOINT": OPENAI_ENDPOINT,
    "MARKETPLACE_RESOURCE_SUFFIX": SUFFIX,
}
project_setup.write_env(REPO_ROOT / ".env", OUTPUT_ENV)
ENV = foundry_env.load_env()
if any(ENV.get(key) != value for key, value in OUTPUT_ENV.items()):
    raise RuntimeError("Downstream configuration does not match the verified setup.")
CHECKPOINT = {
    "schema_version": 1, "track": "one-day-chat-only",
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "subscription_id": CONTEXT["subscription_id"], "tenant_id": CONTEXT["tenant_id"],
    "account_resource_id": ACCOUNT["id"], "project_resource_id": PROJECT["id"],
    "project_endpoint": PROJECT_ENDPOINT, "azure_openai_endpoint": OPENAI_ENDPOINT,
    "resource_suffix": SUFFIX, "chat_deployment": {"name": CHAT_NAME, **CHAT_SPEC},
    "provisioning_state": "Succeeded", "smoke_tests": SMOKE_TESTS,
}
foundry_env.save_artifact(ARTIFACT, CHECKPOINT)
notebook_parts.write_checkpoint(
    ARTIFACTS / "part_b.json", lab="lab1", part="b", context=notebook_parts.scope(ENV),
    evidence=[ARTIFACT], state={"track": "one-day-chat-only", "smoke_tests": SMOKE_TESTS,
                              "project_resource_id": PROJECT["id"]})
print("Lab 1 complete: project and chat inference verified. Continue with Lab 4.")
