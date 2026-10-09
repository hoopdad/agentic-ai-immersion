"""Labs 5-6, notebook part: Foundry IQ knowledge base over Azure AI Search.

Runs on:  the learner workstation (notebook or python). Nothing here ships in the container.
Goal:     Turn data/knowledge/*.md into two search indexes (marketplace and accounts, each with
          the universal docs), two knowledge sources, one knowledge base (healthcare-marketplace-kb) and a
          project connection so a managed identity can call the knowledge base over MCP. The hosted
          agent in hosted/main.py reaches the same MCP endpoint with MCPStreamableHTTPTool.
Inputs:   artifacts/lab2/hosted.json (chain check: Labs 3-4 deployed the basics agent); data/knowledge
Outputs:  artifacts/lab3/knowledge.json  indexes, knowledge sources, kb name, mcp endpoint, connection
Time:     about 15 min of the Do block (the index build itself takes 1 to 2 min)

Run:      python knowledge_base.py                   build + demo (direct index queries)
          python knowledge_base.py --skip-connection  build indexes and kb only (no ARM call)
          python knowledge_base.py --demo-only
lab3_hosted_knowledge.py imports this module and calls build() as its first step.
"""
# %% Imports and environment
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]      # build-and-operate-foundry-agents/ (common/ and data/ live here)
sys.path.insert(0, str(ROOT))
from common import marketplace_data, foundry_env, guardrails, resource_names  # noqa: E402,F401

LABS_DIR = ROOT / "3-day-labs"
sys.path.insert(0, str(LABS_DIR))
import lab_helpers as helpers  # noqa: E402

import requests  # noqa: E402
from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from azure.search.documents import SearchClient  # noqa: E402
from azure.search.documents.indexes import SearchIndexClient  # noqa: E402
from azure.search.documents.indexes.models import (  # noqa: E402
    AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters, HnswAlgorithmConfiguration, KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel, KnowledgeSourceReference, SearchField, SearchFieldDataType, SearchIndex,
    SearchIndexFieldReference, SearchIndexKnowledgeSource, SearchIndexKnowledgeSourceParameters,
    SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch, VectorSearch,
    VectorSearchProfile)
from openai import AzureOpenAI, RateLimitError  # noqa: E402

ENV = foundry_env.load_env()
MODEL = helpers.pick_model(ENV)
EMBEDDING = ENV.get("EMBEDDING_MODEL_DEPLOYMENT_NAME") or "text-embedding-3-large"
LAB = "lab3"

# %% Names: one bounded context per index, universal docs in both
INDEX_MARKETPLACE = resource_names.name(resource_names.SEARCH_INDEX_MARKETPLACE, ENV)
INDEX_ACCOUNTS = resource_names.name(resource_names.SEARCH_INDEX_ACCOUNTS, ENV)
INDEXES = {
    INDEX_MARKETPLACE: ["marketplace", "universal"],
    INDEX_ACCOUNTS: ["accounts", "universal"],
}
KNOWLEDGE_SOURCES = {
    resource_names.name(resource_names.KNOWLEDGE_SOURCE_MARKETPLACE, ENV): INDEX_MARKETPLACE,
    resource_names.name(resource_names.KNOWLEDGE_SOURCE_ACCOUNTS, ENV): INDEX_ACCOUNTS,
}
KB_NAME = resource_names.name(resource_names.KNOWLEDGE_BASE, ENV)
CONNECTION_NAME = resource_names.name(resource_names.PROJECT_CONNECTION, ENV)
KB_API_VERSION = "2025-11-01-Preview"
ARM_API_VERSION = "2025-10-01-preview"
VECTOR_DIMS = 3072                      # text-embedding-3-large
VECTOR_PROFILE = "marketplace-vector-profile"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
EMBEDDING_BATCH_SIZE = 16
MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
)


def search_endpoint() -> str:
    endpoint = ENV.get("AZURE_AI_SEARCH_ENDPOINT")
    if not endpoint:
        raise SystemExit("[lab3] AZURE_AI_SEARCH_ENDPOINT is not set in .env (see SETUP.md)")
    return endpoint.rstrip("/")


