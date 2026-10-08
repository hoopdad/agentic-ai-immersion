"""Stable workshop resource names scoped by one attendee suffix."""
from __future__ import annotations

import os
import re

SUFFIX_ENV = "MARKETPLACE_RESOURCE_SUFFIX"
LOCAL_SUFFIX = "local"
SUFFIX_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,14}[a-z0-9])?$")

HOSTED_CONCIERGE = "healthcare-marketplace-concierge-hosted"
HOSTED_TRIAGE = "healthcare-marketplace-triage-hosted"
HOSTED_CLAIMS = "healthcare-marketplace-claims-review-invocations"
PROMPT_CONCIERGE = "healthcare-marketplace-concierge"
PROMPT_TRIAGE = "healthcare-marketplace-concierge-triage"
PROMPT_MARKETPLACE = "marketplace-guide"
PROMPT_ACCOUNTS = "accounts-assistant"
PROMPT_COMPLIANCE = "compliance-reviewer"
PROMPT_HANDOFF = "advisor-handoff"
WORKFLOW_TRIAGE = "healthcare-marketplace-triage-workflow"
SEARCH_INDEX_MARKETPLACE = "healthcare-marketplace-kb-marketplace"
SEARCH_INDEX_ACCOUNTS = "healthcare-marketplace-kb-accounts"
KNOWLEDGE_SOURCE_MARKETPLACE = "marketplace-ks"
KNOWLEDGE_SOURCE_ACCOUNTS = "accounts-ks"
KNOWLEDGE_BASE = "healthcare-marketplace-kb"
PROJECT_CONNECTION = "healthcare-marketplace-kb-connection"

AGENT_BASE_NAMES = (
    HOSTED_CONCIERGE,
    HOSTED_TRIAGE,
    HOSTED_CLAIMS,
    PROMPT_CONCIERGE,
    PROMPT_TRIAGE,
    PROMPT_MARKETPLACE,
    PROMPT_ACCOUNTS,
    PROMPT_COMPLIANCE,
    PROMPT_HANDOFF,
    WORKFLOW_TRIAGE,
)
INDEX_BASE_NAMES = (SEARCH_INDEX_MARKETPLACE, SEARCH_INDEX_ACCOUNTS)
KNOWLEDGE_SOURCE_BASE_NAMES = (KNOWLEDGE_SOURCE_MARKETPLACE, KNOWLEDGE_SOURCE_ACCOUNTS)
KNOWLEDGE_BASE_NAMES = (KNOWLEDGE_BASE,)
CONNECTION_BASE_NAMES = (PROJECT_CONNECTION,)


def suffix(env: dict[str, str] | None = None, *, required: bool = False) -> str:
    raw = (env or {}).get(SUFFIX_ENV) or os.environ.get(SUFFIX_ENV, "")
    value = raw.strip().lower()
    placeholder = not value or (value.startswith("<") and value.endswith(">"))
    if placeholder:
        if required:
            raise RuntimeError(
                f"Set {SUFFIX_ENV} in the repository-root .env to a unique value such as jd-4821."
            )
        return LOCAL_SUFFIX
    if not SUFFIX_RE.fullmatch(value):
        raise ValueError(
            f"{SUFFIX_ENV} must be 1-16 lowercase letters, numbers, or hyphens; "
            "it must start and end with a letter or number."
        )
    if required and value == LOCAL_SUFFIX:
        raise ValueError(f"{SUFFIX_ENV}=local is reserved for offline checks; choose a unique attendee suffix.")
    return value


def name(base: str, env: dict[str, str] | None = None, *, required: bool = False) -> str:
    return f"{base}-{suffix(env, required=required)}"


def belongs_to_workshop(candidate: str, base_names: tuple[str, ...]) -> bool:
    return any(
        candidate.startswith(f"{base}-") and SUFFIX_RE.fullmatch(candidate[len(base) + 1:])
        for base in base_names
    )
