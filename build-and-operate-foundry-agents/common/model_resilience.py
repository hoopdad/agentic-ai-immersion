"""Shared model rate-limit retries and Responses failure handling for workshop agents."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from agent_framework import ChatMiddleware

DEFAULT_MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
)


def rate_limit_response(error: Exception) -> Any | None:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        message = str(current).lower()
        if getattr(response, "status_code", None) == 429 or "rate_limit" in message or "rate limit" in message:
            return response
        current = getattr(current, "inner_exception", None) or current.__cause__
    return None


def retry_after_seconds(headers: Mapping[str, str] | None, attempt: int) -> float:
    retry_after_ms = headers.get("retry-after-ms") if headers else None
    if retry_after_ms:
        try:
            return max(float(retry_after_ms) / 1000, 0.0)
        except ValueError:
            pass
    retry_after = headers.get("retry-after") if headers else None
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return min(2 ** attempt, 60)


def rate_limit_details(headers: Mapping[str, str] | None) -> str:
    return ", ".join(
        f"{name}={headers[name]}"
        for name in RATE_LIMIT_HEADERS
        if headers and headers.get(name) is not None
    )


class RateLimitRetryMiddleware(ChatMiddleware):
    def __init__(
        self,
        logger: Callable[[str], None] = print,
        max_retries: int = DEFAULT_MAX_RATE_LIMIT_RETRIES,
    ):
        self.logger = logger
        self.max_retries = max_retries

    async def process(self, context, call_next) -> None:
        for attempt in range(1, self.max_retries + 2):
            try:
                await call_next()
                return
            except Exception as exc:
                response = rate_limit_response(exc)
                if response is None:
                    raise
                headers = response.headers
                delay = retry_after_seconds(headers, attempt)
                details = rate_limit_details(headers)
                suffix = f" ({details})" if details else ""
                if attempt > self.max_retries:
                    raise RuntimeError(
                        f"model rate limit persisted after {self.max_retries} retries; "
                        f"retry-after={delay:g}s{suffix}"
                    ) from exc
                self.logger(
                    f"model rate limit; retrying in {delay:g}s "
                    f"({attempt}/{self.max_retries}){suffix}"
                )
                await asyncio.sleep(delay)


def ensure_response_succeeded(payload: dict, label: str) -> None:
    if payload.get("status") != "failed":
        return
    error = payload.get("error") or {}
    code = error.get("code", "unknown_error") if isinstance(error, dict) else "unknown_error"
    message = error.get("message", error) if isinstance(error, dict) else error
    raise RuntimeError(f"[{label}] response failed ({code}): {str(message)[:2000]}")