def aoai_resource_url() -> str:
    """Resource URL for the vectorizer and the knowledge base model (no /openai/ suffix)."""
    endpoint = ENV.get("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        return endpoint.split("/openai/")[0].rstrip("/")
    project = ENV.get("FOUNDRY_PROJECT_ENDPOINT", "")
    host = re.match(r"https://[^/]+", project)
    if not host:
        raise SystemExit("[lab3] set AZURE_OPENAI_ENDPOINT (or FOUNDRY_PROJECT_ENDPOINT) in .env")
    print(f"[lab3] AZURE_OPENAI_ENDPOINT not set, using the Foundry host {host.group(0)}")
    return host.group(0)


def deployed_model_name(kind: str, deployment_name: str) -> str:
    """Resolve the underlying model, never treating an attendee deployment alias as a model name."""
    path = helpers.artifact_path("lab1", "project.json")
    if path.is_file():
        checkpoint = foundry_env.load_artifact(path)
        expected = {
            "project_resource_id": ENV.get("PROJECT_RESOURCE_ID"),
            "project_endpoint": ENV.get("FOUNDRY_PROJECT_ENDPOINT"),
            "resource_suffix": ENV.get("MARKETPLACE_RESOURCE_SUFFIX"),
        }
        if checkpoint.get("provisioning_state") != "Succeeded" or any(
            checkpoint.get("smoke_tests", {}).get(model) != "passed" for model in ("chat", "embedding")
        ):
            raise RuntimeError("Complete the Labs 1-2 model smoke tests before building Search resources.")
        if any(not value or checkpoint.get(key) != value for key, value in expected.items()) or \
                checkpoint.get("azure_openai_endpoint", "").rstrip("/") != aoai_resource_url() or \
                checkpoint.get("chat_deployment", {}).get("name") != MODEL or \
                checkpoint.get("embedding_deployment", {}).get("name") != EMBEDDING:
            raise RuntimeError("Labs 1-2 model checkpoint does not match the current project and deployment configuration.")
        deployment = checkpoint.get(f"{kind}_deployment", {})
    else:
        project_id = ENV.get("PROJECT_RESOURCE_ID", "")
        match = re.fullmatch(
            r"(/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.CognitiveServices/accounts/[^/]+)"
            r"/projects/[^/]+",
            project_id, re.IGNORECASE,
        )
        if not match:
            raise RuntimeError("Set the current PROJECT_RESOURCE_ID before discovering deployed model metadata.")
        setup = helpers.load_lab_module("foundry-project-models/project_setup.py")
        cli = setup.AzureCLI()
        account = cli.rest("get", match.group(1))
        project = cli.rest("get", project_id)
        project_endpoint, openai_endpoint = setup.endpoints(account, project)
        if project_endpoint != ENV.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/") or \
                openai_endpoint.rstrip("/") != aoai_resource_url():
            raise RuntimeError("Discovered model account does not match the current project and OpenAI endpoints.")
        resource_id = f"{match.group(1)}/deployments/{quote(deployment_name, safe='')}"
        deployment = cli.rest("get", resource_id)
        if deployment.get("name") != deployment_name or deployment.get("id", "").lower() != resource_id.lower() or \
                deployment.get("properties", {}).get("provisioningState") != "Succeeded":
            raise RuntimeError("Discovered model deployment does not match the current target or is not ready.")
    model = deployment.get("properties", {}).get("model", {})
    if model.get("format") != "OpenAI" or not model.get("name"):
        raise RuntimeError("The deployed OpenAI model metadata is missing; rerun the Labs 1-2 verified handoff.")
    return model["name"]


# %% Documents: frontmatter, heading chunks, index records
def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.split("#")[0].strip().strip('"')
    return meta, text[match.end():]


def chunk_by_heading(body: str, min_words: int = 40) -> list[tuple[str, str]]:
    """Split Markdown on headings; fold very short sections into the previous one."""
    chunks: list[tuple[str, list[str]]] = []
    heading = "Introduction"
    for line in body.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip() or heading
            chunks.append((heading, []))
            continue
        if not chunks:
            chunks.append((heading, []))
        chunks[-1][1].append(line)
    merged: list[tuple[str, str]] = []
    for title, lines in chunks:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if merged and len(text.split()) < min_words:
            prev_title, prev_text = merged[-1]
            merged[-1] = (prev_title, f"{prev_text}\n\n{title}\n{text}")
        else:
            merged.append((title, text))
    return merged


def load_records(contexts: list[str]) -> list[dict]:
    """One index record per heading chunk, tagged with doc_id and context for citations and filters."""
    records = []
    for context in contexts:
        for doc in marketplace_data.list_knowledge_docs(context):
            meta, body = split_frontmatter(marketplace_data.read_knowledge_doc(doc["doc_id"]))
            title = meta.get("title") or doc["title"]
            for n, (heading, text) in enumerate(chunk_by_heading(body), start=1):
                records.append({
                    "id": f"{doc['doc_id']}-{n}",
                    "title": f"{title}: {heading}",
                    "content": f"[{doc['doc_id']}] {title}\n{heading}\n\n{text}",
                    "doc_id": doc["doc_id"],
                    "context": doc.get("context", context),
                })
    return records


# %% Embeddings (Entra token, no keys)
def retry_after_seconds(headers, attempt: int) -> float:
    retry_after_ms = headers.get("retry-after-ms")
    if retry_after_ms:
        try:
            return max(float(retry_after_ms) / 1000, 0.0)
        except ValueError:
            pass
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return min(2 ** attempt, 60)


def rate_limit_details(headers) -> str:
    return ", ".join(
        f"{name}={headers[name]}"
        for name in RATE_LIMIT_HEADERS
        if headers.get(name) is not None
    )


def make_embedder(credential):
    client = AzureOpenAI(
        azure_endpoint=aoai_resource_url(),
        azure_ad_token_provider=get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default"),
        api_version="2024-02-01",
        max_retries=0,
    )

    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start:start + EMBEDDING_BATCH_SIZE]
            for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 2):
                try:
                    response = client.embeddings.with_raw_response.create(input=batch, model=EMBEDDING)
                    break
                except RateLimitError as exc:
                    if attempt > MAX_RATE_LIMIT_RETRIES:
                        raise
                    delay = retry_after_seconds(exc.response.headers, attempt)
                    details = rate_limit_details(exc.response.headers)
                    suffix = f" ({details})" if details else ""
                    print(
                        f"[lab3] embedding rate limit; retrying in {delay:g}s "
                        f"({attempt}/{MAX_RATE_LIMIT_RETRIES}){suffix}",
                        flush=True,
                    )
                    time.sleep(delay)
            details = rate_limit_details(response.headers)
            if details:
                print(f"[lab3] embedding rate limits: {details}", flush=True)
            result = response.parse()
            vectors.extend(item.embedding for item in result.data)
        return vectors

    return embed


