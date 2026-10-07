from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
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
import validate_workshop  # noqa: E402
from common import model_resilience, resource_names  # noqa: E402
from py_to_ipynb import build_notebook, validate_cell_descriptions, validate_step_ids  # noqa: E402


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


class GuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guardrails = load("payment_promise_guardrails", ROOT / "common/guardrails.py")

    def test_payment_promise_detector_allows_explicit_disclaimers(self) -> None:
        disclaimers = (
            "A resubmission is reviewed under the plan rules, and payment is not guaranteed.",
            "I cannot promise that any resubmission will be paid.",
            "There is no guarantee that the claim will be approved.",
            "Resubmitting does not mean the claim will be covered.",
        )
        for text in disclaimers:
            with self.subTest(text=text):
                self.assertFalse(self.guardrails.contains_payment_promise(text))

    def test_payment_promise_detector_rejects_positive_outcomes(self) -> None:
        promises = (
            "Your resubmission will be paid.",
            "Payment is guaranteed.",
            "I guarantee payment after resubmission.",
            "Payment is not guaranteed, but your claim will be paid.",
        )
        for text in promises:
            with self.subTest(text=text):
                self.assertTrue(self.guardrails.contains_payment_promise(text))


class DeploymentTests(unittest.TestCase):
    def test_artifact_chain_requires_correct_predecessor_and_checkpoint(self):
        valid = ast.parse('helpers.require_artifact("lab3", "hosted.json", through=3, caller="lab4")')
        validate_workshop.validate_artifact_chain(valid, "lab4")
        for source in (
            'helpers.require_artifact("lab3", "hosted.json", through=2, caller="lab4")',
            'helpers.require_artifact("lab2", "hosted.json", through=2, caller="lab4")',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_workshop.validate_artifact_chain(ast.parse(source), "lab4")

    def test_internal_catch_up_skips_project_provisioning(self):
        module = load("catch_up_regression", ROOT / "labs/catch_up.py")
        self.assertEqual(set(module.STEPS), set(range(2, 8)))
        for number, (relative, _) in module.STEPS.items():
            self.assertTrue((ROOT / "labs" / relative).is_file(), f"missing Lab {number} driver")
        knowledge = MagicMock()
        with patch.object(module.helpers, "load_lab_module", return_value=knowledge):
            self.assertTrue(module.run_step(3, skip_connection=True))
        knowledge.build.assert_called_once_with(skip_connection=True)
        operate = MagicMock()
        with patch.object(module.helpers, "load_lab_module", return_value=operate):
            self.assertTrue(module.run_step(5))
        operate.build.assert_called_once_with(skip_judges=True)
        operate.demo.assert_called_once_with(operate.build.return_value, limit=6)

    def test_stretch7_vendoring_removes_generated_python_artifacts(self):
        prepare_paths = (
            ROOT / "labs/stretch7-invocations-toolbox-skills/hosted-invocations/prepare.py",
            ROOT / "labs/stretch7-invocations-toolbox-skills/hosted-responses-skills/prepare.py",
        )
        for index, prepare_path in enumerate(prepare_paths):
            with self.subTest(package=prepare_path.parent.name), tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp) / "package"
                package.mkdir()
                module = load(f"stretch7_prepare_{index}", prepare_path)
                sources = {}
                for name in module.SOURCES:
                    source = Path(tmp) / f"{name}-source"
                    source.mkdir()
                    (source / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
                    sources[name] = source
                for filename in module.REQUIRED_ROOT_FILES:
                    (package / filename).touch()
                (package / ".agentignore").write_text(".azure/\n", encoding="utf-8")
                cache = package / "__pycache__"
                cache.mkdir()
                bytecode = cache / "main.cpython-314.pyc"
                bytecode.write_bytes(b"generated")
                with patch.object(module, "HERE", package), \
                        patch.object(module, "SOURCES", sources), \
                        patch.object(module, "MANIFEST", package / ".vendored.json"):
                    module.vendor()
                self.assertFalse(bytecode.exists())
                self.assertFalse(cache.exists())

    def test_stretch7_vendoring_retains_ignored_azd_environment_state(self):
        prepare_paths = (
            ROOT / "labs/stretch7-invocations-toolbox-skills/hosted-invocations/prepare.py",
            ROOT / "labs/stretch7-invocations-toolbox-skills/hosted-responses-skills/prepare.py",
        )
        for index, prepare_path in enumerate(prepare_paths):
            with self.subTest(package=prepare_path.parent.name), tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp) / "package"
                package.mkdir()
                module = load(f"stretch7_prepare_state_{index}", prepare_path)
                sources = {}
                for name in module.SOURCES:
                    source = Path(tmp) / f"{name}-source"
                    source.mkdir()
                    (source / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
                    sources[name] = source
                for filename in module.REQUIRED_ROOT_FILES:
                    (package / filename).touch()
                (package / ".agentignore").write_text(".azure/\n.env\n.env.*\n", encoding="utf-8")
                azd_environment = package / ".azure/dev"
                azd_environment.mkdir(parents=True)
                azd_config = package / ".azure/config.json"
                azd_config.write_text("{}\n", encoding="utf-8")
                azd_env = azd_environment / ".env"
                azd_env.write_text("AZURE_ENV_NAME=dev\n", encoding="utf-8")
                with patch.object(module, "HERE", package), \
                        patch.object(module, "SOURCES", sources), \
                        patch.object(module, "MANIFEST", package / ".vendored.json"):
                    module.vendor()
                    self.assertTrue(azd_config.is_file())
                    self.assertTrue(azd_env.is_file())
                    (package / ".env").write_text("SECRET=do-not-package\n", encoding="utf-8")
                    with self.assertRaisesRegex(SystemExit, r"forbidden package files: \.env"):
                        module.review()

    def test_lab2_smoke_can_disable_storage_without_changing_multiturn_default(self):
        module = load("lab2_storage_regression", ROOT / "labs/lab2-hosted-agent-basics/lab2_hosted_basics.py")
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

    def test_lab2_hosted_requirements_do_not_request_all_integrations(self):
        path = ROOT / "labs/lab2-hosted-agent-basics/hosted/requirements.txt"
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

    def test_deployment_submits_azd_up_without_interactive_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for filename in ("prepare.py", "main.py", "requirements.txt"):
                (folder / filename).touch()
            args = argparse.Namespace(folder=folder, settings=[], project_id="/project",
                                      project_endpoint="https://example.test", model="model",
                                      agent_name="agent-jd-4821", resource_suffix="jd-4821",
                                      protocol="responses", check_package=False)
            with patch.object(deployment, "check_toolchain"), patch.object(deployment, "check_endpoint"), \
                    patch.object(deployment, "configure_service_environment"), \
                    patch.object(deployment.subprocess, "run") as run:
                deployment.deploy(args)
            submitted = [call for call in run.call_args_list if call.args[0][:2] == ("azd", "up")]
            self.assertEqual(len(submitted), 1)
            self.assertEqual(submitted[0].args[0], ("azd", "up", "--no-prompt"))
            self.assertTrue(submitted[0].kwargs["check"])

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
            ("lab2-hosted-agent-basics/lab2_hosted_basics.py", {}),
            ("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py", {"hosted": {"model": "model"}}),
            ("lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py", {}),
            ("stretch7-invocations-toolbox-skills/stretch7_invocations.py", {}),
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

    def test_stretch7_driver_help_runs_as_a_script(self):
        script = ROOT / "labs/stretch7-invocations-toolbox-skills/stretch7_invocations.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--deploy", result.stdout)

    def test_stretch7_driver_loads_workshop_environment_module(self):
        script = ROOT / "labs/stretch7-invocations-toolbox-skills/stretch7_invocations.py"
        command = (
            "import runpy; "
            f"module = runpy.run_path({str(script)!r}, run_name='stretch7_test'); "
            "print(module['foundry_env'].__file__)"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            Path(result.stdout.strip()).resolve(),
            (ROOT / "common/foundry_env.py").resolve(),
        )

    def test_lab3_storage_uses_blob_or_files_not_redis(self):
        module = load(
            "migration_lab3_storage",
            ROOT / "labs/lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py",
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

    def test_lab4_uses_file_session_store_and_does_not_deploy_redis(self):
        main_path = ROOT / "labs/lab4-hosted-multi-agent-handoff/hosted/main.py"
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
                "migration_lab4_file_session_driver",
                ROOT / "labs/lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py",
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
            "lab1-foundry-project-models/lab1_project_models.py": "1",
            "lab2-hosted-agent-basics/lab2_hosted_basics.py": "2",
            "lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py": "3",
            "lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py": "4",
            "lab5-operate-hosted-agents/lab5_operate.py": "5",
            "stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py": "S6",
            "stretch7-invocations-toolbox-skills/stretch7_invocations.py": "S7",
        }
        for relative, prefix in cases.items():
            with self.subTest(driver=relative):
                text = (ROOT / "labs" / relative).read_text(encoding="utf-8")
                self.assertEqual(validate_step_ids(build_notebook(text), prefix), [])

    def test_lab2_formatted_header_is_generated_from_driver(self):
        path = ROOT / "labs/lab2-hosted-agent-basics/lab2_hosted_basics.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        first_cell = notebook["cells"][0]
        header = "".join(first_cell["source"])
        self.assertEqual(first_cell["cell_type"], "markdown")
        self.assertTrue(header.startswith("# Lab 2: Hosted agent basics\n"))
        self.assertIn("| Goal |", header)
        self.assertIn("**How to run.**", header)
        self.assertIn("Execute this notebook's cells in order", header)
        self.assertIn("## Before the first run", header)
        self.assertEqual(notebook["cells"][1]["cell_type"], "markdown")
        self.assertIn("This cell loads the workshop environment", "".join(notebook["cells"][1]["source"]))

    def test_walkthrough_headers_include_table_sourced_technology_focus(self):
        cases = {
            "lab2-hosted-agent-basics/lab2_hosted_basics.py": (
                "Hosted version; Responses",
                "`Agent`; `FoundryChatClient`; `@tool`",
            ),
            "lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py": (
                "Foundry IQ; Search; MCP",
                "`MCPStreamableHTTPTool`; history",
            ),
            "lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py": (
                "Hosted triage; HTTP turns",
                "`WorkflowBuilder`; `request_info`",
            ),
            "lab5-operate-hosted-agents/lab5_operate.py": (
                "Tracing; evaluation; versions",
                "Evaluate the Framework-built agent",
            ),
            "stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py": (
                "`PromptAgentDefinition`; YAML workflow",
                "Hosted `@tool` bridge, not a new graph",
            ),
            "stretch7-invocations-toolbox-skills/stretch7_invocations.py": (
                "Invocations; optional Toolbox",
                "`InvocationsHostServer`; `@tool`; schema",
            ),
        }
        for relative, (foundry_topics, framework_topics) in cases.items():
            with self.subTest(driver=relative):
                path = ROOT / "labs" / relative
                notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
                header = " ".join("".join(notebook["cells"][0]["source"]).split())
                expected = (
                    f"**Technology focus.** This lab uses Microsoft Foundry ({foundry_topics}) "
                    f"and Microsoft Agent Framework ({framework_topics})."
                )
                self.assertIn(expected, header)

    def test_walkthrough_cells_have_descriptions_and_omit_cli_and_raw_shell_cells(self):
        cases = (
            ("lab1-foundry-project-models/lab1_project_models.py", "lab1_walkthrough.ipynb"),
            ("lab2-hosted-agent-basics/lab2_hosted_basics.py", "lab2_walkthrough.ipynb"),
            ("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py", "lab3_walkthrough.ipynb"),
            ("lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py", "lab4_walkthrough.ipynb"),
            ("lab5-operate-hosted-agents/lab5_operate.py", "lab5_walkthrough.ipynb"),
            ("stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py", "stretch6_walkthrough.ipynb"),
            ("stretch7-invocations-toolbox-skills/stretch7_invocations.py", "stretch7_walkthrough.ipynb"),
        )
        for relative, notebook_name in cases:
            with self.subTest(driver=relative):
                path = ROOT / "labs" / relative
                notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
                self.assertEqual(
                    json.loads(path.with_name(notebook_name).read_text(encoding="utf-8"))["cells"],
                    notebook["cells"],
                )
                self.assertEqual(validate_cell_descriptions(notebook), [])
                for index, cell in enumerate(notebook["cells"]):
                    source = "".join(cell["source"])
                    self.assertNotEqual(cell["cell_type"], "raw", "Shell tasks must be executable Python cells.")
                    if cell["cell_type"] == "markdown":
                        for forbidden in ("script mode", "script-only", "JupyterLab", "Bash terminal", "# %%", "```bash"):
                            self.assertNotIn(forbidden, source)
                        continue
                    self.assertEqual(cell["cell_type"], "code")
                    self.assertIsNone(cell["execution_count"])
                    self.assertEqual(cell["outputs"], [])
                    ast.parse(source)
                    self.assertNotIn("argparse.ArgumentParser", source)
                    self.assertNotIn('if __name__ == "__main__"', source)
                    description = "".join(notebook["cells"][index - 1]["source"])
                    sentences = re.findall(r"(?m)^This (?:optional )?cell [^\n]+$", description)
                    self.assertEqual(len(sentences), 1, "Each code cell needs one explicit description sentence.")
                    sentence = re.sub(r"`[^`]*`", "", sentences[0])
                    self.assertTrue(sentence.endswith("."), "The description must be a complete sentence.")
                    self.assertEqual(len(re.findall(r"[.!?](?:\s|$)", sentence)), 1)

    def test_lab3_build_is_executable_from_the_notebook(self):
        path = ROOT / "labs/lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        build_cell = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
            and cell["source"][0].startswith("# Step 3.2 -")
        )
        self.assertIn('if "__file__" not in globals():\n    hosted = build()', build_cell)

    def test_lab4_classifier_gate_reports_results_without_false_success(self):
        path = ROOT / "labs/lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        self.assertEqual(
            json.loads(path.with_name("lab4_walkthrough.ipynb").read_text(encoding="utf-8")),
            notebook,
        )
        gate = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
            and cell["source"][0].startswith("# Step 4.11 -")
        )
        for lob, status in (("accounts", "approved"), ("both", "approved"), ("accounts", "declined")):
            with self.subTest(lob=lob, status=status):
                logger = MagicMock()
                uuid = MagicMock()
                uuid.uuid4.return_value.hex = "offline123"
                send = MagicMock(side_effect=[
                    ({"status": "pending_advisor_approval", "packet": {"lob": lob}}, "response-1"),
                    ({"status": status}, "response-2"),
                ])
                namespace = {
                    "RUN_LAB4_EXERCISE_GATES": True,
                    "build": MagicMock(),
                    "uuid": uuid,
                    "HostedProcess": MagicMock(),
                    "post_turn": send,
                    "LOCAL_BASE": "http://localhost:8088",
                    "PENDING": "pending_advisor_approval",
                    "json": json,
                    "log": logger,
                }
                if lob == "accounts" and status == "approved":
                    exec(gate, namespace)
                    messages = [call.args[0] for call in logger.call_args_list]
                    self.assertEqual(len(messages), 4)
                    self.assertIn("participant> My card was declined", messages[0])
                    self.assertIn("lob=accounts, status=pending_advisor_approval", messages[1])
                    self.assertIn("advisor> approve (automatic)", messages[2])
                    self.assertEqual(
                        messages[3],
                        "PASS Step 4.11: routed to accounts; advisor approval completed (status=approved).",
                    )
                    advisor_turn = json.loads(send.call_args.args[1])
                    self.assertEqual(advisor_turn["advisor"], "approve")
                    self.assertEqual(send.call_args.args[2], "response-1")
                else:
                    with self.assertRaises(AssertionError):
                        exec(gate, namespace)
                    self.assertFalse(any(
                        "PASS" in call.args[0] for call in logger.call_args_list
                    ))

    def test_lab3_embedding_retries_at_the_service_requested_time(self):
        module = load(
            "migration_lab3_embedding_retry",
            ROOT / "labs/lab3-hosted-knowledge-sessions/knowledge_base.py",
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

        with patch.object(module, "aoai_resource_url", return_value="https://example.openai.azure.com"), \
                patch.object(module, "AzureOpenAI", return_value=client), \
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
            "labs/lab2-hosted-agent-basics/hosted/main.py",
            "labs/lab3-hosted-knowledge-sessions/hosted/main.py",
            "labs/lab4-hosted-multi-agent-handoff/hosted/main.py",
            "labs/stretch7-invocations-toolbox-skills/hosted-responses-skills/main.py",
            "labs/stretch7-invocations-toolbox-skills/hosted-invocations/main.py",
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
            "labs/lab2-hosted-agent-basics/lab2_hosted_basics.py",
            "labs/lab2-hosted-agent-basics/hosted/test_local.py",
            "labs/lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py",
            "labs/lab3-hosted-knowledge-sessions/hosted/test_local.py",
            "labs/lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py",
            "labs/lab4-hosted-multi-agent-handoff/hosted/test_local.py",
        )
        for relative_path in paths:
            with self.subTest(path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("model_resilience.ensure_response_succeeded(payload,", source)

    def test_lab3_ask_surfaces_failed_response_details(self):
        module = load(
            "migration_lab3_failed_response",
            ROOT / "labs/lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py",
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


class Lab5TracingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load(
            "lab5_tracing_regression",
            ROOT / "labs/lab5-operate-hosted-agents/lab5_operate.py",
        )

    def test_malformed_project_connection_string_disables_optional_tracing(self):
        project = MagicMock()
        project.telemetry.get_application_insights_connection_string.return_value = "not-a-connection-string"
        with patch.object(self.module, "ENV", {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}), \
                patch.object(self.module.foundry_env, "get_project_client", return_value=project):
            self.assertEqual(self.module.tracing_config(), {"enabled": False, "source": None})

    def test_local_tracing_uses_entra_authentication(self) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.monitor.opentelemetry import configure_azure_monitor

        credential = MagicMock(spec=DefaultAzureCredential)
        tracing = {"enabled": True, "connection_string": "InstrumentationKey=example"}
        with patch("azure.identity.DefaultAzureCredential", return_value=credential) as create_credential, \
                patch("azure.monitor.opentelemetry.configure_azure_monitor", spec=configure_azure_monitor) as configure:
            self.module.configure_local_tracing(tracing)
            configure.assert_called_once_with(
                connection_string=tracing["connection_string"], credential=credential,
            )
            create_credential.assert_called_once_with()
            self.module.configure_local_tracing({"enabled": False})
            configure.assert_called_once()

    def test_hosted_tracing_uses_entra_authentication(self) -> None:
        path = ROOT / "labs/lab3-hosted-knowledge-sessions/hosted/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "configure_tracing")
        create_credential = MagicMock()
        namespace = {"os": os, "DefaultAzureCredential": create_credential, "log": MagicMock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        with patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=example"}), \
                patch("azure.monitor.opentelemetry.configure_azure_monitor") as configure, \
                patch("agent_framework.observability.configure_otel_providers") as instrument:
            self.assertTrue(namespace["configure_tracing"]())
            configure.assert_called_once_with(
                connection_string="InstrumentationKey=example",
                credential=create_credential.return_value,
            )
            create_credential.assert_called_once_with()
            instrument.assert_called_once_with()

    def test_trace_gate_prints_kql_for_the_current_trace_id(self) -> None:
        path = ROOT / "labs/lab5-operate-hosted-agents/lab5_operate.py"
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        gate = next(
            "".join(cell["source"]) for cell in notebook["cells"]
            if cell["cell_type"] == "code" and cell["source"][0].startswith("# Step 5.11 -")
        )
        trace_id = "1234567890abcdef1234567890abcdef"
        bundle = {"tracing": {"enabled": True}, "hosted": {}, "knowledge": {}, "custom": {}, "judges": {}}
        row = {"id": "GQ-01", "query": "hello", "response": "safe answer", "citations": [], "trace_id": trace_id}
        with patch.object(self.module, "configure_local_tracing"), \
                patch.object(self.module, "flush_local_tracing"), \
                patch.object(self.module, "HostedTarget"), \
                patch.object(self.module, "load_golden", return_value=[row]), \
                patch.object(self.module, "answer", return_value=row), \
                patch.object(self.module, "write_report"), \
                patch("builtins.print") as output:
            namespace = {"build": MagicMock(return_value=bundle), "demo": self.module.demo}
            exec(gate, namespace)
        output = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertIn("union requests, dependencies", output)
        self.assertIn(f'| where operation_Id == "{trace_id}"', output)
        self.assertIn("| where timestamp > ago(1h)", output)
        self.assertNotIn("<printed-trace-id>", output)
        self.assertEqual(output.count("union requests, dependencies"), 1)

    def test_export_timeout_preserves_results_and_prints_kql_without_false_success(self) -> None:
        trace_id = "1234567890abcdef1234567890abcdef"
        bundle = {"tracing": {"enabled": True}, "hosted": {}, "knowledge": {}, "custom": {}, "judges": {}}
        row = {"id": "GQ-01", "query": "hello", "response": "safe answer", "citations": [], "trace_id": trace_id}
        target = MagicMock(mode="local")
        events = []
        with patch.object(self.module, "configure_local_tracing"), \
                patch.object(self.module, "HostedTarget", return_value=target), \
                patch.object(self.module, "load_golden", return_value=[row]), \
                patch.object(self.module, "answer", return_value=row), \
                patch.object(self.module, "write_report", side_effect=lambda *_: events.append("saved")) as report, \
                patch.object(self.module, "flush_local_tracing",
                             side_effect=RuntimeError("export flush timed out")), \
                patch("builtins.print") as output, \
                self.assertRaisesRegex(RuntimeError, "export flush timed out"):
            self.module.demo(bundle, limit=1)
        target.close.assert_called_once()
        report.assert_called_once()
        self.assertEqual(events, ["saved"])
        self.assertEqual(report.call_args.args[0][0]["trace_id"], trace_id)
        output = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertIn(f'| where operation_Id == "{trace_id}"', output)
        self.assertNotIn("PASS", output)
        self.assertNotIn("next: python ./eval_gate.py", output)

    def test_local_quality_gate_build_can_skip_tracing(self):
        missing_lab4 = ROOT / "labs/artifacts/lab4/missing-hosted.json"
        artifacts = [
            {"agent_name": "concierge", "version_label": "test", "local_url": "http://localhost:8088"},
            {"index_name": "plans"},
        ]
        with patch.object(self.module.helpers, "require_artifact", side_effect=artifacts), \
                patch.object(self.module.helpers, "artifact_path", return_value=missing_lab4), \
                patch.object(self.module.foundry_env, "save_artifact"), \
                patch.object(self.module, "write_pipeline_md"), \
                patch.object(self.module, "tracing_config", side_effect=AssertionError("tracing should be skipped")):
            bundle = self.module.build(skip_judges=True, enable_tracing=False)
        self.assertEqual(bundle["tracing"], {"enabled": False, "source": None})

    def test_answer_records_a_searchable_trace_id(self) -> None:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        self.addCleanup(provider.shutdown)
        target = MagicMock(mode="local")
        target.ask.return_value = "A licensed advisor can compare the available plans."
        item = {"id": "GQ-01", "participant_id": "P-1001", "context": "marketplace", "query": "hello"}
        with patch.object(self.module, "tracer", return_value=provider.get_tracer("offline")), \
                patch("builtins.print") as output:
            row = self.module.answer({"tracing": {"enabled": True}}, target, item)
        span, = exporter.get_finished_spans()
        self.assertEqual(row["trace_id"], f"{span.context.trace_id:032x}")
        self.assertEqual(span.name, "marketplace.golden_question")
        self.assertEqual(span.attributes["marketplace.golden_id"], "GQ-01")
        self.assertTrue(any(row["trace_id"] in call.args[0] for call in output.call_args_list))

    def test_demo_returns_trace_ids_for_the_notebook_query(self) -> None:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        self.addCleanup(provider.shutdown)
        target = MagicMock(mode="local")
        target.ask.return_value = "safe answer"
        bundle = {"tracing": {"enabled": True}, "hosted": {}, "knowledge": {}, "custom": {}, "judges": {}}
        with patch.object(self.module, "configure_local_tracing"), \
                patch.object(self.module, "flush_local_tracing") as flush, \
                patch.object(self.module, "HostedTarget", return_value=target), \
                patch.object(self.module, "load_golden", return_value=[{"id": "GQ-01", "query": "hello"}]), \
                patch.object(self.module, "tracer", return_value=provider.get_tracer("offline")), \
                patch.object(self.module, "write_report") as report:
            summary = self.module.demo(bundle, limit=1)
        span, = exporter.get_finished_spans()
        self.assertEqual(summary["trace_ids"], [f"{span.context.trace_id:032x}"])
        self.assertEqual(summary["questions"], 1)
        target.close.assert_called_once()
        flush.assert_called_once_with(bundle["tracing"])
        self.assertEqual(report.call_args.args[0][0]["trace_id"], summary["trace_ids"][0])

    def test_trace_gate_rejects_a_nonrecording_span(self) -> None:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

        provider = TracerProvider(sampler=ALWAYS_OFF)
        self.addCleanup(provider.shutdown)
        target = MagicMock(mode="local")
        target.ask.return_value = "safe answer"
        with patch.object(self.module, "tracer", return_value=provider.get_tracer("offline")), \
                self.assertRaisesRegex(RuntimeError, "not recording"):
            self.module.answer({"tracing": {"enabled": True}}, target, {"query": "hello"})
        target.ask.assert_not_called()

    def test_tracing_flushes_and_reports_a_timeout(self) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        self.addCleanup(provider.shutdown)
        with patch.object(trace, "get_tracer_provider", return_value=provider), \
                patch.object(provider, "force_flush", return_value=True) as flush:
            self.module.flush_local_tracing({"enabled": True})
            flush.assert_called_once()
            self.module.flush_local_tracing({"enabled": False})
            flush.assert_called_once()
        with patch.object(trace, "get_tracer_provider", return_value=provider), \
                patch.object(provider, "force_flush", return_value=False), \
                self.assertRaisesRegex(RuntimeError, "flush timed out"):
            self.module.flush_local_tracing({"enabled": True})

    def test_local_request_propagates_the_question_trace_context(self) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        lab3 = self.module.helpers.load_lab_module(
            "lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py"
        )
        provider = TracerProvider()
        self.addCleanup(provider.shutdown)
        response = MagicMock()
        response.json.return_value = {"output_text": "safe answer"}
        with provider.get_tracer("offline").start_as_current_span("marketplace.golden_question") as span, \
                patch("httpx.post", return_value=response) as post:
            lab3.ask(8088, "hello", "eval-offline")
        headers = post.call_args.kwargs["headers"]
        context = TraceContextTextMapPropagator().extract(headers)
        parent = trace.get_current_span(context).get_span_context()
        self.assertEqual(parent.trace_id, span.get_span_context().trace_id)
        self.assertEqual(parent.span_id, span.get_span_context().span_id)
        self.assertTrue(parent.is_remote)
        self.assertEqual(post.call_args.kwargs["json"], {
            "input": "hello", "stream": False, "conversation": "eval-offline",
        })


class Lab5HostedTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load(
            "lab5_hosted_target_regression",
            ROOT / "labs/lab5-operate-hosted-agents/lab5_operate.py",
        )
        cls.lab3 = cls.module.helpers.load_lab_module(
            "lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py"
        )

    def test_local_target_uses_lab3_process_api_and_forwards_tracing(self) -> None:
        knowledge = {"mcp_endpoint": "https://example.test/mcp"}
        for connection in (None, "InstrumentationKey=example"):
            with self.subTest(connection=connection):
                tracing = {"enabled": connection is not None, "connection_string": connection}
                with patch.object(self.module.helpers, "load_lab_module", return_value=self.lab3), \
                        patch.object(self.lab3, "port_open", return_value=False), \
                        patch.object(self.lab3.HostedProcess, "start", autospec=True,
                                     side_effect=lambda server: server) as start, \
                        patch.object(self.lab3.HostedProcess, "stop", autospec=True) as stop, \
                        patch.object(self.lab3, "ask", return_value=("safe answer", {})) as ask, \
                        patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": "inherited"}):
                    target = self.module.HostedTarget("local", {}, knowledge, tracing)
                    start.assert_called_once_with(target.proc)
                    self.assertEqual(target.proc.knowledge, knowledge)
                    self.assertEqual(target.proc.port, self.module.LOCAL_PORT)
                    self.assertEqual(target.proc.env_overrides, {
                        "APPLICATIONINSIGHTS_CONNECTION_STRING": connection,
                    })
                    self.assertEqual(os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"], "inherited")
                    self.assertEqual(target.ask("hello"), "safe answer")
                    self.assertEqual(ask.call_args.args[:2], (self.module.LOCAL_PORT, "hello"))
                    self.assertTrue(ask.call_args.args[2].startswith("eval-"))
                    target.close()
                    stop.assert_called_once_with(target.proc)

    def test_local_target_does_not_stop_an_existing_server(self) -> None:
        with patch.object(self.module.helpers, "load_lab_module", return_value=self.lab3), \
                patch.object(self.lab3, "port_open", return_value=True), \
                patch.object(self.lab3.HostedProcess, "start", autospec=True) as start, \
                patch.object(self.lab3.HostedProcess, "stop", autospec=True) as stop:
            target = self.module.HostedTarget("local", {}, {}, {"enabled": False})
            self.assertIsNone(target.proc)
            target.close()
            start.assert_not_called()
            stop.assert_not_called()


class PromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load("migration_promote", ROOT / "labs/lab5-operate-hosted-agents/promote.py")

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
