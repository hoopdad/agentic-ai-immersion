"""Chat message store for Agent Framework sessions (Lab 3 imports it; Lab 4 and S7 reuse the helpers).

Hosted agents are stateless containers by design. If the conversation history lives inside the process, a
restart, a version roll or a second replica loses the participant mid-call. This module keeps the history
OUTSIDE the container, keyed by session id, with three interchangeable backends:

* AzureBlobMessageStore   one bounded JSON blob per session, opt-in with an Azure Blob URL and managed identity
                          or a local Azurite connection string. ETags protect concurrent replica updates.
* RedisMessageStore       redis-py, key marketplace:messages:<session_id> (a Redis list, one JSON message per entry),
                          TTL MARKETPLACE_SESSION_TTL_SECONDS (default 7 days). Shared by every replica.
* FileMessageStore        <dir>/<session_id>.messages.json. One laptop, the "kill it and restart" demo.

Plus the glue Agent Framework needs:

* serialize_messages / deserialize_messages   Message objects <-> JSON friendly dicts
* get_message_store(default_dir)              Azure Blob/Azurite, Redis, then files
* as_history_provider(store)                  wraps a store as an Agent Framework history (context) provider
* build_history_provider(default_dir)         RedisHistoryProvider for Redis, otherwise a store wrapped by
                                              as_history_provider

Pattern source: Agent Framework's `ContextProvider` lifecycle. The hosted Responses server owns protocol history,
so Blob, Azurite, and file stores add durable context without registering a second framework `HistoryProvider`.

No agent_framework or redis import happens at module import time. `python common/message_store.py` runs the
file-backend self-test on a machine with nothing installed.

Usage (hosted main.py):
    from common import message_store
    provider = message_store.build_history_provider(HERE / "message_store")
    agent = Agent(client=client, instructions=..., tools=..., context_providers=[provider],
                  default_options={"store": False})
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable, Protocol, runtime_checkable
from urllib.parse import urlparse

DEFAULT_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_MAX_MESSAGES = 200
REDIS_KEY_PREFIX = "marketplace:messages"
FILE_SUFFIX = ".messages.json"
BLOB_PREFIX = "sessions/"
BLOB_CONTAINER_DEFAULT = "marketplace-history"
MAX_BLOB_WRITE_RETRIES = 5


def _safe_id(session_id: str) -> str:
    from common.session_store import safe_session_id   # same sanitiser as the session map

    return safe_session_id(session_id)


# ---------------------------------------------------------------------------
# Serialization: Message objects <-> dicts
# ---------------------------------------------------------------------------
def message_to_dict(message: Any) -> dict:
    """One message as a JSON friendly dict. Accepts Agent Framework Message objects or plain dicts."""
    if isinstance(message, dict):
        return dict(message)
    for attr in ("to_dict", "model_dump"):
        method = getattr(message, attr, None)
        if callable(method):
            try:
                data = method()
                if isinstance(data, dict):
                    return data
            except TypeError:
                continue
    return {"role": str(getattr(message, "role", "user")), "text": getattr(message, "text", str(message))}


def message_from_dict(data: dict) -> Any:
    """Rebuild a Message, normalizing legacy text rows to the SDK's contents format."""
    try:
        from agent_framework import Message
    except ImportError:
        return dict(data)
    normalized = dict(data)
    text = normalized.pop("text", None)
    if text is not None and not normalized.get("contents"):
        normalized["contents"] = [{"type": "text", "text": text}]
    return Message.from_dict(normalized)


def serialize_messages(messages: Iterable[Any]) -> list[dict]:
    return [message_to_dict(message) for message in messages]


def deserialize_messages(rows: Iterable[dict]) -> list[Any]:
    return [message_from_dict(row) for row in rows]


def message_text(message: Any) -> str:
    """Plain text of a message or dict, for transcripts and tests."""
    if isinstance(message, dict):
        return message.get("text") or " ".join(
            part.get("text", "") for part in message.get("contents", []) if isinstance(part, dict)) or ""
    return getattr(message, "text", "") or ""


def message_role(message: Any) -> str:
    role = message.get("role") if isinstance(message, dict) else getattr(message, "role", "user")
    value = getattr(role, "value", role)
    return str(value)


# ---------------------------------------------------------------------------
# The store contract (synchronous, plain Python)
# ---------------------------------------------------------------------------
@runtime_checkable
class MessageStore(Protocol):
    def get_messages(self, session_id: str) -> list[dict]: ...
    def add_messages(self, session_id: str, messages: Iterable[Any]) -> None: ...
    def clear(self, session_id: str) -> None: ...
    def list_session_ids(self) -> list[str]: ...