# %% Index definition: keyword + vector + semantic, vectorizer for query-time embeddings
def index_definition(name: str) -> SearchIndex:
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="doc_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="context", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=VECTOR_DIMS,
                    vector_search_profile_name=VECTOR_PROFILE),
    ]
    # VERIFY against https://learn.microsoft.com/python/api/azure-search-documents/ before delivery:
    # keyword names vectorizer_name / algorithm_configuration_name on 11.7.0b2.
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="marketplace-hnsw")],
        profiles=[VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name="marketplace-hnsw",
                                      vectorizer_name="marketplace-aoai-vectorizer")],
        vectorizers=[AzureOpenAIVectorizer(
            vectorizer_name="marketplace-aoai-vectorizer",
            parameters=AzureOpenAIVectorizerParameters(resource_url=aoai_resource_url(),
                                                       deployment_name=EMBEDDING,
                                                       model_name=deployed_model_name("embedding", EMBEDDING)))],
    )
    semantic = SemanticSearch(
        default_configuration_name="marketplace-semantic",
        configurations=[SemanticConfiguration(
            name="marketplace-semantic",
            prioritized_fields=SemanticPrioritizedFields(title_field=SemanticField(field_name="title"),
                                                         content_fields=[SemanticField(field_name="content")]))],
    )
    return SearchIndex(name=name, fields=fields, vector_search=vector_search, semantic_search=semantic)


def build_index(index_client: SearchIndexClient, credential, name: str, contexts: list[str], embed) -> int:
    index_client.create_or_update_index(index_definition(name))
    records = load_records(contexts)
    for record, vector in zip(records, embed([r["content"] for r in records])):
        record["content_vector"] = vector
    SearchClient(endpoint=search_endpoint(), index_name=name, credential=credential).upload_documents(records)
    doc_ids = sorted({r["doc_id"] for r in records})
    print(f"[lab3] index {name}: {len(records)} chunks from {len(doc_ids)} docs {doc_ids}")
    return len(records)


# %% Knowledge sources and the knowledge base
def build_knowledge_sources(index_client: SearchIndexClient) -> None:
    for ks_name, index_name in KNOWLEDGE_SOURCES.items():
        source = SearchIndexKnowledgeSource(
            name=ks_name,
            description=f"Healthcare Marketplace functional documentation, {index_name.split('-')[-1]} context",
            search_index_parameters=SearchIndexKnowledgeSourceParameters(
                search_index_name=index_name,
                source_data_fields=[SearchIndexFieldReference(name="content"), SearchIndexFieldReference(name="title")]),
        )
        # VERIFY against the azure-search-documents 11.7.0b2 reference before delivery (method name).
        index_client.create_or_update_knowledge_source(knowledge_source=source)
        print(f"[lab3] knowledge source {ks_name} -> {index_name}")


