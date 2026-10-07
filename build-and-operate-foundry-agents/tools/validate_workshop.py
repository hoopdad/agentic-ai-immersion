"""Offline migration and workshop checks; never authenticate or deploy."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from py_to_ipynb import build_notebook, validate_cell_descriptions, validate_step_ids

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
WALKTHROUGHS = {
    "lab1-foundry-project-models": ("lab1_project_models.py", "lab1_walkthrough.ipynb", "1", "lab1"),
    "lab2-hosted-agent-basics": ("lab2_hosted_basics.py", "lab2_walkthrough.ipynb", "2", "lab2"),
    "lab3-hosted-knowledge-sessions": ("lab3_hosted_knowledge.py", "lab3_walkthrough.ipynb", "3", "lab3"),
    "lab4-hosted-multi-agent-handoff": ("lab4_hosted_multi_agent.py", "lab4_walkthrough.ipynb", "4", "lab4"),
    "lab5-operate-hosted-agents": ("lab5_operate.py", "lab5_walkthrough.ipynb", "5", "lab5"),
    "stretch6-prompt-agents-and-workflows": ("stretch6_prompt_agents.py", "stretch6_walkthrough.ipynb", "S6", "stretch6"),
    "stretch7-invocations-toolbox-skills": ("stretch7_invocations.py", "stretch7_walkthrough.ipynb", "S7", "stretch7"),
}
PREREQUISITES = {
    "lab2": {("lab1", "project.json", 1)},
    "lab3": {("lab2", "hosted.json", 2)},
    "lab4": {("lab3", "hosted.json", 3)},
    "lab5": {("lab3", "hosted.json", 3), ("lab3", "knowledge.json", 3)},
    "stretch6": {("lab3", "knowledge.json", 3), ("lab3", "hosted.json", 3)},
}


def validate_artifact_chain(tree: ast.Module, lab: str) -> None:
    references = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) \
                or node.func.attr != "require_artifact":
            continue
        values = [
            lab if isinstance(arg, ast.Name) and arg.id == "LAB" else ast.literal_eval(arg)
            for arg in node.args[:3]
        ]
        if len(values) < 3:
            through = next((keyword.value for keyword in node.keywords if keyword.arg == "through"), None)
            if through is None:
                raise ValueError(f"{lab}: artifact prerequisite must specify through")
            values.append(ast.literal_eval(through))
        target, name, through = values
        if through != int(target.removeprefix("lab").removeprefix("stretch")):
            raise ValueError(f"{lab}: {target}/{name} must use its own predecessor number, not through={through}")
        references.add((target, name, through))
    missing = PREREQUISITES.get(lab, set()) - references
    if missing:
        raise ValueError(f"{lab}: missing artifact prerequisite checks: {missing}")


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True,
                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def main() -> None:
    for path in (REPO / ".devcontainer").glob("*.sh"):
        if b"\r" in path.read_bytes():
            raise ValueError(f"Bash script must use LF line endings, including in the working tree: {path}")
    excluded = {".venv", "__pycache__", "artifacts", ".azure"}
    for path in ROOT.rglob("*.py"):
        if not excluded.intersection(path.relative_to(ROOT).parts):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    expected_notebooks = {
        ROOT / "labs" / directory / notebook
        for directory, (_, notebook, _, _) in WALKTHROUGHS.items()
    }
    actual_notebooks = set((ROOT / "labs").glob("*/*.ipynb"))
    if actual_notebooks != expected_notebooks:
        raise ValueError(f"Workshop must contain exactly seven expected walkthroughs: "
                         f"missing={expected_notebooks - actual_notebooks}, unexpected={actual_notebooks - expected_notebooks}")
    for directory, (script_name, notebook_name, prefix, lab) in WALKTHROUGHS.items():
        source = ROOT / "labs" / directory / script_name
        path = source.with_name(notebook_name)
        run("tools/py_to_ipynb.py", "--check", str(path))
        notebook = json.loads(path.read_text(encoding="utf-8"))
        script = source.read_text(encoding="utf-8")
        if notebook != build_notebook(script, seed=source.stem):
            raise ValueError(f"Regenerate {path} from {source}")
        title = "".join(notebook["cells"][0]["source"]).splitlines()[0]
        expected_title = f"# Stretch {prefix[1:]}:" if prefix.startswith("S") else f"# Lab {prefix}:"
        if not title.startswith(expected_title):
            raise ValueError(f"{path}: expected notebook title {expected_title!r}, got {title!r}")
        tree = ast.parse(script, filename=str(source))
        lab_values = [
            node.value.value for node in tree.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
            and any(isinstance(target, ast.Name) and target.id == "LAB" for target in node.targets)
        ]
        if lab == "lab1":
            if "labs/artifacts/lab1/project.json" not in script:
                raise ValueError(f"{source}: missing Lab 1 project checkpoint path")
        elif lab_values != [lab]:
            raise ValueError(f"{source}: expected artifact namespace LAB = {lab!r}")
        validate_artifact_chain(tree, lab)
        step_problems = validate_step_ids(notebook, prefix) + validate_cell_descriptions(notebook)
        if step_problems:
            raise ValueError(f"{path}: {'; '.join(step_problems)}")
        for cell in notebook["cells"]:
            text = "".join(cell["source"])
            if cell["cell_type"] == "raw":
                raise ValueError(f"Raw shell cells are not learner notebook actions: {path}")
            if cell["cell_type"] == "code":
                if cell.get("outputs") or cell.get("execution_count") is not None:
                    raise ValueError(f"Executed notebook output must not be committed: {path}")
                if any(token in text for token in ("argparse.ArgumentParser", "RUN_LAB", 'if __name__ == "__main__"')):
                    raise ValueError(f"CLI-only code or environment gates in learner notebook: {path}")
                ast.parse(text, filename=str(path))
    pins = {line.lower() for line in (REPO / "requirements.txt").read_text().splitlines()
            if "==" in line}
    for path in (ROOT / "labs").glob("**/requirements.txt"):
        if path.parent == ROOT / "labs":
            continue
        for line in path.read_text().splitlines():
            if line and not line.startswith("#") and line.lower() not in pins:
                raise ValueError(f"Hosted requirement does not match root lock: {path}: {line}")
    for name in ("marketplace_data", "session_store", "message_store"):
        run(f"common/{name}.py")
    run("-m", "unittest", "discover", "-s", "tests", "-v")
    run("-m", "unittest", "discover", "-s", "labs/stretch6-prompt-agents-and-workflows",
        "-p", "test_stretch6_offline.py", "-v")
    with tempfile.TemporaryDirectory(prefix="foundry-workshop-check-") as directory:
        sandbox_repo = Path(directory) / "repository"
        sandbox_repo.mkdir()
        shutil.copy2(REPO / "requirements.txt", sandbox_repo / "requirements.txt")
        marker = sandbox_repo / ".devcontainer"
        marker.mkdir()
        shutil.copy2(REPO / ".devcontainer/devcontainer.json", marker / "devcontainer.json")
        sandbox = sandbox_repo / ROOT.name
        shutil.copytree(ROOT, sandbox, ignore=shutil.ignore_patterns(
            ".env", ".env.*", ".venv", "__pycache__", "artifacts", ".azure",
        ))
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([
            sys.executable, "-m", "unittest", "discover", "-s", "tests",
            "-p", "test_py_to_ipynb.py", "-v",
        ], cwd=sandbox, env=environment, check=True)
        for prepare in sorted((sandbox / "labs").glob("*/hosted*/prepare.py")):
            subprocess.run([sys.executable, str(prepare)], cwd=prepare.parent,
                           env=environment, check=True)
        subprocess.run([
            sys.executable,
            str(sandbox / "labs/stretch7-invocations-toolbox-skills/hosted-invocations/test_local.py"),
            "--offline",
        ], cwd=sandbox, env=environment, check=True)
    print("Offline workshop checks passed. Azure and container-build checks are separate.")


if __name__ == "__main__":
    main()
