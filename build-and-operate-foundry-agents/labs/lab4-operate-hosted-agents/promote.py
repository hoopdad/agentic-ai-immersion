"""Gate a promotion; print a Bash command by default, execute only with --execute."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
LABS_DIR = HERE.parent
ROOT = LABS_DIR.parent
GATE_PATH = LABS_DIR / "artifacts" / "lab4" / "gate_result.json"
PROMOTIONS_PATH = LABS_DIR / "artifacts" / "lab4" / "promotions.jsonl"
HOSTED_DIR = LABS_DIR / "lab2-hosted-knowledge-sessions" / "hosted"
ENVS_DIR = HERE / "envs"
ORDER = ["dev", "test", "prod"]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LABS_DIR))
from common.foundry_env import _parse_env_file  # noqa: E402
from deployment import validate_cloud_settings  # noqa: E402


def check_gate() -> dict:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    required = {"passed", "evaluated_at", "questions", "failures"}
    if not isinstance(gate, dict) or not required.issubset(gate) or gate["passed"] is not True:
        raise ValueError("A passing, complete gate_result.json is required. Run eval_gate.py --run first.")
    return gate


def bash_block(target: str, tag: str) -> str:
    command = ["python", str(Path(__file__).resolve()), "--to", target, "--tag", tag, "--execute"]
    return "\n".join(["(", "set -euo pipefail", shlex.join(command), ")"])


def execute(target: str, tag: str) -> None:
    env_file = ENVS_DIR / f".env.{target}"
    settings = _parse_env_file(env_file)
    if not settings or any(not value or re.search(r"<[^>]+>", value) for value in settings.values()):
        raise ValueError(f"Replace empty values and placeholders in {env_file} before promotion.")
    for key in ("FOUNDRY_PROJECT_ENDPOINT", "PROJECT_RESOURCE_ID", "AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        if not settings.get(key):
            raise ValueError(f"Missing {key} in {env_file}")
    validate_cloud_settings(settings)
    env = {**os.environ, **settings}

    def run(*command: str) -> None:
        subprocess.run(command, cwd=HOSTED_DIR, env=env, check=True)

    run("git", "check-ref-format", f"refs/tags/{tag}")
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=ROOT, check=False,
    )
    if result.returncode != 1:
        raise RuntimeError(f"Tag already exists or tag lookup failed: {tag} (exit {result.returncode}).")
    run(sys.executable, "prepare.py")
    run("azd", "env", "select", f"healthcare-marketplace-concierge-{target}")
    # Refuse to deploy an already-selected azd environment against a different project.
    azd_values = json.loads(subprocess.check_output(
        ["azd", "env", "get-values", "--output", "json"], cwd=HOSTED_DIR, env=env, text=True,
    ))
    if azd_values.get("AZURE_AI_PROJECT_ID") != settings["PROJECT_RESOURCE_ID"]:
        raise ValueError("Selected azd environment does not match PROJECT_RESOURCE_ID; initialize it first.")
    for key, value in settings.items():
        run("azd", "env", "set", key, value)
    run("azd", "up", "--no-prompt")
    run(sys.executable, "test_local.py", "--deployed")
    run("git", "tag", tag)


def record(gate: dict, target: str, tag: str, outcome: str) -> None:
    PROMOTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROMOTIONS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "from": ORDER[max(ORDER.index(target) - 1, 0)], "to": target, "tag": tag,
            "gate_evaluated_at": gate["evaluated_at"], "outcome": outcome,
        }) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", choices=ORDER, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    tag = args.tag or f"healthcare-marketplace-concierge-{args.to}-{datetime.now(timezone.utc):%Y.%m.%d-%H%M}"
    try:
        gate = check_gate()
    except (OSError, ValueError) as exc:
        print(f"Promotion stopped: {exc}", file=sys.stderr)
        return 1
    if not args.execute:
        print(bash_block(args.to, tag))
        record(gate, args.to, tag, "dry-run")
        return 0
    try:
        execute(args.to, tag)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        record(gate, args.to, tag, f"failed: {exc}")
        print(f"Promotion stopped: {exc}", file=sys.stderr)
        return 1
    record(gate, args.to, tag, "promoted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
