"""Offline regression checks for the notebook-only learner interface."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from py_to_ipynb import (  # noqa: E402
    build_notebook,
    split_cells,
    validate_cell_descriptions,
    validate_notebook,
    validate_step_ids,
)
from validate_workshop import LAB_DEPENDENCIES, WALKTHROUGHS, validate_checkpoint_contract  # noqa: E402

INTERNAL_DRIVERS = (
    ("foundry-project-models/lab1_project_models.py", "lab1_walkthrough.ipynb", "1"),
    ("hosted-agent-basics/lab2_hosted_basics.py", "lab2_walkthrough.ipynb", "2"),
    ("hosted-knowledge-sessions/lab3_hosted_knowledge.py", "lab3_walkthrough.ipynb", "3"),
    ("hosted-multi-agent-handoff/lab4_hosted_multi_agent.py", "lab4_walkthrough.ipynb", "4"),
    ("operate-hosted-agents/lab5_operate.py", "lab5_walkthrough.ipynb", "5"),
    ("prompt-agents-and-workflows/stretch6_prompt_agents.py", "stretch6_walkthrough.ipynb", "S6"),
    ("invocations-toolbox-skills/stretch7_invocations.py", "stretch7_walkthrough.ipynb", "S7"),
)

DRIVERS = tuple(
    (f"{directory}/{source}", notebook, prefix)
    for directory, parts in WALKTHROUGHS.items()
    for source, notebook, prefix, _, _ in parts
)


def notebook_action(source: str) -> ast.Module:
    """Extract explicit notebook actions without importing cloud packages."""
    tree = ast.parse(source)
    return ast.Module(
        body=[
            node for node in tree.body
            if isinstance(node, ast.If) and ast.unparse(node.test) == "'__file__' not in globals()"
        ],
        type_ignores=[],
    )


class ConverterTests(unittest.TestCase):
    def test_each_numbered_folder_owns_exactly_one_documented_lab(self):
        self.assertEqual(list(WALKTHROUGHS), [f"lab{number}" for number in range(1, 15)])
        for folder, parts in WALKTHROUGHS.items():
            with self.subTest(folder=folder):
                self.assertEqual(len(parts), 1)
                source, notebook, number, _, _ = parts[0]
                directory = ROOT / "labs" / folder
                self.assertEqual(folder, f"lab{number}")
                self.assertEqual([path.name for path in directory.glob("*.ipynb")], [notebook])
                self.assertEqual([path.name for path in directory.glob("*.py")], [source])
                guide = (directory / "README.md").read_text(encoding="utf-8")
                self.assertTrue(guide.startswith(f"# Lab {number}:"))
                self.assertIn(f"]({notebook})", guide)
                self.assertIn("## Prerequisites", guide)
                self.assertIn("## Checkpoint", guide)

    def test_numbered_labs_have_matching_navigation_and_prerequisites(self):
        self.assertEqual([int(prefix) for _, _, prefix in DRIVERS], list(range(1, 15)))
        guide = (ROOT / "labs" / "README.md").read_text(encoding="utf-8")
        rows = {int(cells[1].strip()): cells for line in guide.splitlines()
                if re.match(r"^\| \d+ \|", line) and (cells := line.split("|"))}
        self.assertEqual(list(rows), list(range(1, 15)))
        for source, notebook_name, prefix in DRIVERS:
            with self.subTest(lab=prefix):
                number = int(prefix)
                path = ROOT / "labs" / source
                notebook_path = path.with_name(notebook_name)
                self.assertEqual(path.stem.split("_")[0], f"lab{number}")
                self.assertEqual(notebook_name, f"lab{number}_walkthrough.ipynb")
                notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
                introduction = "".join(notebook["cells"][0]["source"])
                self.assertTrue(introduction.startswith(f"# Lab {number}:"))
                self.assertIn("**Prerequisites:**", introduction)
                self.assertIn(notebook_path.relative_to(ROOT / "labs").as_posix(), rows[number][2])
                for predecessor in LAB_DEPENDENCIES[number]:
                    self.assertRegex(introduction, rf"\bLab {predecessor}\b")
                    self.assertRegex(rows[number][3], rf"\bLab {predecessor}\b")
                text = path.read_text(encoding="utf-8")
                self.assertEqual(set(re.findall(r"\bStep (\d+)\.", text)), {prefix})

    def test_checkpoint_contract_requires_scoped_real_handoffs(self):
        source = (
            "context = notebook_parts.scope(ENV)\n"
            "previous = notebook_parts.read_checkpoint(ARTIFACTS / 'part_a.json', "
            "lab='lab2', part='a', context=context)\n"
            "notebook_parts.write_checkpoint(ARTIFACTS / 'part_b.json', "
            "lab='lab2', part='b', context=context, state={'hosted': hosted})\n"
        )
        validate_checkpoint_contract(ast.parse(source), "lab2", "b")
        lines = source.splitlines()
        validate_checkpoint_contract(ast.parse("\n".join([lines[0], lines[1], lines[1], lines[2]])), "lab2", "b")
        for invalid in (
            source.replace("lab='lab2'", "lab='lab3'"),
            source.replace("part='a'", "part='b'"),
            source.replace("context=context", "context=None"),
            source.replace("'part_a.json'", "'part_b.json'"),
            source.replace("state={'hosted': hosted}", "state={}"),
            source.replace("state={'hosted': hosted}", "state={'complete': True}"),
            source.splitlines()[0] + "\n" + source.splitlines()[2],
        ):
            with self.subTest(source=invalid), self.assertRaises(ValueError):
                validate_checkpoint_contract(ast.parse(invalid), "lab2", "b")

    def test_all_fourteen_labs_publish_their_real_checkpoint_contract(self):
        count = 0
        for directory, parts in WALKTHROUGHS.items():
            for source, _, _, lab, part in parts:
                with self.subTest(source=source):
                    path = ROOT / "labs" / directory / source
                    validate_checkpoint_contract(ast.parse(path.read_text(encoding="utf-8")), lab, part)
                    count += 1
        self.assertEqual(count, 14)

    def test_fresh_b_kernels_restore_state_without_repeating_a_cloud_work(self):
        cases = (
            ("lab8", "lab8_advisor_recovery.py", "lab4",
             {"pending": {name: {"session_id": name} for name in ("S1", "S2", "S3")},
              "hosted": {"agent_name": "existing"}, "tested_sources": {"hosted": "synthetic-fingerprint"}}, "pending"),
            ("lab10", "lab10_release_rollback.py", "lab5",
             {"bundle": {"info": {"version": "measured"}}, "summary": {"questions": 6}}, "bundle"),
            ("lab12", "lab12_workflows_delegation.py", "stretch6",
             {"prompt_agents": {"agents": {"triage": {"agent_id": "existing", "agent_version": "3"}}}},
             "prompt_info"),
            ("lab14", "lab14_skills_toolbox.py", "stretch7",
             {"nightly": {"reviews": 3}, "invocations": {"agent_name": "existing"}}, "part_a"),
        )
        for directory, filename, lab, state, restored in cases:
            with self.subTest(lab=lab):
                path = ROOT / "labs" / directory / filename
                notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
                startup = next(cell for cell in notebook["cells"] if cell["cell_type"] == "code")
                action = compile(notebook_action("".join(startup["source"])), str(path), "exec")
                cloud = Mock(side_effect=AssertionError("B must not replay A's cloud work."))
                context = {"project": "current", "suffix": "current-attendee"}
                checkpoint = {"state": state}
                parts = SimpleNamespace(
                    read_checkpoint=Mock(return_value=checkpoint), scope=Mock(return_value=context),
                )
                artifacts = ROOT / "labs/artifacts" / lab
                files = {
                    artifacts / "pending_sessions.json": {
                        name: {"status": None, "packet": None} for name in ("S1", "S2", "S3")
                    },
                    artifacts / "hosted.json": {"agent_name": "existing"},
                    artifacts / "invocations.json": {
                        "agents": {"invocations": state.get("invocations")}, "sample_run": state.get("nightly"),
                    },
                    **{artifacts / "sessions" / f"{name}.json": {"notes": {}}
                       for name in ("S1", "S2", "S3")},
                }
                helpers = SimpleNamespace(artifact_path=lambda namespace, name: ROOT / "labs/artifacts" / namespace / name)
                driver = SimpleNamespace(
                    ENV={"current": "configuration"}, ARTIFACTS=artifacts,
                    HOSTED_RECORD=artifacts / "hosted.json", RECORD=artifacts / "invocations.json",
                    source_fingerprints=Mock(return_value=state.get("tested_sources", {})),
                    SPECS={"triage": {}}, build=cloud, demo=cloud, publish_prompt_agents=cloud,
                )
                namespace = {
                    "driver": driver, "notebook_parts": parts, "lab_helpers": helpers, "json": json,
                    "gate": SimpleNamespace(
                        RESULTS_PATH=artifacts / "eval_results.jsonl",
                        load_results=Mock(return_value=([{"response": "measured"}] * 6, [])),
                    ),
                }
                with patch.object(Path, "unlink"), patch.object(
                    Path, "read_text", autospec=True, side_effect=lambda path, **kwargs: json.dumps(files[path]),
                ):
                    exec(action, namespace)
                self.assertIn(restored, namespace)
                parts.read_checkpoint.assert_called_once_with(
                    artifacts / "part_a.json", lab=lab, part="a", context=context,
                )
                parts.scope.assert_called_once_with(driver.ENV)
                cloud.assert_not_called()
                parts.read_checkpoint.side_effect = RuntimeError("Run A first.")
                with patch.object(Path, "unlink"), self.assertRaisesRegex(RuntimeError, "Run A first"):
                    exec(action, {key: value for key, value in namespace.items() if key not in (
                        "part_a", "pending", "bundle", "rows", "load_errors", "prompt_info",
                    )})
                cloud.assert_not_called()

    def test_advisor_recovery_uses_durable_session_not_a_response_or_new_intake(self):
        path = ROOT / "labs/lab8/lab8_advisor_recovery.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        resume = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "resume_pending")
        namespace = {"json": json, "driver": SimpleNamespace(PENDING="pending")}
        exec(compile(ast.Module(body=[resume], type_ignores=[]), str(path), "exec"), namespace)
        packet = {
            "case_id": "S3", "participant_id": "synthetic-participant",
            "lob": "both", "advisor_decision": "approve",
        }
        send = Mock(side_effect=[
            ({"status": "pending", "resume_path": "session_store"}, "new-response"),
            ({"status": "approved", "packet": packet, "resume_path": "previous_response"}, "final-response"),
        ])
        restart = Mock()
        result, paths = namespace["resume_pending"](
            {"session_id": "persisted-session", "reply": {
                "status": "pending", "packet": {**packet, "advisor_decision": None},
            }},
            ["revise", "approve"], send, restart=restart,
        )
        self.assertIs(result, packet)
        self.assertEqual(paths, ["session_store", "previous_response"])
        self.assertEqual(restart.call_count, 2)
        self.assertEqual(
            [(json.loads(call.args[0]), call.args[1]) for call in send.call_args_list],
            [
                ({"session_id": "persisted-session", "advisor": "revise"}, None),
                ({"session_id": "persisted-session", "advisor": "approve"}, "new-response"),
            ],
        )

    def test_internal_cli_cells_are_omitted_without_skip_instructions(self):
        text = (
            "# %% [markdown]\n# This cell defines the example.\n"
            "# %% Step 1.1 - Example\nvalue = 1\n"
            "# %% [script-only]\ndef main():\n    return value\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        cells = split_cells(text)
        self.assertEqual(len(cells), 2)
        self.assertNotIn("main()", "\n".join(line for _, lines in cells for line in lines))
        self.assertIn("def main():", "\n".join(split_cells(text, notebook_safe=False)[-1][1]))

    def test_description_validation_rejects_missing_or_empty_markdown(self):
        self.assertTrue(validate_cell_descriptions(build_notebook("# %% Step 1.1 - Example\npass\n")))
        self.assertEqual(validate_cell_descriptions(build_notebook(
            "# %% [markdown]\n# This cell demonstrates validation.\n# %% Step 1.1 - Example\npass\n"
        )), [])

    def test_all_walkthroughs_are_fresh_described_output_free_and_notebook_only(self):
        for relative, notebook_name, prefix in DRIVERS:
            with self.subTest(driver=relative):
                path = ROOT / "labs" / relative
                notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
                self.assertEqual(notebook, json.loads(path.with_name(notebook_name).read_text(encoding="utf-8")))
                self.assertEqual(validate_notebook(notebook), [])
                self.assertEqual(validate_step_ids(notebook, prefix), [])
                self.assertEqual(validate_cell_descriptions(notebook), [])
                for cell in notebook["cells"]:
                    source = "".join(cell["source"])
                    self.assertNotEqual(cell["cell_type"], "raw")
                    if cell["cell_type"] == "code":
                        ast.parse(source)
                        self.assertEqual(cell["outputs"], [])
                        self.assertIsNone(cell["execution_count"])
                        self.assertNotIn("argparse.ArgumentParser", source)
                        self.assertNotIn("RUN_LAB", source)
                    else:
                        for forbidden in ("script mode", "script-only", "JupyterLab", "Bash terminal", "# %%", "```bash"):
                            self.assertNotIn(forbidden, source)

    def test_notebook_paths_work_from_repository_and_lab_directories(self):
        original = Path.cwd()
        try:
            for relative, _, _ in INTERNAL_DRIVERS[1:]:
                path = ROOT / "shared" / relative
                tree = ast.parse(path.read_text(encoding="utf-8"))
                assignment = next(
                    node for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "SOURCE_PATH" for target in node.targets)
                )
                for directory in (ROOT.parent, ROOT, path.parent):
                    with self.subTest(driver=relative, cwd=directory):
                        os.chdir(directory)
                        namespace = {"Path": Path}
                        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(path), "exec"), namespace)
                        self.assertEqual(namespace["SOURCE_PATH"], path)
        finally:
            os.chdir(original)

    def test_split_kernel_paths_work_without_file_or_a_kernel_globals(self):
        original = Path.cwd()
        try:
            for relative, _, _ in DRIVERS:
                path = ROOT / "labs" / relative
                notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
                startup = next(cell for cell in notebook["cells"] if cell["cell_type"] == "code")
                tree = ast.parse("".join(startup["source"]))
                locations = ast.Module(body=[
                    node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id in {
                        "HERE", "REPO_ROOT", "WORKSHOP", "SOURCE_PATH", "ROOT",
                    } for target in node.targets)
                ], type_ignores=[])
                for directory in (ROOT.parent, ROOT, path.parent):
                    with self.subTest(source=relative, cwd=directory):
                        os.chdir(directory)
                        namespace = {"Path": Path}
                        exec(compile(locations, str(path), "exec"), namespace)
                        self.assertEqual(namespace.get("WORKSHOP", namespace.get("ROOT")), ROOT)
                        if "SOURCE_PATH" in namespace:
                            self.assertEqual(namespace["SOURCE_PATH"], path)
        finally:
            os.chdir(original)

    def test_lab3_exercises_execute_without_environment_toggles(self):
        path = ROOT / "shared" / INTERNAL_DRIVERS[2][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        for step, function in (("3.8", "broken_store_acceptance_gate"), ("3.9", "knowledge_acceptance_gate")):
            with self.subTest(step=step):
                cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith(f"# Step {step} -"))
                gate = Mock()
                exec(compile(notebook_action("".join(cell["source"])), str(path), "exec"), {function: gate})
                gate.assert_called_once_with()

    def test_lab2_requires_verified_setup_only_in_notebooks(self):
        path = ROOT / "shared" / INTERNAL_DRIVERS[1][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith("# Step 2.2 -"))
        action = compile(notebook_action("".join(cell["source"])), str(path), "exec")
        environment = {
            "PROJECT_RESOURCE_ID": "/project", "FOUNDRY_PROJECT_ENDPOINT": "https://project.example.test",
            "MARKETPLACE_RESOURCE_SUFFIX": "jd-4821", "AZURE_AI_MODEL_DEPLOYMENT_NAME": "chat-jd-4821",
        }
        verified = {
            "provisioning_state": "Succeeded", "smoke_tests": {"chat": "passed", "embedding": "passed"},
            "project_resource_id": environment["PROJECT_RESOURCE_ID"],
            "project_endpoint": environment["FOUNDRY_PROJECT_ENDPOINT"],
            "resource_suffix": environment["MARKETPLACE_RESOURCE_SUFFIX"],
            "chat_deployment": {"name": environment["AZURE_AI_MODEL_DEPLOYMENT_NAME"]},
        }
        for record, valid in ((verified, True), ({}, False),
                              ({**verified, "smoke_tests": {"chat": "passed", "embedding": "failed"}}, False)):
            with self.subTest(record=record):
                require = Mock(return_value=record)
                namespace = {"LAB": "lab2", "ENV": environment, "lab_helpers": SimpleNamespace(require_artifact=require)}
                if valid:
                    exec(action, namespace)
                else:
                    with self.assertRaises(RuntimeError):
                        exec(action, namespace)
                require.assert_called_once_with("lab1", "project.json", through=1, caller="lab2")
        for key in environment:
            with self.subTest(mismatched_config=key):
                namespace = {
                    "LAB": "lab2", "ENV": {**environment, key: "other"},
                    "lab_helpers": SimpleNamespace(require_artifact=Mock(return_value=verified)),
                }
                with self.assertRaisesRegex(RuntimeError, key):
                    exec(action, namespace)
        require = Mock(side_effect=AssertionError("Internal builds must not provision or require setup."))
        exec(action, {"__file__": str(path), "lab_helpers": SimpleNamespace(require_artifact=require)})
        require.assert_not_called()

    def test_scale_out_requires_shared_history_and_does_not_claim_false_success(self):
        path = ROOT / "shared" / INTERNAL_DRIVERS[2][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith("# Step 3.7 -"))
        code = compile(notebook_action("".join(cell["source"])), str(path), "exec")
        for environment in ({}, {"MARKETPLACE_AZURITE_CONNECTION_STRING": "configured"}):
            with self.subTest(shared=bool(environment)):
                gate = Mock()
                output = io.StringIO()
                with redirect_stdout(output):
                    exec(code, {"ENV": environment, "os": SimpleNamespace(environ={}), "scale_out_acceptance_gate": gate})
                if environment:
                    gate.assert_called_once_with()
                else:
                    gate.assert_not_called()
                    self.assertIn("SKIPPED", output.getvalue())
                    self.assertIn("NOT proven", output.getvalue())

    def test_cloud_deployment_is_an_explicit_checked_notebook_action(self):
        for relative, _, _ in INTERNAL_DRIVERS:
            path = ROOT / "shared" / relative
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.If) or ast.unparse(node.test) != "'__file__' not in globals()":
                    continue
                calls = [
                    call for call in ast.walk(node)
                    if isinstance(call, ast.Call) and ast.unparse(call.func) == "subprocess.run"
                ]
                for call in calls:
                    with self.subTest(driver=relative, call=ast.unparse(call)):
                        if isinstance(call.args[0], ast.List) and isinstance(call.args[0].elts[0], ast.Constant) \
                                and call.args[0].elts[0].value in {"bash", "azd"}:
                            self.assertTrue(any(keyword.arg == "check" and isinstance(keyword.value, ast.Constant)
                                                and keyword.value.value is True for keyword in call.keywords))
                # Importing an internal authoring driver must not run notebook actions.
                runner = Mock(side_effect=AssertionError("deployment during import"))
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"),
                     {"__file__": str(path), "subprocess": SimpleNamespace(run=runner)})
                runner.assert_not_called()

    def test_two_package_deployment_stops_when_the_first_command_fails(self):
        path = ROOT / "shared" / INTERNAL_DRIVERS[6][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith("# Step S7.9 -"))
        runner = Mock(side_effect=RuntimeError("first deployment failed"))
        namespace = {
            "subprocess": SimpleNamespace(run=runner),
            "deploy_commands": Mock(return_value="first deployment\nsecond deployment"),
            "LAB_DIR": path.parent,
        }
        with self.assertRaisesRegex(RuntimeError, "first deployment failed"):
            exec(compile(notebook_action("".join(cell["source"])), str(path), "exec"), namespace)
        runner.assert_called_once_with(
            ["bash", "-lc", "set -euo pipefail\nfirst deployment\nsecond deployment"],
            cwd=path.parent,
            check=True,
        )

    def test_stretch7_inputs_override_unrelated_skill_defaults_and_validate_toolbox(self):
        path = ROOT / "shared" / INTERNAL_DRIVERS[6][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        source = next(
            "".join(cell["source"]) for cell in notebook["cells"]
            if "".join(cell["source"]).startswith("# Step S7.1 -")
        )
        action = notebook_action(source)
        for name, url, valid in (
            ("", "", True),
            ("approved-toolbox", "https://toolbox.example.test/mcp", True),
            ("", "https://toolbox.example.test/mcp", False),
            ("approved-toolbox", "", False),
            ("approved-toolbox", "http://toolbox.example.test/mcp", False),
            ("approved-toolbox", "https://attendee@toolbox.example.test/mcp", False),
            ("approved-toolbox", "https://toolbox.example.test/mcp?sig=credential", False),
        ):
            with self.subTest(name=name, url=url):
                configured = ast.parse(ast.unparse(action).replace(
                    "TOOLBOX_NAME = ''", f"TOOLBOX_NAME = {name!r}"
                ).replace("TOOLBOX_MCP_URL = ''", f"TOOLBOX_MCP_URL = {url!r}"))
                environment = {"SKILL_NAMES": "unrelated-root-sample", "TOOLBOX_NAME": "old-toolbox"}
                namespace = {
                    "ENV": {}, "os": SimpleNamespace(environ=environment),
                    "urlsplit": urlsplit, "SKILLS_SRC": path.parent / "skills",
                }
                if valid:
                    exec(compile(configured, str(path), "exec"), namespace)
                    self.assertEqual(environment["SKILL_NAMES"], "")
                    self.assertEqual(namespace["ENV"], {
                        "TOOLBOX_NAME": name, "TOOLBOX_MCP_URL": url, "SKILL_NAMES": "",
                    })
                else:
                    with self.assertRaises(ValueError):
                        exec(compile(configured, str(path), "exec"), namespace)
                    self.assertEqual(environment["SKILL_NAMES"], "unrelated-root-sample")
        for names, valid in (("hra-reimbursement-rules", True), ("unrelated-root-sample", False), ("../outside", False)):
            with self.subTest(skills=names):
                configured = ast.parse(ast.unparse(action).replace("SKILL_NAMES = ''", f"SKILL_NAMES = {names!r}"))
                namespace = {
                    "ENV": {}, "os": SimpleNamespace(environ={}),
                    "urlsplit": urlsplit, "SKILLS_SRC": path.parent / "skills",
                }
                if valid:
                    exec(compile(configured, str(path), "exec"), namespace)
                    self.assertEqual(namespace["ENV"]["SKILL_NAMES"], names)
                else:
                    with self.assertRaisesRegex(ValueError, "local workshop skills"):
                        exec(compile(configured, str(path), "exec"), namespace)


if __name__ == "__main__":
    unittest.main()
