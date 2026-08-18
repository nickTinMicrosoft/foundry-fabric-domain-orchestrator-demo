import tempfile
import unittest
from pathlib import Path

from src.storage import ChatMessage, SqlAlchemyChatStore, SqliteChatStore


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


if __name__ == "__main__":
    unittest.main()
