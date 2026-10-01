from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "labs"))
sys.path.insert(0, str(ROOT / "tools"))
import deployment  # noqa: E402
from common import model_resilience, resource_names  # noqa: E402
from py_to_ipynb import build_notebook, validate_step_ids  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class MessageSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if importlib.util.find_spec("agent_framework") is None:
            raise unittest.SkipTest("Agent Framework is required for SDK serialization tests.")
        cls.module = load("message_store_regression", ROOT / "common/message_store.py")

    def test_legacy_text_rows_round_trip_without_mutating_input(self) -> None:
        for text in ("hello", ""):
            with self.subTest(text=text):
                row = {"role": "user", "text": text}
                messages = self.module.deserialize_messages(self.module.serialize_messages([row]))
                self.assertEqual(messages[0].text, text)
                self.assertEqual(messages[0].role, "user")
                self.assertEqual(row, {"role": "user", "text": text})

    def test_sdk_contents_and_metadata_are_preserved(self) -> None:
        from agent_framework import Message

        original = Message.from_dict({
            "role": "assistant",
            "message_id": "message-1",
            "author_name": "advisor",
            "contents": [
                {"type": "text", "text": "Checking eligibility."},
                {"type": "function_call", "call_id": "call-1",
                 "name": "get_participant", "arguments": '{"participant_id":"P-1001"}'},
            ],
        })
        result = self.module.deserialize_messages(self.module.serialize_messages([original]))
        self.assertEqual(result[0].to_dict(), original.to_dict())

    def test_sdk_deserialization_errors_are_not_silently_downgraded(self) -> None:
        from agent_framework import Message

        with patch.object(Message, "from_dict", side_effect=ValueError("Invalid message")), \
                self.assertRaisesRegex(ValueError, "Invalid message"):
            self.module.message_from_dict({"role": "user", "text": "hello"})

    def test_without_sdk_returns_an_independent_dict(self) -> None:
        row = {"role": "user", "text": "hello"}
        with patch.dict(sys.modules, {"agent_framework": None}):
            result = self.module.message_from_dict(row)
        self.assertEqual(result, row)
        self.assertIsNot(result, row)


