"""Offline regression checks for the notebook-only learner interface."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from py_to_ipynb import (  # noqa: E402
    build_notebook,
    split_cells,
    validate_cell_descriptions,
    validate_notebook,
    validate_step_ids,
)

DRIVERS = (
    ("lab1-foundry-project-models/lab1_project_models.py", "lab1_walkthrough.ipynb", "1"),
    ("lab2-hosted-agent-basics/lab2_hosted_basics.py", "lab2_walkthrough.ipynb", "2"),
    ("lab3-hosted-knowledge-sessions/lab3_hosted_knowledge.py", "lab3_walkthrough.ipynb", "3"),
    ("lab4-hosted-multi-agent-handoff/lab4_hosted_multi_agent.py", "lab4_walkthrough.ipynb", "4"),
    ("lab5-operate-hosted-agents/lab5_operate.py", "lab5_walkthrough.ipynb", "5"),
    ("stretch6-prompt-agents-and-workflows/stretch6_prompt_agents.py", "stretch6_walkthrough.ipynb", "S6"),
    ("stretch7-invocations-toolbox-skills/stretch7_invocations.py", "stretch7_walkthrough.ipynb", "S7"),
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
            for relative, _, _ in DRIVERS[1:]:
                path = ROOT / "labs" / relative
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

    def test_lab3_exercises_execute_without_environment_toggles(self):
        path = ROOT / "labs" / DRIVERS[2][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        for step, function in (("3.8", "broken_store_acceptance_gate"), ("3.9", "knowledge_acceptance_gate")):
            with self.subTest(step=step):
                cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith(f"# Step {step} -"))
                gate = Mock()
                exec(compile(notebook_action("".join(cell["source"])), str(path), "exec"), {function: gate})
                gate.assert_called_once_with()

    def test_lab2_requires_verified_setup_only_in_notebooks(self):
        path = ROOT / "labs" / DRIVERS[1][0]
        notebook = build_notebook(path.read_text(encoding="utf-8"), seed=path.stem)
        cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith("# Step 2.2 -"))
        action = compile(notebook_action("".join(cell["source"])), str(path), "exec")
        verified = {"provisioning_state": "Succeeded", "smoke_tests": {"chat": "passed", "embedding": "passed"}}
        for record, valid in ((verified, True), ({}, False),
                              ({**verified, "smoke_tests": {"chat": "passed", "embedding": "failed"}}, False)):
            with self.subTest(record=record):
                require = Mock(return_value=record)
                namespace = {"LAB": "lab2", "lab_helpers": SimpleNamespace(require_artifact=require)}
                if valid:
                    exec(action, namespace)
                else:
                    with self.assertRaises(RuntimeError):
                        exec(action, namespace)
                require.assert_called_once_with("lab1", "project.json", through=1, caller="lab2")
        require = Mock(side_effect=AssertionError("Internal builds must not provision or require setup."))
        exec(action, {"__file__": str(path), "lab_helpers": SimpleNamespace(require_artifact=require)})
        require.assert_not_called()

    def test_scale_out_requires_shared_history_and_does_not_claim_false_success(self):
        path = ROOT / "labs" / DRIVERS[2][0]
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
        for relative, _, _ in DRIVERS:
            path = ROOT / "labs" / relative
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
        path = ROOT / "labs" / DRIVERS[6][0]
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


if __name__ == "__main__":
    unittest.main()
