"""Shared, print-only Bash commands and explicit Python deployment runner."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from common import resource_names  # noqa: E402

MINIMUM_AZD = (1, 34, 2)
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def checked_value(name: str, value: str) -> str:
    if not value or re.search(r"<[^>]+>", value):
        raise ValueError(f"{name} must be configured, without placeholders.")
    return value


def bash_deploy_block(
    folder: Path,
    name: str,
    protocol: str,
    env: dict[str, str],
    settings: dict[str, str] | None = None,
    *,
    check_package: bool = False,
) -> str:
    suffix = resource_names.suffix(env, required=True)
    if not name.endswith(f"-{suffix}"):
        raise ValueError(f"Agent name {name!r} must end with the configured suffix {suffix!r}.")
    command = [
        "python", str(Path(__file__).resolve()), "--folder", str(folder.resolve()),
        "--agent-name", name, "--protocol", protocol,
        "--resource-suffix", suffix,
        "--project-id", checked_value("PROJECT_RESOURCE_ID", env.get("PROJECT_RESOURCE_ID", "")),
        "--project-endpoint", checked_value("FOUNDRY_PROJECT_ENDPOINT", env.get("FOUNDRY_PROJECT_ENDPOINT", "")),
        "--model", checked_value("model", env.get("AZURE_AI_MODEL_DEPLOYMENT_NAME") or env.get("FOUNDRY_MODEL", "")),
    ]
    if check_package:
        command.append("--check-package")
    for key, value in (settings or {}).items():
        command.extend(["--set", key, checked_value(key, value)])
    return "\n".join([
        "# Paste into the dev-container Bash terminal. Printing does not deploy.",
        "(", "set -euo pipefail", shlex.join(command), ")",
        "# Wait for the version to be active, then record it and run the deployed smoke test.",
    ])


def check_toolchain() -> None:
    for command in ("az", "azd"):
        if shutil.which(command) is None:
            raise RuntimeError(f"Required command {command!r} is missing. Rebuild the dev container.")
    output = subprocess.check_output(["azd", "version"], text=True)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if not match or tuple(map(int, match.groups())) < MINIMUM_AZD:
        raise RuntimeError("azd 1.34.2 or newer is required. Upgrade azd before deploying.")


def check_endpoint(endpoint: str, name: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT must be an HTTPS project endpoint.")
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://ai.azure.com",
         "--query", "accessToken", "--output", "tsv"], text=True,
    ).strip()
    if not token:
        raise RuntimeError("Azure CLI returned no access token. Run az login inside the dev container.")
    request = Request(
        f"{endpoint.rstrip('/')}/agents/{name}?api-version=v1",
        headers={"Authorization": f"Bearer {token}", "Foundry-Features": "HostedAgents=V1Preview"},
    )
    try:
        with urlopen(request, timeout=30):
            pass
    except HTTPError as exc:
        if exc.code == 404:
            return  # The first version has not been created yet.
        if exc.code == 403:
            raise RuntimeError(
                "Foundry denied access. Verify project RBAC and the approved network/private-endpoint path."
            ) from exc
        raise


def validate_cloud_settings(settings: dict[str, str]) -> None:
    if settings.get("MARKETPLACE_AZURITE_CONNECTION_STRING"):
        raise ValueError(
            "MARKETPLACE_AZURITE_CONNECTION_STRING is local-only and must not be deployed."
        )

    blob_url = settings.get("MARKETPLACE_BLOB_STORAGE_URL", "")
    if blob_url:
        parsed = urlparse(blob_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path not in ("", "/")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.hostname in {"azurite", "localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "MARKETPLACE_BLOB_STORAGE_URL must be an Azure-reachable HTTPS Blob account URL."
            )

    value = settings.get("MARKETPLACE_REDIS_URL", "")
    if value and urlparse(value).hostname in {"redis", "localhost", "127.0.0.1", "::1"}:
        raise ValueError(
            "The dev-container Redis URL cannot be used by a deployed agent. Set MARKETPLACE_REDIS_URL "
            "to a shared Azure-reachable Redis endpoint before deploying, or unset it for file-only local demos."
        )


def configure_service_environment(manifest: Path, service_name: str, names: set[str]) -> None:
    """Reference selected azd environment values from the generated agent service."""
    invalid = sorted(name for name in names if not ENVIRONMENT_NAME.fullmatch(name))
    if invalid:
        raise ValueError(f"Invalid environment variable name(s): {', '.join(invalid)}")

    lines = manifest.read_text(encoding="utf-8").splitlines()
    service_marker = f"    {service_name}:"
    try:
        service_start = lines.index(service_marker)
    except ValueError as exc:
        raise ValueError(f"Generated azure.yaml has no service named {service_name!r}.") from exc

    service_end = next(
        (
            index for index in range(service_start + 1, len(lines))
            if lines[index].startswith("    ") and not lines[index].startswith("        ")
        ),
        len(lines),
    )
    try:
        env_start = next(
            index for index in range(service_start + 1, service_end)
            if lines[index] == "        env:"
        )
    except StopIteration:
        env_start = next(
            (
                index for index in range(service_start + 1, service_end)
                if lines[index].startswith("        ")
            ),
            service_end,
        )
        lines.insert(env_start, "        env:")
        service_end += 1

    env_end = next(
        (
            index for index in range(env_start + 1, service_end)
            if not lines[index].startswith("            ")
        ),
        service_end,
    )
    existing = {
        line.strip().partition(":")[0]
        for line in lines[env_start + 1:env_end]
        if ":" in line
    }
    additions = [f"            {name}: ${{{name}}}" for name in sorted(names - existing)]
    lines[env_end:env_end] = additions
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def deploy(args: argparse.Namespace) -> None:
    settings = dict(args.settings)
    validate_cloud_settings(settings)
    folder = args.folder.resolve()
    for name in ("prepare.py", "main.py", "requirements.txt"):
        if not (folder / name).is_file():
            raise FileNotFoundError(f"Missing hosted package source: {folder / name}")
    for name in ("project_id", "project_endpoint", "model"):
        checked_value(name, getattr(args, name))
    if not args.agent_name.endswith(f"-{args.resource_suffix}"):
        raise ValueError("Agent name does not match --resource-suffix.")
    check_toolchain()
    check_endpoint(args.project_endpoint, args.agent_name)

    def run(*command: str) -> None:
        environment = None
        if command[0] == "azd":
            environment = {**os.environ, "AZURE_DEV_USER_AGENT": "microsoft_foundry_skill"}
        subprocess.run(command, cwd=folder, check=True, env=environment)

    run(sys.executable, "prepare.py")
    if args.check_package:
        run(sys.executable, "prepare.py", "--check")
    run("azd", "config", "set", "auth.useAzCliAuth", "true")
    run("azd", "extension", "install", "azure.ai.agents")
    run(
        "azd", "ai", "agent", "init", "--no-prompt", "--project-id", args.project_id,
        "--agent-name", args.agent_name, "--model-deployment", args.model, "--protocol", args.protocol,
        "--deploy-mode", "code", "--runtime", "python_3_14", "--entry-point", "main.py",
        "--dep-resolution", "remote_build",
    )
    container_settings = {**settings, "MARKETPLACE_AGENT_NAME": args.agent_name}
    configure_service_environment(folder / "azure.yaml", args.agent_name, set(container_settings))
    for key, value in container_settings.items():
        run("azd", "env", "set", key, value)
    run("azd", "up", "--no-prompt")
    print(f"Deployment submitted for {args.agent_name}. Wait for status active before invoking.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--agent-name", required=True)
    parser.add_argument("--resource-suffix", required=True)
    parser.add_argument("--protocol", choices=("responses", "invocations"), required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--set", dest="settings", nargs=2, action="append", default=[], metavar=("KEY", "VALUE"))
    parser.add_argument("--check-package", action="store_true")
    args = parser.parse_args()
    try:
        deploy(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Deployment stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