class DeploymentTests(unittest.TestCase):
    def test_lab1_smoke_can_disable_storage_without_changing_multiturn_default(self):
        module = load("lab1_storage_regression", ROOT / "labs/lab1-hosted-agent-basics/lab1_hosted_basics.py")
        project = MagicMock()
        client = project.get_openai_client.return_value.with_options.return_value.__enter__.return_value
        client.responses.create.return_value.output_text = "ready"
        with patch.object(module.foundry_env, "get_project_client") as factory:
            factory.return_value.__enter__.return_value = project
            result = module.call_deployed("hello", store=False)
            self.assertEqual(result["text"], "ready")
            client.responses.create.assert_called_with(input="hello", store=False)
            project.get_openai_client.return_value.with_options.assert_called_with(timeout=120.0, max_retries=0)
            module.call_deployed("next", previous_response_id="response-1")
            client.responses.create.assert_called_with(input="next", store=True, previous_response_id="response-1")

    def test_lab1_hosted_requirements_do_not_request_all_integrations(self):
        path = ROOT / "labs/lab1-hosted-agent-basics/hosted/requirements.txt"
        requirements = {
            line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        self.assertIn("agent-framework-core==1.9.0", requirements)
        self.assertIn("agent-framework-openai==1.8.2", requirements)
        self.assertIn("mcp==1.28.1", requirements)
        self.assertFalse(any(line.startswith(("agent-framework==", "agent-framework[",
                                             "agent-framework-core[")) for line in requirements))
        root_pins = set((ROOT.parent / "requirements.txt").read_text().splitlines())
        self.assertTrue(requirements <= root_pins, "Hosted runtime pins must match the workstation lock.")

    def test_bash_quoting_preserves_arguments(self):
        env = {
            "PROJECT_RESOURCE_ID": "/subscriptions/example/projects/it's $(not-a-command)",
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/api/projects/demo",
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": "model with spaces",
            "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821",
        }
        block = deployment.bash_deploy_block(
            Path("folder with ' quotes"), "agent-jd-4821", "responses", env
        )
        args = shlex.split(block.splitlines()[3])
        self.assertEqual(args[args.index("--project-id") + 1], env["PROJECT_RESOURCE_ID"])
        self.assertEqual(args[args.index("--model") + 1], env["AZURE_AI_MODEL_DEPLOYMENT_NAME"])
        self.assertIn("set -euo pipefail", block)

    def test_generation_never_executes(self):
        with patch.object(deployment.subprocess, "run") as run:
            deployment.bash_deploy_block(Path("."), "agent-jd-4821", "responses", {
                "PROJECT_RESOURCE_ID": "/project", "FOUNDRY_PROJECT_ENDPOINT": "https://example.test",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "model", "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821",
            })
        run.assert_not_called()

    def test_placeholder_and_local_redis_rejected(self):
        with self.assertRaises(ValueError):
            deployment.checked_value("project", "<your-project>")
        for hostname in ("localhost", "127.0.0.1", "redis"):
            with self.subTest(hostname=hostname), self.assertRaises(ValueError):
                deployment.validate_cloud_settings({"MARKETPLACE_REDIS_URL": f"redis://{hostname}:6379/0"})

    def test_failed_prepare_stops_before_azd(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for filename in ("prepare.py", "main.py", "requirements.txt"):
                (folder / filename).touch()
            args = argparse.Namespace(folder=folder, settings=[], project_id="/project",
                                      project_endpoint="https://example.test", model="model",
                                      agent_name="agent-jd-4821", resource_suffix="jd-4821",
                                      protocol="responses", check_package=False)
            with patch.object(deployment, "check_toolchain"), patch.object(deployment, "check_endpoint"), \
                    patch.object(deployment.subprocess, "run",
                                 side_effect=subprocess.CalledProcessError(2, "prepare.py")) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    deployment.deploy(args)
                self.assertEqual(run.call_count, 1)

    def test_generated_agent_service_references_container_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "azure.yaml"
            manifest.write_text(
                "name: hosted\n"
                "services:\n"
                "    test-agent:\n"
                "        project: .\n"
                "        env:\n"
                "            AZURE_AI_MODEL_DEPLOYMENT_NAME: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}\n"
                "        kind: hosted\n"
                "    test-project:\n"
                "        host: azure.ai.project\n",
                encoding="utf-8",
            )

            deployment.configure_service_environment(
                manifest,
                "test-agent",
                {"MARKETPLACE_AGENT_NAME", "MARKETPLACE_KB_MCP_URL"},
            )

            content = manifest.read_text(encoding="utf-8")
            self.assertIn("            MARKETPLACE_AGENT_NAME: ${MARKETPLACE_AGENT_NAME}\n", content)
            self.assertIn("            MARKETPLACE_KB_MCP_URL: ${MARKETPLACE_KB_MCP_URL}\n", content)
            self.assertEqual(content.count("AZURE_AI_MODEL_DEPLOYMENT_NAME"), 2)
            self.assertLess(content.index("MARKETPLACE_KB_MCP_URL"), content.index("    test-project:"))

    def test_minimum_azd_version(self):
        with patch.object(deployment.shutil, "which", return_value="/bin/tool"):
            for version in ("1.34.1", "unparseable"):
                with self.subTest(version=version), \
                        patch.object(deployment.subprocess, "check_output", return_value=version), \
                        self.assertRaises(RuntimeError):
                    deployment.check_toolchain()
            with patch.object(deployment.subprocess, "check_output", return_value="azd version 1.34.2"):
                deployment.check_toolchain()

    def test_all_driver_generators_emit_bash(self):
        env = {"PROJECT_RESOURCE_ID": "/project", "FOUNDRY_PROJECT_ENDPOINT": "https://example.test",
               "AZURE_AI_MODEL_DEPLOYMENT_NAME": "model", "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821"}
        cases = [
            ("lab1-hosted-agent-basics/lab1_hosted_basics.py", {}),
            ("lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py", {"hosted": {"model": "model"}}),
            ("lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py", {}),
            ("stretch6-invocations-toolbox-skills/stretch6_invocations.py", {}),
        ]
        with patch.dict(os.environ, {"MARKETPLACE_RESOURCE_SUFFIX": "jd-4821"}, clear=True):
            for index, (filename, kwargs) in enumerate(cases):
                with self.subTest(driver=filename):
                    module = load(f"migration_driver_{index}", ROOT / "labs" / filename)
                    block = module.deploy_commands(env, **kwargs)
                    self.assertIn("set -euo pipefail", block)
                    self.assertNotIn("PowerShell", block)
                    self.assertNotIn("$LASTEXITCODE", block)
                    commands = [shlex.split(line) for line in block.splitlines() if line.startswith("python ")]
                    self.assertEqual(len(commands), 2 if index == 3 else 1)
                    for command in commands:
                        self.assertIn("--project-endpoint", command)

    def test_lab2_storage_uses_blob_or_files_not_redis(self):
        module = load(
            "migration_lab2_storage",
            ROOT / "labs/lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py",
        )
        container_env = module.container_environment(
            {"mcp_endpoint": "https://example.test/mcp"},
            {
                "MARKETPLACE_REDIS_URL": "rediss://cache.example.test:10000/0",
                "MARKETPLACE_BLOB_STORAGE_URL": "https://storage.example.test",
                "MARKETPLACE_BLOB_STORAGE_CONTAINER": "history",
            },
        )
        self.assertNotIn("MARKETPLACE_REDIS_URL", container_env)
        self.assertEqual(container_env["MARKETPLACE_BLOB_STORAGE_URL"], "https://storage.example.test")
        self.assertNotIn("redis", module.HOSTED_DIR.joinpath("requirements.txt").read_text().lower())

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_process = MagicMock()
            fake_process.poll.return_value = None
            hosted = module.HostedProcess({}, log_path=Path(temp_dir) / "hosted.log")
            with patch.dict(os.environ, {"MARKETPLACE_REDIS_URL": "redis://redis:6379/0"}), \
                    patch.object(module, "LABS_DIR", Path(temp_dir)), \
                    patch.object(module, "port_open", side_effect=[False, True]), \
                    patch.object(module.subprocess, "Popen", return_value=fake_process) as popen:
                hosted.start()
                self.assertNotIn("MARKETPLACE_REDIS_URL", popen.call_args.kwargs["env"])
                hosted.stop()

        with patch.object(module, "ENV", {
            "MARKETPLACE_REDIS_URL": "redis://redis:6379/0",
            "MARKETPLACE_BLOB_STORAGE_URL": "",
            "MARKETPLACE_AZURITE_CONNECTION_STRING": "",
        }), patch.dict(os.environ, {"MARKETPLACE_REDIS_URL": "redis://redis:6379/0"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Azure Blob Storage or Azurite"):
                module.shared_history_env_overrides()

    def test_lab3_uses_file_session_store_and_does_not_deploy_redis(self):
        main_path = ROOT / "labs/lab3-hosted-multi-agent-handoff/hosted/main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))
        service = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TriageService")
        initializer = next(node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        session_assignment = next(
            node for node in ast.walk(initializer)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == "sessions" for target in node.targets)
        )
        self.assertEqual(session_assignment.value.func.attr, "FileSessionStore")

        with patch.dict(os.environ, {
            "MARKETPLACE_REDIS_URL": "redis://redis:6379/0",
            "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821",
        }):
            driver = load(
                "migration_lab3_file_session_driver",
                ROOT / "labs/lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py",
            )
            with patch.object(deployment, "bash_deploy_block", return_value="deploy") as deploy:
                driver.deploy_commands(env={"PROJECT_RESOURCE_ID": "/project"})
                self.assertNotIn("MARKETPLACE_REDIS_URL", deploy.call_args.args[4])

    def test_resource_names_require_and_apply_unique_suffix(self):
        env = {"MARKETPLACE_RESOURCE_SUFFIX": "JD-4821"}
        self.assertEqual(resource_names.suffix(env, required=True), "jd-4821")
        self.assertEqual(
            resource_names.name(resource_names.HOSTED_CONCIERGE, env, required=True),
            "healthcare-marketplace-concierge-hosted-jd-4821",
        )
        for value in ("", "<your-unique-suffix>", "local", "bad_suffix"):
            with self.subTest(value=value), self.assertRaises((RuntimeError, ValueError)):
                resource_names.suffix({"MARKETPLACE_RESOURCE_SUFFIX": value}, required=True)

    def test_every_walkthrough_code_block_has_consecutive_step_id(self):
        cases = {
            "lab1-hosted-agent-basics/lab1_hosted_basics.py": "1",
            "lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py": "2",
            "lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py": "3",
            "lab4-operate-hosted-agents/lab4_operate.py": "4",
            "stretch5-prompt-agents-and-workflows/stretch5_prompt_agents.py": "S5",
            "stretch6-invocations-toolbox-skills/stretch6_invocations.py": "S6",
        }
        for relative, prefix in cases.items():
            with self.subTest(driver=relative):
                text = (ROOT / "labs" / relative).read_text(encoding="utf-8")
                self.assertEqual(validate_step_ids(build_notebook(text), prefix), [])

    def test_lab1_formatted_header_is_generated_from_driver(self):
        path = ROOT / "labs/lab1-hosted-agent-basics/lab1_hosted_basics.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        first_cell = notebook["cells"][0]
        header = "".join(first_cell["source"])
        self.assertEqual(first_cell["cell_type"], "markdown")
        self.assertTrue(header.startswith("# Lab 1: Hosted agent basics\n"))
        self.assertIn("| Goal |", header)
        self.assertIn("**How to run code**", header)
        self.assertIn("## Before the first run", header)
        self.assertEqual(notebook["cells"][1]["cell_type"], "markdown")
        self.assertIn("Shell commands use the container filesystem", "".join(notebook["cells"][1]["source"]))

    def test_lab2_build_is_executable_from_the_notebook(self):
        path = ROOT / "labs/lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        build_cell = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
            and cell["source"][0].startswith("# Step 2.2 -")
        )
        self.assertIn('if "__file__" not in globals():\n    hosted = build()', build_cell)

    def test_lab2_embedding_retries_at_the_service_requested_time(self):
        module = load(
            "migration_lab2_embedding_retry",
            ROOT / "labs/lab2-hosted-knowledge-sessions/knowledge_base.py",
        )
        response = MagicMock()
        response.headers = {"x-ratelimit-limit-requests": "6"}
        response.parse.return_value.data = [MagicMock(embedding=[1.0, 2.0])]
        rate_limit_response = MagicMock()
        rate_limit_response.headers = {"retry-after": "60"}
        rate_limit = module.RateLimitError(
            "rate limited",
            response=rate_limit_response,
            body={"error": {"code": "RateLimitReached"}},
        )
        client = MagicMock()
        client.embeddings.with_raw_response.create.side_effect = [rate_limit, response]

        with patch.object(module, "AzureOpenAI", return_value=client), \
                patch.object(module, "get_bearer_token_provider"), \
                patch.object(module.time, "sleep") as sleep:
            embed = module.make_embedder(MagicMock())
            self.assertEqual(embed(["content"]), [[1.0, 2.0]])

        sleep.assert_called_once_with(60.0)
        self.assertEqual(client.embeddings.with_raw_response.create.call_count, 2)

    def test_hosted_chat_retries_and_reports_model_rate_limits(self):
        rate_limit = RuntimeError("rate limit exceeded")
        rate_limit.response = MagicMock(
            status_code=429,
            headers={
                "retry-after": "60",
                "x-ratelimit-limit-requests": "600",
                "x-ratelimit-limit-tokens": "100000",
            },
        )
        wrapped = RuntimeError("chat client failed")
        wrapped.inner_exception = rate_limit
        call_next = AsyncMock(side_effect=[wrapped, None])
        logs = []

        with patch.object(model_resilience.asyncio, "sleep", new=AsyncMock()) as sleep:
            model_resilience.asyncio.run(
                model_resilience.RateLimitRetryMiddleware(logs.append).process(MagicMock(), call_next)
            )

        sleep.assert_awaited_once_with(60.0)
        self.assertEqual(call_next.await_count, 2)
        self.assertIn("x-ratelimit-limit-tokens=100000", logs[0])

    def test_all_hosted_model_clients_install_rate_limit_retry(self):
        paths = (
            "labs/lab1-hosted-agent-basics/hosted/main.py",
            "labs/lab2-hosted-knowledge-sessions/hosted/main.py",
            "labs/lab3-hosted-multi-agent-handoff/hosted/main.py",
            "labs/stretch6-invocations-toolbox-skills/hosted-responses-skills/main.py",
            "labs/stretch6-invocations-toolbox-skills/hosted-invocations/main.py",
        )
        for relative_path in paths:
            with self.subTest(path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn(
                    "middleware=[model_resilience.RateLimitRetryMiddleware(log)]",
                    source,
                )

    def test_local_responses_clients_surface_failed_payloads(self):
        paths = (
            "labs/lab1-hosted-agent-basics/lab1_hosted_basics.py",
            "labs/lab1-hosted-agent-basics/hosted/test_local.py",
            "labs/lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py",
            "labs/lab2-hosted-knowledge-sessions/hosted/test_local.py",
            "labs/lab3-hosted-multi-agent-handoff/lab3_hosted_multi_agent.py",
            "labs/lab3-hosted-multi-agent-handoff/hosted/test_local.py",
        )
        for relative_path in paths:
            with self.subTest(path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("model_resilience.ensure_response_succeeded(payload,", source)

    def test_lab2_ask_surfaces_failed_response_details(self):
        module = load(
            "migration_lab2_failed_response",
            ROOT / "labs/lab2-hosted-knowledge-sessions/lab2_hosted_knowledge.py",
        )
        response = MagicMock()
        response.json.return_value = {
            "status": "failed",
            "output": [],
            "error": {"code": "server_error", "message": "rate_limit_exceeded: retry-after=60s"},
        }
        with patch("httpx.post", return_value=response), \
                self.assertRaisesRegex(RuntimeError, "response failed.*retry-after=60s"):
            module.ask(8088, "hello", "session-1")

    def test_step_validation_rejects_missing_and_duplicate_ids(self):
        notebook = build_notebook("# %% Step 2.1 - First\npass\n# %% Missing\npass\n")
        self.assertTrue(validate_step_ids(notebook, "2"))
        duplicate = build_notebook("# %% Step 2.1 - First\npass\n# %% Step 2.1 - Again\npass\n")
        self.assertTrue(validate_step_ids(duplicate, "2"))

    def test_cleanup_own_scope_contains_only_suffixed_resources(self):
        cleanup = load("cleanup_workshop_regression", ROOT / "tools/cleanup_workshop.py")
        env = {"MARKETPLACE_RESOURCE_SUFFIX": "jd-4821"}
        resources = cleanup.own_resources(env)
        self.assertTrue(resources)
        self.assertTrue(all("jd-4821" in item.name for item in resources))
        self.assertEqual(cleanup.project_name("/accounts/demo/projects/workshop"), "workshop")


class PromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load("migration_promote", ROOT / "labs/lab4-operate-hosted-agents/promote.py")

    def test_gate_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = Path(tmp) / "gate.json"
            with patch.object(self.module, "GATE_PATH", gate):
                for value in ({}, {"passed": False}, {"passed": True}):
                    gate.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        self.module.check_gate()

    def test_printed_promotion_is_explicit_and_quoted(self):
        block = self.module.bash_block("test", "tag'$(echo unsafe)")
        command = shlex.split(block.splitlines()[2])
        self.assertEqual(command[-2:], ["tag'$(echo unsafe)", "--execute"])
        self.assertIn("set -euo pipefail", block)

    def test_failed_smoke_never_tags_or_overwrites_environment_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env.test"
            content = ("FOUNDRY_PROJECT_ENDPOINT=https://example.test\n"
                       "PROJECT_RESOURCE_ID=/project\nAZURE_AI_MODEL_DEPLOYMENT_NAME=model\n")
            env_file.write_text(content)
            commands = []

            def run(command, **kwargs):
                commands.append(command)
                if "show-ref" in command:
                    return subprocess.CompletedProcess(command, 1)
                if "test_local.py" in command:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0)

            with patch.object(self.module, "ENVS_DIR", Path(tmp)), \
                    patch.object(self.module.subprocess, "run", side_effect=run), \
                    patch.object(self.module.subprocess, "check_output",
                                 return_value='{"AZURE_AI_PROJECT_ID": "/project"}'):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.module.execute("test", "new-tag")
            self.assertFalse(any(command[:2] == ("git", "tag") for command in commands))
            self.assertEqual(env_file.read_text(), content)


if __name__ == "__main__":
    unittest.main()
