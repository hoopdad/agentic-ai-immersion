"""Check learner tooling without deploying or invoking an Azure service."""
from __future__ import annotations

import importlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "labs"))
from common import foundry_env, resource_names  # noqa: E402
from deployment import check_toolchain  # noqa: E402


def main() -> None:
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError("Use the repository's Python 3.14 dev-container interpreter.")
    check_toolchain()
    for command in ("bash", "pwsh", "git"):
        if shutil.which(command) is None:
            raise RuntimeError(f"Missing command: {command}. Rebuild the dev container.")
    for name in ("agent_framework", "agent_framework_foundry_hosting", "azure.ai.projects",
                 "azure.ai.evaluation", "azure.search.documents", "redis", "mcp", "yaml", "jupyter"):
        importlib.import_module(name)
    env = foundry_env.load_env()
    resource_names.suffix(env, required=True)
    redis_url = env["MARKETPLACE_REDIS_URL"]
    if foundry_env.is_local_redis_url(redis_url):
        import redis
        if not redis.Redis.from_url(redis_url).ping():
            raise RuntimeError("The dev-container Redis companion did not respond to PING.")
    extensions = subprocess.check_output(["azd", "extension", "list"], text=True)
    if "azure.ai.agents" not in extensions:
        raise RuntimeError("Run: azd extension install azure.ai.agents")
    print("Tooling checks passed. Azure login, RBAC and service connectivity still require separate checks.")


if __name__ == "__main__":
    main()
