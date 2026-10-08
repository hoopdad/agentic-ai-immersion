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
INTERNAL_DRIVERS = {
    "lab1-foundry-project-models": ("lab1_project_models.py", "lab1_walkthrough.ipynb", "1", "lab1"),
    "lab2-hosted-agent-basics": ("lab2_hosted_basics.py", "lab2_walkthrough.ipynb", "2", "lab2"),
    "lab3-hosted-knowledge-sessions": ("lab3_hosted_knowledge.py", "lab3_walkthrough.ipynb", "3", "lab3"),
    "lab4-hosted-multi-agent-handoff": ("lab4_hosted_multi_agent.py", "lab4_walkthrough.ipynb", "4", "lab4"),
    "lab5-operate-hosted-agents": ("lab5_operate.py", "lab5_walkthrough.ipynb", "5", "lab5"),
    "stretch6-prompt-agents-and-workflows": ("stretch6_prompt_agents.py", "stretch6_walkthrough.ipynb", "S6", "stretch6"),
    "stretch7-invocations-toolbox-skills": ("stretch7_invocations.py", "stretch7_walkthrough.ipynb", "S7", "stretch7"),
}
WALKTHROUGHS = {
    "lab1-foundry-project-models": (
        ("lab1a_identity_project.py", "lab1a_walkthrough.ipynb", "1", "lab1", "a"),
        ("lab1b_models_verify.py", "lab1b_walkthrough.ipynb", "1", "lab1", "b"),
    ),
    "lab2-hosted-agent-basics": (
        ("lab2a_tools_local.py", "lab2a_walkthrough.ipynb", "2", "lab2", "a"),
        ("lab2b_deploy_invoke.py", "lab2b_walkthrough.ipynb", "2", "lab2", "b"),
    ),
    "lab3-hosted-knowledge-sessions": (
        ("lab3a_knowledge_retrieval.py", "lab3a_walkthrough.ipynb", "3", "lab3", "a"),
        ("lab3b_sessions_resiliency.py", "lab3b_walkthrough.ipynb", "3", "lab3", "b"),
    ),
    "lab4-hosted-multi-agent-handoff": (
        ("lab4a_specialist_orchestration.py", "lab4a_walkthrough.ipynb", "4", "lab4", "a"),
        ("lab4b_advisor_recovery.py", "lab4b_walkthrough.ipynb", "4", "lab4", "b"),
    ),
    "lab5-operate-hosted-agents": (
        ("lab5a_tracing_evaluation.py", "lab5a_walkthrough.ipynb", "5", "lab5", "a"),
        ("lab5b_release_rollback.py", "lab5b_walkthrough.ipynb", "5", "lab5", "b"),
    ),
    "stretch6-prompt-agents-and-workflows": (
        ("stretch6a_prompt_agents.py", "stretch6a_walkthrough.ipynb", "S6", "stretch6", "a"),
        ("stretch6b_workflows_delegation.py", "stretch6b_walkthrough.ipynb", "S6", "stretch6", "b"),
    ),
    "stretch7-invocations-toolbox-skills": (
        ("stretch7a_invocations.py", "stretch7a_walkthrough.ipynb", "S7", "stretch7", "a"),
        ("stretch7b_skills_toolbox.py", "stretch7b_walkthrough.ipynb", "S7", "stretch7", "b"),
    ),
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


def validate_checkpoint_contract(tree: ast.Module, lab: str, part: str) -> None:
    """Check scope-bound helper handoffs, separately from the original artifact chain."""
    assignments = {
        target.id: node.value
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }

    def resolve(value: ast.AST) -> ast.AST:
        seen = set()
        while isinstance(value, ast.Name) and value.id in assignments and value.id not in seen:
            seen.add(value.id)
            value = assignments[value.id]
        return value

    calls = {"write_checkpoint": [], "read_checkpoint": []}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else ""
        )
        if name in calls:
            calls[name].append(node)
    required = {"write_checkpoint": part}
    if part == "b":
        required["read_checkpoint"] = "a"
    for name, expected_part in required.items():
        if len(calls[name]) != 1:
            raise ValueError(f"{lab}{part.upper()}: expected one {name} handoff")
        call = calls[name][0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        for key, expected in (("lab", lab), ("part", expected_part)):
            value = resolve(keywords.get(key, ast.Constant(None)))
            if not isinstance(value, ast.Constant) or value.value != expected:
                raise ValueError(f"{lab}{part.upper()}: {name} must use {key}={expected!r}")
        if "context" not in keywords or isinstance(resolve(keywords["context"]), ast.Constant):
            raise ValueError(f"{lab}{part.upper()}: {name} needs explicit current scope context")
        if not call.args:
            raise ValueError(f"{lab}{part.upper()}: {name} needs the checkpoint artifact path")
        path = resolve(call.args[0])
        if f"part_{expected_part}.json" not in ast.unparse(path):
            raise ValueError(f"{lab}{part.upper()}: {name} must address part_{expected_part}.json")
        if name == "write_checkpoint":
            metadata = [resolve(keywords[key]) for key in ("state", "evidence") if key in keywords]
            if not any(
                isinstance(node, (ast.Name, ast.Call))
                for value in metadata for node in ast.walk(value)
            ):
                raise ValueError(f"{lab}{part.upper()}: checkpoint needs actual state or evidence")
    if part == "b" and calls["read_checkpoint"][0].lineno >= calls["write_checkpoint"][0].lineno:
        raise ValueError(f"{lab}B: restore A before publishing B")


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
        for directory, parts in WALKTHROUGHS.items()
        for _, notebook, _, _, _ in parts
    }
    actual_notebooks = set((ROOT / "labs").glob("*/*.ipynb"))
    if actual_notebooks != expected_notebooks:
        raise ValueError(f"Workshop must contain exactly fourteen expected walkthroughs: "
                         f"missing={expected_notebooks - actual_notebooks}, unexpected={actual_notebooks - expected_notebooks}")
    # The original callable drivers retain the cumulative artifact prerequisites.
    for directory, (script_name, _, _, lab) in INTERNAL_DRIVERS.items():
        source = ROOT / "labs" / directory / script_name
        validate_artifact_chain(ast.parse(source.read_text(encoding="utf-8")), lab)
    for directory, (script_name, notebook_name, prefix, lab, part) in (
        (directory, item) for directory, parts in WALKTHROUGHS.items() for item in parts
    ):
        source = ROOT / "labs" / directory / script_name
        path = source.with_name(notebook_name)
        run("tools/py_to_ipynb.py", "--check", str(path))
        notebook = json.loads(path.read_text(encoding="utf-8"))
        script = source.read_text(encoding="utf-8")
        if notebook != build_notebook(script, seed=source.stem):
            raise ValueError(f"Regenerate {path} from {source}")
        title = "".join(notebook["cells"][0]["source"]).splitlines()[0]
        label = f"Stretch {prefix[1:]}" if prefix.startswith("S") else f"Lab {prefix}"
        expected_title = f"# {label}{part.upper()}:"
        if not title.startswith(expected_title):
            raise ValueError(f"{path}: expected notebook title {expected_title!r}, got {title!r}")
        tree = ast.parse(script, filename=str(source))
        validate_checkpoint_contract(tree, lab, part)
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
    with tempfile.TemporaryDirectory(prefix="foundry-workshop-check-", dir=REPO) as directory:
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
        prepares = sorted((sandbox / "labs").glob("*/hosted*/prepare.py"))
        if len(prepares) != 5:
            raise ValueError(f"Expected five hosted package snapshots, got {len(prepares)}")
        for prepare in prepares:
            subprocess.run([sys.executable, str(prepare)], cwd=prepare.parent,
                           env=environment, check=True)
        subprocess.run([
            sys.executable,
            str(sandbox / "labs/stretch7-invocations-toolbox-skills/hosted-invocations/test_local.py"),
            "--offline",
        ], cwd=sandbox, env=environment, check=True)
    print("Offline workshop checks passed: fourteen A/B notebooks and five hosted package snapshots. "
          "Azure and container-build checks are separate.")


if __name__ == "__main__":
    main()
