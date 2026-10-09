from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "3-day-labs"))
import deployment  # noqa: E402
LAB3_DIR = ROOT / "shared/hosted-knowledge-sessions"
sys.path.insert(0, str(LAB3_DIR))
import lab3_hosted_knowledge  # noqa: E402
from common import message_store


class FakeDownloader:
    def __init__(self, data: bytes):
        self.data = data

    def readall(self) -> bytes:
        return self.data


class FakeBlob:
    def __init__(self, container: "FakeContainer", name: str):
        self.container = container
        self.name = name

    def get_blob_properties(self):
        item = self.container.blobs.get(self.name)
        if item is None:
            raise ResourceNotFoundError("Blob does not exist.")
        return SimpleNamespace(etag=item["etag"], metadata=item["metadata"])

    def download_blob(self, *, etag: str, match_condition):
        item = self.container.blobs.get(self.name)
        if item is None:
            raise ResourceNotFoundError("Blob does not exist.")
        if item["etag"] != etag:
            raise ResourceModifiedError("Blob changed.")
        return FakeDownloader(item["data"])

    def upload_blob(self, data: bytes, *, overwrite: bool, metadata: dict, etag=None, match_condition=None):
        item = self.container.blobs.get(self.name)
        if not overwrite and item is not None:
            raise ResourceExistsError("Blob already exists.")
        if etag is not None:
            if item is None or item["etag"] != etag:
                raise ResourceModifiedError("Blob changed.")
            if self.container.interfere_on_next_upload:
                self.container.interfere_on_next_upload = False
                item["data"] = json.dumps([{"role": "assistant", "text": "concurrent turn"}]).encode()
                item["etag"] = self.container.next_etag()
                raise ResourceModifiedError("A second replica wrote the blob.")
        self.container.blobs[self.name] = {
            "data": data,
            "etag": self.container.next_etag(),
            "metadata": metadata,
        }

    def delete_blob(self, *, etag=None, match_condition=None):
        item = self.container.blobs.get(self.name)
        if item is None:
            raise ResourceNotFoundError("Blob does not exist.")
        if etag is not None and item["etag"] != etag:
            raise ResourceModifiedError("Blob changed.")
        del self.container.blobs[self.name]


class FakeContainer:
    def __init__(self):
        self.blobs: dict[str, dict] = {}
        self.etag = 0
        self.interfere_on_next_upload = False

    def next_etag(self) -> str:
        self.etag += 1
        return str(self.etag)

    def get_container_properties(self):
        return SimpleNamespace()

    def get_blob_client(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)

    def list_blobs(self, *, name_starts_with: str):
        return [SimpleNamespace(name=name) for name in sorted(self.blobs) if name.startswith(name_starts_with)]


class AzureBlobMessageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = FakeContainer()
        self.store = message_store.AzureBlobMessageStore(
            container_name="history",
            container_client=self.container,
            max_messages=3,
            ttl_seconds=7,
        )

    def test_appends_bounds_lists_and_clears_session_history(self) -> None:
        self.store.add_messages("session-1", [
            {"role": "user", "text": "first"},
            {"role": "assistant", "text": "second"},
        ])
        self.store.add_messages("session-1", [{"role": "user", "text": "third"}])

        rows = self.store.get_messages("session-1")
        self.assertEqual([message_store.message_text(row) for row in rows], ["first", "second", "third"])
        self.store.add_messages("session-1", [{"role": "assistant", "text": "fourth"}])
        self.assertEqual(
            [message_store.message_text(row) for row in self.store.get_messages("session-1")],
            ["second", "third", "fourth"],
        )
        self.assertEqual(self.store.list_session_ids(), ["session-1"])

        self.store.clear("session-1")
        self.assertEqual(self.store.get_messages("session-1"), [])
        self.assertEqual(self.store.list_session_ids(), [])

    def test_expires_history_after_ttl(self) -> None:
        with patch.object(message_store.time, "time", return_value=10):
            self.store.add_messages("session-1", [{"role": "user", "text": "old"}])
        with patch.object(message_store.time, "time", return_value=18):
            self.assertEqual(self.store.get_messages("session-1"), [])
            self.assertEqual(self.store.list_session_ids(), [])

    def test_retries_etag_conflict_without_losing_concurrent_history(self) -> None:
        self.store.add_messages("session-1", [{"role": "user", "text": "first"}])
        self.container.interfere_on_next_upload = True

        self.store.add_messages("session-1", [{"role": "user", "text": "second"}])

        self.assertEqual(
            [message_store.message_text(row) for row in self.store.get_messages("session-1")],
            ["concurrent turn", "second"],
        )

    def test_azure_blob_configuration_overrides_local_redis(self) -> None:
        with patch.dict(os.environ, {
            "MARKETPLACE_BLOB_STORAGE_URL": "https://account.blob.core.windows.net",
            "MARKETPLACE_AZURITE_CONNECTION_STRING": "",
            "MARKETPLACE_REDIS_URL": "redis://redis:6379/0",
        }, clear=True):
            self.assertEqual(message_store.selected_backend(), "azure-blob")

    def test_azurite_configuration_is_local_only_backend(self) -> None:
        with patch.dict(os.environ, {
            "MARKETPLACE_BLOB_STORAGE_URL": "",
            "MARKETPLACE_AZURITE_CONNECTION_STRING": "local-emulator-connection-string",
            "MARKETPLACE_REDIS_URL": "redis://redis:6379/0",
        }, clear=True):
            self.assertEqual(message_store.selected_backend(), "azurite")

    def test_conflicting_blob_configurations_are_rejected(self) -> None:
        with patch.dict(os.environ, {
            "MARKETPLACE_BLOB_STORAGE_URL": "https://account.blob.core.windows.net",
            "MARKETPLACE_AZURITE_CONNECTION_STRING": "local-emulator-connection-string",
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "Set either"):
                message_store.selected_backend()

    def test_cloud_deployment_rejects_local_or_http_blob_endpoints(self) -> None:
        for endpoint in (
            "http://azurite:10000/devstoreaccount1",
            "https://localhost",
            "https://user:password@account.blob.core.windows.net",
            "https://account.blob.core.windows.net/container",
            "https://account.blob.core.windows.net/?sig=secret",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                deployment.validate_cloud_settings({"MARKETPLACE_BLOB_STORAGE_URL": endpoint})

    def test_cloud_deployment_accepts_https_blob_account_url(self) -> None:
        deployment.validate_cloud_settings({
            "MARKETPLACE_BLOB_STORAGE_URL": "https://account.blob.core.windows.net",
            "MARKETPLACE_BLOB_STORAGE_CONTAINER": "marketplace-history",
        })

    def test_cloud_deployment_rejects_azurite_connection_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "local-only"):
            deployment.validate_cloud_settings({
                "MARKETPLACE_AZURITE_CONNECTION_STRING": "local-emulator-connection-string",
            })

    def test_deployment_uses_existing_blob_settings_but_not_local_storage(self) -> None:
        settings = lab3_hosted_knowledge.container_environment(
            {"mcp_endpoint": "https://search.blob.core.windows.net/kb/mcp"},
            {
                "MARKETPLACE_BLOB_STORAGE_URL": "https://account.blob.core.windows.net",
                "MARKETPLACE_BLOB_STORAGE_CONTAINER": "history",
                "MARKETPLACE_AZURITE_CONNECTION_STRING": "local-emulator-connection-string",
                "MARKETPLACE_REDIS_URL": "redis://redis:6379/0",
            },
        )
        self.assertEqual(settings["MARKETPLACE_BLOB_STORAGE_URL"], "https://account.blob.core.windows.net")
        self.assertEqual(settings["MARKETPLACE_BLOB_STORAGE_CONTAINER"], "history")
        self.assertNotIn("MARKETPLACE_AZURITE_CONNECTION_STRING", settings)
        self.assertNotIn("MARKETPLACE_REDIS_URL", settings)


class HistoryProviderAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_shares_history_through_current_context_provider_lifecycle(self) -> None:
        from agent_framework import ContextProvider, HistoryProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            first = message_store.as_history_provider(message_store.FileMessageStore(temp_dir))
            second = message_store.as_history_provider(message_store.FileMessageStore(temp_dir))
            self.assertIsInstance(first, ContextProvider)
            self.assertNotIsInstance(first, HistoryProvider)
            self.assertEqual(first.source_id, "marketplace_history")

            first_context = SimpleNamespace(
                session_id="session-1",
                input_messages=[{"role": "user", "text": "hello"}],
                response=SimpleNamespace(messages=[{"role": "assistant", "text": "welcome"}]),
            )
            await first.after_run(agent=None, session=None, context=first_context, state={})

            loaded = []
            second_context = SimpleNamespace(
                session_id="session-1",
                extend_messages=lambda provider, messages: loaded.extend(messages),
            )
            await second.before_run(agent=None, session=None, context=second_context, state={})

        self.assertEqual(
            [message_store.message_text(message) for message in loaded],
            ["hello", "welcome"],
        )


if __name__ == "__main__":
    unittest.main()
