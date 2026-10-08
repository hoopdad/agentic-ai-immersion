"""List or delete Azure resources created by this workshop."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from common import foundry_env, resource_names  # noqa: E402

ARM_API_VERSION = "2025-10-01-preview"


@dataclass(frozen=True)
class Resource:
    kind: str
    name: str


def own_resources(env: dict[str, str]) -> list[Resource]:
    return [
        *(Resource("agent", resource_names.name(base, env, required=True))
          for base in resource_names.AGENT_BASE_NAMES),
        Resource("evaluation", f"{resource_names.name(resource_names.HOSTED_CONCIERGE, env, required=True)}-eval"),
        *(Resource("knowledge_base", resource_names.name(base, env, required=True))
          for base in resource_names.KNOWLEDGE_BASE_NAMES),
        *(Resource("knowledge_source", resource_names.name(base, env, required=True))
          for base in resource_names.KNOWLEDGE_SOURCE_BASE_NAMES),
        *(Resource("index", resource_names.name(base, env, required=True))
          for base in resource_names.INDEX_BASE_NAMES),
        *(Resource("connection", resource_names.name(base, env, required=True))
          for base in resource_names.CONNECTION_BASE_NAMES),
    ]


def list_connections(credential: DefaultAzureCredential, project_resource_id: str) -> list[str]:
    token = credential.get_token("https://management.azure.com/.default").token
    response = requests.get(
        f"https://management.azure.com{project_resource_id}/connections?api-version={ARM_API_VERSION}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    return [item["name"] for item in response.json().get("value", [])]


def all_resources(env: dict[str, str], credential: DefaultAzureCredential) -> list[Resource]:
    from azure.ai.projects import AIProjectClient

    foundry_env.require(env, "FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_SEARCH_ENDPOINT", "PROJECT_RESOURCE_ID")
    resources: list[Resource] = []
    with AIProjectClient(endpoint=env["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project:
        resources.extend(
            Resource("agent", item.name)
            for item in project.agents.list()
            if resource_names.belongs_to_workshop(item.name, resource_names.AGENT_BASE_NAMES)
        )
        with project.get_openai_client() as openai_client:
            resources.extend(
                Resource("evaluation", item.name)
                for item in openai_client.evals.list()
                if item.name.startswith(f"{resource_names.HOSTED_CONCIERGE}-") and item.name.endswith("-eval")
            )
    with SearchIndexClient(endpoint=env["AZURE_AI_SEARCH_ENDPOINT"], credential=credential) as search:
        resources.extend(
            Resource("knowledge_base", item.name)
            for item in search.list_knowledge_bases()
            if resource_names.belongs_to_workshop(item.name, resource_names.KNOWLEDGE_BASE_NAMES)
        )
        resources.extend(
            Resource("knowledge_source", item.name)
            for item in search.list_knowledge_sources()
            if resource_names.belongs_to_workshop(item.name, resource_names.KNOWLEDGE_SOURCE_BASE_NAMES)
        )
        resources.extend(
            Resource("index", name)
            for name in search.list_index_names()
            if resource_names.belongs_to_workshop(name, resource_names.INDEX_BASE_NAMES)
        )
    resources.extend(
        Resource("connection", name)
        for name in list_connections(credential, env["PROJECT_RESOURCE_ID"])
        if resource_names.belongs_to_workshop(name, resource_names.CONNECTION_BASE_NAMES)
    )
    return resources


def delete_connection(
    credential: DefaultAzureCredential,
    project_resource_id: str,
    name: str,
) -> None:
    token = credential.get_token("https://management.azure.com/.default").token
    response = requests.delete(
        f"https://management.azure.com{project_resource_id}/connections/{name}?api-version={ARM_API_VERSION}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if response.status_code not in (200, 202, 204, 404):
        response.raise_for_status()


def delete_resources(
    resources: list[Resource],
    env: dict[str, str],
    credential: DefaultAzureCredential,
) -> None:
    from azure.ai.projects import AIProjectClient

    foundry_env.require(env, "FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_SEARCH_ENDPOINT", "PROJECT_RESOURCE_ID")
    by_kind = {kind: [item for item in resources if item.kind == kind] for kind in {
        "agent", "evaluation", "knowledge_base", "knowledge_source", "index", "connection"
    }}
    with AIProjectClient(endpoint=env["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project:
        for item in by_kind["agent"]:
            try:
                project.agents.delete(item.name, force=True)
                print(f"deleted agent {item.name}")
            except ResourceNotFoundError:
                print(f"not found agent {item.name}")
        with project.get_openai_client() as openai_client:
            known_evals = {item.name: item.id for item in openai_client.evals.list()}
            for item in by_kind["evaluation"]:
                eval_id = known_evals.get(item.name)
                if eval_id:
                    openai_client.evals.delete(eval_id)
                    print(f"deleted evaluation {item.name}")
                else:
                    print(f"not found evaluation {item.name}")
    with SearchIndexClient(endpoint=env["AZURE_AI_SEARCH_ENDPOINT"], credential=credential) as search:
        delete_methods = {
            "knowledge_base": search.delete_knowledge_base,
            "knowledge_source": search.delete_knowledge_source,
            "index": search.delete_index,
        }
        for kind in ("knowledge_base", "knowledge_source", "index"):
            for item in by_kind[kind]:
                try:
                    delete_methods[kind](item.name)
                    print(f"deleted {kind} {item.name}")
                except ResourceNotFoundError:
                    print(f"not found {kind} {item.name}")
    for item in by_kind["connection"]:
        delete_connection(credential, env["PROJECT_RESOURCE_ID"], item.name)
        print(f"deleted connection {item.name}")


def project_name(project_resource_id: str) -> str:
    return project_resource_id.rstrip("/").split("/")[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("own", "all"), default="own")
    parser.add_argument("--execute", action="store_true", help="Delete the listed resources; default is dry-run.")
    parser.add_argument(
        "--confirm-all",
        metavar="PROJECT_NAME",
        help="Required with --scope all --execute; must equal the project name in PROJECT_RESOURCE_ID.",
    )
    args = parser.parse_args()
    env = foundry_env.load_env()
    credential = DefaultAzureCredential()
    if args.scope == "all":
        expected = project_name(env.get("PROJECT_RESOURCE_ID", ""))
        if args.execute and args.confirm_all != expected:
            parser.error(f"--confirm-all must equal {expected!r} for all-attendee cleanup")
        resources = all_resources(env, credential)
    else:
        resources = own_resources(env)
    action = "DELETE" if args.execute else "would delete"
    for item in resources:
        print(f"{action:12} {item.kind:16} {item.name}")
    if not args.execute:
        print("Dry run only. Add --execute after reviewing the list.")
        return 0
    delete_resources(resources, env, credential)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
