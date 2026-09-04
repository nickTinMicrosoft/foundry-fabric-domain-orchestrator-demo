import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.storage import (
    ChatMessage,
    CosmosChatStore,
    FabricCosmosChatStore,
    SqlAlchemyChatStore,
    SqliteChatStore,
    create_chat_store,
)


class SqliteChatStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteChatStore(str(Path(directory) / "chat.db"))
            messages = [
                ChatMessage(role="user", content="Hello"),
                ChatMessage(
                    role="assistant",
                    content="Hi",
                    routing_events=(
                        {
                            "domain": "Example",
                            "status": "completed",
                            "outcome": "Done",
                        },
                    ),
                ),
            ]
            store.save("user@example.com", "conversation", messages)
            loaded = store.load("user@example.com", "conversation")
            self.assertEqual(messages, loaded)
            self.assertEqual(
                ["conversation"],
                store.list_conversations("user@example.com"),
            )


class SqlAlchemyChatStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "chat.db"
            store = SqlAlchemyChatStore(f"sqlite:///{database_path}")
            messages = [ChatMessage(role="user", content="Persist me")]
            store.save("user@example.com", "conversation", messages)
            self.assertEqual(
                messages,
                store.load("user@example.com", "conversation"),
            )
            self.assertEqual(
                ["conversation"],
                store.list_conversations("user@example.com"),
            )
            store.close()


class ChatStoreFactoryTests(unittest.TestCase):
    @patch("src.storage.CosmosChatStore")
    def test_cosmos_uses_default_credential_when_key_is_unset(
        self,
        cosmos_store,
    ):
        environment = {
            "CHAT_STORAGE_PROVIDER": "cosmos",
            "COSMOS_ENDPOINT": "https://example.documents.azure.com:443/",
            "COSMOS_DATABASE": "foundry-demo",
            "COSMOS_CONTAINER": "chat-history",
        }
        with patch.dict("os.environ", environment, clear=True):
            create_chat_store()
        cosmos_store.assert_called_once_with(
            endpoint=environment["COSMOS_ENDPOINT"],
            key=None,
            database_name=environment["COSMOS_DATABASE"],
            container_name=environment["COSMOS_CONTAINER"],
        )

    @patch("src.storage.FabricCosmosChatStore")
    def test_fabric_cosmos_uses_existing_resources(self, fabric_store):
        environment = {
            "CHAT_STORAGE_PROVIDER": "fabric-cosmos",
            "FABRIC_COSMOS_ENDPOINT": (
                "https://example.cosmos.fabric.microsoft.com:443/"
            ),
            "FABRIC_COSMOS_DATABASE": "orchestrator-history",
            "FABRIC_COSMOS_CONTAINER": "chat-history",
        }
        with patch.dict("os.environ", environment, clear=True):
            create_chat_store()
        fabric_store.assert_called_once_with(
            endpoint=environment["FABRIC_COSMOS_ENDPOINT"],
            database_name=environment["FABRIC_COSMOS_DATABASE"],
            container_name=environment["FABRIC_COSMOS_CONTAINER"],
        )

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.cosmos.CosmosClient")
    def test_fabric_cosmos_does_not_create_resources(
        self,
        cosmos_client,
        default_credential,
    ):
        database = cosmos_client.return_value.get_database_client.return_value
        FabricCosmosChatStore(
            endpoint="https://example.cosmos.fabric.microsoft.com:443/",
            database_name="orchestrator-history",
            container_name="chat-history",
        )
        cosmos_client.return_value.create_database_if_not_exists.assert_not_called()
        database.create_container_if_not_exists.assert_not_called()
        database.get_container_client.assert_called_once_with("chat-history")
        cosmos_client.assert_called_once_with(
            "https://example.cosmos.fabric.microsoft.com:443/",
            credential=default_credential.return_value,
            connection_mode="Gateway",
        )
        default_credential.assert_called_once_with(
            exclude_interactive_browser_credential=True
        )


if __name__ == "__main__":
    unittest.main()
