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

from py_to_ipynb import validate_step_ids

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
STEP_PREFIXES = {
    "lab1_walkthrough.ipynb": "1",
    "lab2_walkthrough.ipynb": "2",
    "lab3_walkthrough.ipynb": "3",
    "lab4_walkthrough.ipynb": "4",
    "stretch5_walkthrough.ipynb": "S5",
    "stretch6_walkthrough.ipynb": "S6",
}


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
    for path in (ROOT / "labs").glob("*/*_walkthrough.ipynb"):
        run("tools/py_to_ipynb.py", "--check", str(path))
        notebook = json.loads(path.read_text(encoding="utf-8"))
        step_problems = validate_step_ids(notebook, STEP_PREFIXES[path.name])
        if step_problems:
            raise ValueError(f"{path}: {'; '.join(step_problems)}")
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                if cell.get("outputs") or cell.get("execution_count") is not None:
                    raise ValueError(f"Executed notebook output must not be committed: {path}")
                ast.parse("".join(cell["source"]), filename=str(path))
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
    run("-m", "unittest", "discover", "-s", "labs/stretch5-prompt-agents-and-workflows",
        "-p", "test_stretch5_offline.py", "-v")
    with tempfile.TemporaryDirectory(prefix="foundry-workshop-check-") as directory:
        sandbox = Path(directory) / ROOT.name
        shutil.copytree(ROOT, sandbox, ignore=shutil.ignore_patterns(
            ".env", ".env.*", ".venv", "__pycache__", "artifacts", ".azure",
        ))
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        for prepare in sorted((sandbox / "labs").glob("*/hosted*/prepare.py")):
            subprocess.run([sys.executable, str(prepare)], cwd=prepare.parent,
                           env=environment, check=True)
        subprocess.run([
            sys.executable,
            str(sandbox / "labs/stretch6-invocations-toolbox-skills/hosted-invocations/test_local.py"),
            "--offline",
        ], cwd=sandbox, env=environment, check=True)
    print("Offline workshop checks passed. Azure and container-build checks are separate.")


if __name__ == "__main__":
    main()