class FileMessageStore:
    """<directory>/<session_id>.messages.json holding a JSON list of messages. Not shared across replicas."""

    kind = "file"

    def __init__(self, directory: Path | str, max_messages: int = DEFAULT_MAX_MESSAGES):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_messages = max_messages

    def _path(self, session_id: str) -> Path:
        return self.directory / f"{_safe_id(session_id)}{FILE_SUFFIX}"

    def get_messages(self, session_id: str) -> list[dict]:
        path = self._path(session_id)
        if not path.is_file():
            return []
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return []
        return list(rows)[-self.max_messages:] if isinstance(rows, list) else []

    def add_messages(self, session_id: str, messages: Iterable[Any]) -> None:
        rows = self.get_messages(session_id) + serialize_messages(messages)
        rows = rows[-self.max_messages:]
        path = self._path(session_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
        tmp.replace(path)                                    # atomic on the same file system

    def clear(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.is_file():
            path.unlink()

    def list_session_ids(self) -> list[str]:
        return sorted(path.name[: -len(FILE_SUFFIX)] for path in self.directory.glob(f"*{FILE_SUFFIX}"))

    def __repr__(self) -> str:
        return f"FileMessageStore({self.directory})"


class RedisMessageStore:
    """redis-py backed store. Key marketplace:messages:<session_id> is a list; every write refreshes the TTL.

    Local Redis for the workshop: docker run -d --name redis-workshop -p 6379:6379 redis:7-alpine and
    MARKETPLACE_REDIS_URL=redis://localhost:6379/0. Azure Managed Redis with Entra: a rediss:// URL and a
    token-refreshing client passed through `client`.
    """

    kind = "redis"

    def __init__(self, url: str | None = None, ttl_seconds: int | None = None, client=None,
                 key_prefix: str = REDIS_KEY_PREFIX, max_messages: int = DEFAULT_MAX_MESSAGES):
        import redis                                         # lazy: only when this backend is chosen

        self.url = url or os.environ.get("MARKETPLACE_REDIS_URL", "redis://localhost:6379/0")
        self.ttl_seconds = int(ttl_seconds or os.environ.get("MARKETPLACE_SESSION_TTL_SECONDS") or DEFAULT_TTL_SECONDS)
        self.key_prefix = key_prefix.rstrip(":")
        self.max_messages = max_messages
        self.client = client or redis.Redis.from_url(self.url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{_safe_id(session_id)}"

    def get_messages(self, session_id: str) -> list[dict]:
        rows = self.client.lrange(self._key(session_id), -self.max_messages, -1)
        out = []
        for raw in rows:
            try:
                out.append(json.loads(raw))
            except ValueError:
                continue
        return out

    def add_messages(self, session_id: str, messages: Iterable[Any]) -> None:
        rows = [json.dumps(row, default=str) for row in serialize_messages(messages)]
        if not rows:
            return
        key = self._key(session_id)
        pipe = self.client.pipeline()
        pipe.rpush(key, *rows)
        pipe.ltrim(key, -self.max_messages, -1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    def clear(self, session_id: str) -> None:
        self.client.delete(self._key(session_id))

    def list_session_ids(self) -> list[str]:
        prefix = f"{self.key_prefix}:"
        return sorted(key[len(prefix):] for key in self.client.scan_iter(match=f"{prefix}*", count=200))

    def __repr__(self) -> str:
        return f"RedisMessageStore({self.url}, ttl={self.ttl_seconds}s)"


class AzureBlobMessageStore:
    """One bounded JSON history blob per session, shared by hosted replicas."""

    kind = "azure-blob"

    def __init__(
        self,
        *,
        account_url: str | None = None,
        azurite_connection_string: str | None = None,
        container_name: str = BLOB_CONTAINER_DEFAULT,
        ttl_seconds: int | None = None,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        container_client: Any | None = None,
    ):
        if account_url and azurite_connection_string:
            raise ValueError(
                "Set either MARKETPLACE_BLOB_STORAGE_URL or "
                "MARKETPLACE_AZURITE_CONNECTION_STRING, not both."
            )
        if not container_name:
            raise ValueError("MARKETPLACE_BLOB_STORAGE_CONTAINER must not be empty.")

        self.account_url = account_url
        self.container_name = container_name
        self.ttl_seconds = int(
            ttl_seconds or os.environ.get("MARKETPLACE_SESSION_TTL_SECONDS") or DEFAULT_TTL_SECONDS
        )
        self.max_messages = max_messages
        self.service_client = None
        self.credential = None
        self._container_verified = container_client is not None

        if container_client is not None:
            self.container_client = container_client
        elif azurite_connection_string:
            from azure.core.exceptions import ResourceExistsError
            from azure.storage.blob import BlobServiceClient

            self.service_client = BlobServiceClient.from_connection_string(azurite_connection_string)
            parsed = urlparse(self.service_client.url)
            if parsed.scheme != "http" or parsed.hostname not in {
                "azurite", "localhost", "127.0.0.1", "::1",
            }:
                self.close()
                raise ValueError("MARKETPLACE_AZURITE_CONNECTION_STRING must target a local Azurite endpoint.")
            self.container_client = self.service_client.get_container_client(container_name)
            try:
                self.container_client.create_container()
            except ResourceExistsError:
                pass
            self._container_verified = True
        elif account_url:
            parsed = urlparse(account_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.path not in ("", "/")
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("MARKETPLACE_BLOB_STORAGE_URL must be an HTTPS Blob account URL.")
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient

            self.credential = DefaultAzureCredential()
            self.service_client = BlobServiceClient(account_url, credential=self.credential)
            self.container_client = self.service_client.get_container_client(container_name)
        else:
            raise ValueError("Configure an Azure Blob URL or Azurite connection string.")

    def _ensure_container(self) -> None:
        if not self._container_verified:
            self.container_client.get_container_properties()
            self._container_verified = True

    @staticmethod
    def _blob_name(session_id: str) -> str:
        return f"{BLOB_PREFIX}{_safe_id(session_id)}{FILE_SUFFIX}"

    @staticmethod
    def _decode_rows(data: bytes) -> list[dict]:
        rows = json.loads(data)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Azure Blob conversation history must be a JSON array of message objects.")
        return rows

    def _read_snapshot(self, blob: Any) -> tuple[list[dict], str | None, bool]:
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError

        for _ in range(MAX_BLOB_WRITE_RETRIES):
            try:
                properties = blob.get_blob_properties()
            except ResourceNotFoundError:
                return [], None, False

            expires_at = int((properties.metadata or {}).get("expires_at", "0"))
            expired = expires_at > 0 and expires_at <= int(time.time())
            if expired:
                return [], properties.etag, True

            try:
                downloader = blob.download_blob(
                    etag=properties.etag,
                    match_condition=MatchConditions.IfNotModified,
                )
                return self._decode_rows(downloader.readall()), properties.etag, False
            except ResourceModifiedError:
                continue
            except ResourceNotFoundError:
                return [], None, False

        raise RuntimeError("Azure Blob conversation changed repeatedly while reading its history.")

    @staticmethod
    def _pause_before_retry(attempt: int) -> None:
        time.sleep(0.01 * (2 ** attempt))

    def get_messages(self, session_id: str) -> list[dict]:
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError

        self._ensure_container()
        blob = self.container_client.get_blob_client(self._blob_name(session_id))
        for attempt in range(MAX_BLOB_WRITE_RETRIES):
            rows, etag, expired = self._read_snapshot(blob)
            if not expired:
                return rows[-self.max_messages:]
            try:
                blob.delete_blob(etag=etag, match_condition=MatchConditions.IfNotModified)
                return []
            except ResourceModifiedError:
                self._pause_before_retry(attempt)
            except ResourceNotFoundError:
                return []
        raise RuntimeError("Azure Blob conversation changed repeatedly while expiring its history.")

    def add_messages(self, session_id: str, messages: Iterable[Any]) -> None:
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError

        additions = serialize_messages(messages)
        if not additions:
            return

        self._ensure_container()
        blob = self.container_client.get_blob_client(self._blob_name(session_id))
        for attempt in range(MAX_BLOB_WRITE_RETRIES):
            rows, etag, _ = self._read_snapshot(blob)
            rows = (rows + additions)[-self.max_messages:]
            payload = json.dumps(rows, default=str).encode("utf-8")
            metadata = {"expires_at": str(int(time.time()) + self.ttl_seconds)}
            try:
                if etag is None:
                    blob.upload_blob(payload, overwrite=False, metadata=metadata)
                else:
                    blob.upload_blob(
                        payload,
                        overwrite=True,
                        etag=etag,
                        match_condition=MatchConditions.IfNotModified,
                        metadata=metadata,
                    )
                return
            except (ResourceExistsError, ResourceModifiedError):
                self._pause_before_retry(attempt)

        raise RuntimeError("Azure Blob conversation was updated too frequently to append messages.")

    def clear(self, session_id: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        self._ensure_container()
        blob = self.container_client.get_blob_client(self._blob_name(session_id))
        try:
            blob.delete_blob()
        except ResourceNotFoundError:
            return

    def list_session_ids(self) -> list[str]:
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError

        self._ensure_container()
        session_ids = []
        for item in self.container_client.list_blobs(name_starts_with=BLOB_PREFIX):
            name = item.name
            if not name.endswith(FILE_SUFFIX):
                continue
            session_id = name[len(BLOB_PREFIX):-len(FILE_SUFFIX)]
            if not session_id or "/" in session_id:
                continue
            blob = self.container_client.get_blob_client(name)
            try:
                properties = blob.get_blob_properties()
            except ResourceNotFoundError:
                continue
            expires_at = int((properties.metadata or {}).get("expires_at", "0"))
            if expires_at > 0 and expires_at <= int(time.time()):
                try:
                    blob.delete_blob(
                        etag=properties.etag,
                        match_condition=MatchConditions.IfNotModified,
                    )
                except ResourceModifiedError:
                    session_ids.append(session_id)
                except ResourceNotFoundError:
                    continue
                continue
            session_ids.append(session_id)
        return sorted(session_ids)

    def close(self) -> None:
        if self.service_client is not None:
            self.service_client.close()
        if self.credential is not None:
            self.credential.close()

    def __repr__(self) -> str:
        endpoint = self.account_url or "Azurite"
        return f"AzureBlobMessageStore({endpoint}/{self.container_name}, ttl={self.ttl_seconds}s)"


def selected_backend() -> str:
    """Backend selected from the optional Blob/Azurite config, Redis URL, or file fallback."""
    blob_url = os.environ.get("MARKETPLACE_BLOB_STORAGE_URL", "")
    azurite_connection_string = os.environ.get("MARKETPLACE_AZURITE_CONNECTION_STRING", "")
    if blob_url and azurite_connection_string:
        raise ValueError(
            "Set either MARKETPLACE_BLOB_STORAGE_URL or "
            "MARKETPLACE_AZURITE_CONNECTION_STRING, not both."
        )
    if blob_url:
        return "azure-blob"
    if azurite_connection_string:
        return "azurite"
    if os.environ.get("MARKETPLACE_REDIS_URL"):
        return "redis"
    return "file"


def get_message_store(default_dir: Path | str) -> MessageStore:
    """Use optional Azure Blob/Azurite, then Redis, and finally JSON files."""
    backend = selected_backend()
    if backend in {"azure-blob", "azurite"}:
        return AzureBlobMessageStore(
            account_url=os.environ.get("MARKETPLACE_BLOB_STORAGE_URL") or None,
            azurite_connection_string=os.environ.get("MARKETPLACE_AZURITE_CONNECTION_STRING") or None,
            container_name=os.environ.get("MARKETPLACE_BLOB_STORAGE_CONTAINER", BLOB_CONTAINER_DEFAULT),
        )
    if backend == "redis":
        return RedisMessageStore(os.environ["MARKETPLACE_REDIS_URL"])
    return FileMessageStore(default_dir)


def describe(store: Any) -> str:
    kind = getattr(store, "kind", type(store).__name__)
    target = (
        getattr(store, "directory", None)
        or getattr(store, "account_url", None)
        or getattr(store, "url", None)
        or getattr(store, "redis_url", "")
    )
    if kind == "azure-blob":
        target = f"{target or 'Azurite'}/{store.container_name}"
    return f"{kind} ({target})"


# ---------------------------------------------------------------------------
# Agent Framework glue: a store becomes a history provider the Agent reads before and writes after a run
# ---------------------------------------------------------------------------
def as_history_provider(store: MessageStore, **kwargs):
    """Wrap a MessageStore as a durable Agent Framework context provider.

    Imported lazily so this module stays importable without agent_framework.
    """
    from agent_framework import ContextProvider

    class StoreHistoryProvider(ContextProvider):
        """Adapter: the synchronous store behind the async provider interface."""

        def __init__(self, inner: MessageStore, source_id: str = "marketplace_history"):
            super().__init__(source_id=source_id)
            self.store = inner

        async def get_messages(self, session_id: str | None, **_) -> list:
            if session_id is None:
                return []
            return deserialize_messages(await asyncio.to_thread(self.store.get_messages, session_id))

        async def save_messages(self, session_id: str | None, messages, **_) -> None:
            if session_id is None:
                return
            await asyncio.to_thread(self.store.add_messages, session_id, messages)

        async def clear(self, session_id: str, **_) -> None:
            await asyncio.to_thread(self.store.clear, session_id)

        async def before_run(self, *, agent, session, context, state) -> None:
            del agent, session
            history = await self.get_messages(context.session_id, state=state)
            context.extend_messages(self, history)

        async def after_run(self, *, agent, session, context, state) -> None:
            del agent, session
            messages = list(context.input_messages)
            if context.response and context.response.messages:
                messages.extend(context.response.messages)
            if messages:
                await self.save_messages(context.session_id, messages, state=state)

        async def aclose(self) -> None:
            close = getattr(self.store, "close", None)
            if callable(close):
                await asyncio.to_thread(close)

        def __repr__(self) -> str:
            return f"StoreHistoryProvider({self.store!r})"

    return StoreHistoryProvider(store, **kwargs)


def build_history_provider(default_dir: Path | str, key_prefix: str = REDIS_KEY_PREFIX):
    """The provider a hosted main.py passes as context_providers=[...].

    Redis: the framework's own RedisHistoryProvider (verified in the base repo notebook threads/2).
    Azure Blob, Azurite, or files use the generic history provider adapter.
    """
    backend = selected_backend()
    if backend == "redis":
        redis_url = os.environ["MARKETPLACE_REDIS_URL"]
        from agent_framework.redis import RedisHistoryProvider

        # VERIFY: key_prefix produces keys "<key_prefix>:<session_id>"; max_messages is shown in the base repo
        # notebook for the older RedisChatMessageStore and may not exist on RedisHistoryProvider.
        return RedisHistoryProvider(redis_url=redis_url, key_prefix=key_prefix)
    return as_history_provider(get_message_store(default_dir))


# ---------------------------------------------------------------------------
# Self-test: file store only, plain dict messages, no packages
# ---------------------------------------------------------------------------
def _selftest() -> int:
    import shutil

    scratch = Path(__file__).resolve().parent / ".message_store_selftest"
    shutil.rmtree(scratch, ignore_errors=True)
    os.environ.pop("MARKETPLACE_REDIS_URL", None)
    os.environ.pop("MARKETPLACE_BLOB_STORAGE_URL", None)
    os.environ.pop("MARKETPLACE_AZURITE_CONNECTION_STRING", None)
    store = get_message_store(scratch)
    failures = []

    def check(name: str, ok: bool) -> None:
        print(f"[message_store] {'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            failures.append(name)

    check("factory picks files when shared-store settings are unset", isinstance(store, FileMessageStore))
    check("FileMessageStore satisfies the MessageStore protocol", isinstance(store, MessageStore))
    check("unknown session has no messages", store.get_messages("nope") == [])

    turn1 = [{"role": "user", "text": "Hi, this is P-1001, ZIP 84095."},
             {"role": "assistant", "text": "Thanks Evelyn. How can I help today?"}]
    turn2 = [{"role": "user", "text": "When can I change my plan?"},
             {"role": "assistant", "text": "Your window is AEP, Oct 15 to Dec 7 [KB-MKT-001]."}]
    store.add_messages("S1-evelyn", turn1)
    store.add_messages("S1-evelyn", turn2)
    rows = store.get_messages("S1-evelyn")
    check("two turns append to four messages", len(rows) == 4)
    check("order is preserved", [message_role(r) for r in rows] == ["user", "assistant", "user", "assistant"])
    check("text survives the round trip", message_text(rows[-1]).startswith("Your window is AEP"))
    check("file name uses the .messages.json suffix", (scratch / "S1-evelyn.messages.json").is_file())
    check("list_session_ids shows the session", store.list_session_ids() == ["S1-evelyn"])

    round_trip = deserialize_messages(serialize_messages(rows))
    check("serialize/deserialize keep the count", len(round_trip) == 4)
    check("serialize/deserialize keep the text", message_text(round_trip[0]) == turn1[0]["text"])

    small = FileMessageStore(scratch / "trim", max_messages=3)
    small.add_messages("s", turn1 + turn2)
    check("max_messages trims the oldest", [message_text(r) for r in small.get_messages("s")] == [message_text(r) for r in (turn1 + turn2)[-3:]])

    store.add_messages("call/2026-10-06 12:00", turn1)
    check("unsafe ids are sanitised for the file name", (scratch / "call_2026-10-06_12_00.messages.json").is_file())

    store.clear("S1-evelyn")
    store.clear("call/2026-10-06 12:00")
    check("clear removes the files", store.get_messages("S1-evelyn") == [] and store.list_session_ids() == [])

    shutil.rmtree(scratch, ignore_errors=True)
    print(f"[message_store] backend for this run: {describe(store)}")
    print(f"[message_store] {'PASS' if not failures else 'FAIL: ' + ', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))    # so `from common.session_store` works when run directly
    raise SystemExit(_selftest())