def build_knowledge_base(index_client: SearchIndexClient) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=KB_NAME,
        description="Healthcare Marketplace knowledge: plans, enrollment periods, HRA rules, "
                    "handoff and privacy policy. Retrieve first, then cite doc ids like [KB-ACC-001].",
        knowledge_sources=[KnowledgeSourceReference(name=ks) for ks in KNOWLEDGE_SOURCES],
        models=[KnowledgeBaseAzureOpenAIModel(azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
            resource_url=aoai_resource_url(), deployment_name=MODEL,
            model_name=deployed_model_name("chat", MODEL)))],
    )
    index_client.create_or_update_knowledge_base(knowledge_base=kb)
    print(f"[lab3] knowledge base {KB_NAME} with sources {list(KNOWLEDGE_SOURCES)}")
    return kb


def mcp_endpoint() -> str:
    return f"{search_endpoint()}/knowledgebases/{KB_NAME}/mcp?api-version={KB_API_VERSION}"


# %% Project connection (ARM) so the project managed identity can call the MCP endpoint
def create_project_connection(credential, target: str) -> dict:
    project_resource_id = ENV.get("PROJECT_RESOURCE_ID")
    if not project_resource_id:
        raise SystemExit("[lab3] PROJECT_RESOURCE_ID is not set in .env; needed for the project connection")
    url = f"https://management.azure.com{project_resource_id}/connections/{CONNECTION_NAME}?api-version={ARM_API_VERSION}"
    token = credential.get_token("https://management.azure.com/.default").token
    body = {
        "name": CONNECTION_NAME,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": target,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    }
    response = requests.put(url, json=body, timeout=60,
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if response.status_code not in (200, 201):
        raise SystemExit(f"[lab3] connection PUT failed {response.status_code}: {response.text[:500]}")
    connection_id = response.json().get("id") or f"{project_resource_id}/connections/{CONNECTION_NAME}"
    print(f"[lab3] project connection {CONNECTION_NAME} -> {target}")
    return {"connection_name": CONNECTION_NAME, "connection_id": connection_id, "target": target}


# %% build(): everything above, then the checkpoint artifact
def save_build_artifact(lab2: dict, counts: dict[str, int], credential, skip_connection: bool = False) -> dict:
    info = {
        "lab": LAB,
        "built_after": {"agent_name": lab2.get("agent_name"), "agent_version": lab2.get("agent_version")},
        "search_endpoint": search_endpoint(),
        "indexes": counts,
        "knowledge_sources": KNOWLEDGE_SOURCES,
        "kb_name": KB_NAME,
        "mcp_endpoint": mcp_endpoint(),
        "retrieval_tool_name": "knowledge_base_retrieve",
        "connection": {} if skip_connection else create_project_connection(credential, mcp_endpoint()),
        "created_at": helpers.now_iso(),
    }
    path = helpers.artifact_path(LAB, "knowledge.json")
    if path.exists():
        info = {**foundry_env.load_artifact(path), **info}      # keep hosted info written by lab3_hosted_knowledge
    foundry_env.save_artifact(path, info)
    print(f"[lab3] saved {path.relative_to(LABS_DIR)}")
    if skip_connection:
        print("[lab3] connection skipped: rerun without --skip-connection before building the agent")
    return info


def build(skip_connection: bool = False) -> dict:
    resource_names.suffix(ENV, required=True)
    lab2 = helpers.require_artifact("lab2", "hosted.json", through=2, caller="lab3")
    credential = AzureCliCredential()
    index_client = SearchIndexClient(endpoint=search_endpoint(), credential=credential)
    embed = make_embedder(credential)
    counts = {name: build_index(index_client, credential, name, contexts, embed) for name, contexts in INDEXES.items()}
    build_knowledge_sources(index_client)
    build_knowledge_base(index_client)
    return save_build_artifact(lab2, counts, credential, skip_connection)


# %% demo(): query the indexes directly, the same way the knowledge base will
def demo(questions: dict[str, str] | None = None) -> None:
    helpers.require_artifact(LAB, "knowledge.json", through=3, caller="lab3")
    credential = AzureCliCredential()
    questions = questions or {
        INDEX_MARKETPLACE: "When is the annual enrollment period and what can I change?",
        INDEX_ACCOUNTS: "Which documents count as proof of payment for a premium claim?",
    }
    for index_name, question in questions.items():
        client = SearchClient(endpoint=search_endpoint(), index_name=index_name, credential=credential)
        hits = client.search(search_text=question, top=3, select=["doc_id", "title", "context"])
        print(f"[lab3] {index_name}: {question}")
        for hit in hits:
            print(f"[lab3]   {hit['doc_id']:<11} {hit['title'][:70]}  ({hit['context']})")
    print(f"[lab3] knowledge base MCP endpoint: {mcp_endpoint()}")
    print(f"[lab3] portal: Azure AI Search > Knowledge bases > {KB_NAME}; Foundry > Management center > Connections")
    print("[lab3] the hosted agent reads this endpoint from MARKETPLACE_KB_MCP_URL (lab3_hosted_knowledge.py sets it)")


# %% YOUR TURN (5 min): semantic ranking
# Rerun one query with semantic ranking and captions. Compare the order of hits.
#
def semantic_ranking_acceptance_gate() -> list[dict]:
    client = SearchClient(
        endpoint=search_endpoint(),
        index_name=INDEX_ACCOUNTS,
        credential=AzureCliCredential(),
    )
    hits = list(client.search(
        search_text="my card was declined at the pharmacy",
        top=3,
        query_type="semantic",
        semantic_configuration_name="marketplace-semantic",
        query_caption="extractive",
        select=["doc_id", "title"],
    ))
    assert hits, "Semantic ranking returned no results."
    assert any(hit.get("@search.captions") for hit in hits), "Semantic captions were not returned."
    for hit in hits:
        print(hit["doc_id"], hit["title"], (hit.get("@search.captions") or [None])[0])
    return hits


if "__file__" not in globals() and os.environ.get("RUN_LAB3_SEMANTIC_GATE") == "1":
    semantic_ranking_acceptance_gate()

# %% YOUR TURN (5 min): scope retrieval by context
# The universal docs live in both indexes. Filter them out of a marketplace query with an OData filter.
#
def scoped_retrieval_acceptance_gate() -> list[dict]:
    client = SearchClient(
        endpoint=search_endpoint(),
        index_name=INDEX_MARKETPLACE,
        credential=AzureCliCredential(),
    )
    hits = list(client.search(
        search_text="when may an assistant recommend a plan",
        top=3,
        filter="context eq 'marketplace'",
        select=["doc_id", "title", "context"],
    ))
    assert hits, "The scoped marketplace query returned no results."
    assert all(hit["context"] == "marketplace" for hit in hits), "The OData filter returned another context."
    assert all(hit["doc_id"] != "KB-UNI-001" for hit in hits), "The universal licensing document was not filtered out."
    for hit in hits:
        print(hit["doc_id"], hit["title"])
    return hits


if "__file__" not in globals() and os.environ.get("RUN_LAB3_SCOPE_GATE") == "1":
    scoped_retrieval_acceptance_gate()

# %% YOUR TURN (5 min): change the chunking
# Set min_words=120 in chunk_by_heading and rebuild healthcare-marketplace-kb-accounts. Count the chunks before and after,
# then rerun the proof-of-payment query. Bigger chunks carry more context but blur citations.
#
def chunking_acceptance_gate() -> tuple[int, int]:
    contexts = INDEXES[INDEX_ACCOUNTS]
    original_count = len(load_records(contexts))
    original_defaults = chunk_by_heading.__defaults__
    credential = AzureCliCredential()
    index_client = SearchIndexClient(endpoint=search_endpoint(), credential=credential)
    embed = make_embedder(credential)
    try:
        chunk_by_heading.__defaults__ = (120,)
        larger_chunk_count = len(load_records(contexts))
        assert larger_chunk_count < original_count, (
            f"Expected fewer chunks at min_words=120, got original={original_count}, larger={larger_chunk_count}."
        )
        built_count = build_index(
            index_client,
            credential,
            INDEX_ACCOUNTS,
            contexts,
            embed,
        )
        assert built_count == larger_chunk_count, "The rebuilt index count did not match the 120-word chunk plan."
        return original_count, larger_chunk_count
    finally:
        chunk_by_heading.__defaults__ = original_defaults
        restored_count = build_index(
            index_client,
            credential,
            INDEX_ACCOUNTS,
            contexts,
            embed,
        )
        assert restored_count == original_count, "The acceptance gate did not restore the original chunking."


if "__file__" not in globals() and os.environ.get("RUN_LAB3_CHUNKING_GATE") == "1":
    print("chunk counts:", chunking_acceptance_gate())


# %% Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-connection", action="store_true", help="skip the ARM connection PUT")
    parser.add_argument("--demo-only", action="store_true", help="query existing indexes only")
    args = parser.parse_args()
    if not args.demo_only:
        build(skip_connection=args.skip_connection)
    demo()
