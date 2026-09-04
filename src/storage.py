import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    routing_events: tuple[dict, ...] = ()


class ChatStore(Protocol):
    def list_conversations(self, user_id: str) -> list[str]:
        ...

    def load(self, user_id: str, conversation_id: str) -> list[ChatMessage]:
        ...

    def save(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ChatMessage],
    ) -> None:
        ...


class NullChatStore:
    def list_conversations(self, user_id: str) -> list[str]:
        return []

    def load(self, user_id: str, conversation_id: str) -> list[ChatMessage]:
        return []

    def save(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ChatMessage],
    ) -> None:
        return None


class SqliteChatStore:
    def __init__(self, path: str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, conversation_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_conversations(self, user_id: str) -> list[str]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def load(self, user_id: str, conversation_id: str) -> list[ChatMessage]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT messages_json FROM conversations
                WHERE user_id = ? AND conversation_id = ?
                """,
                (user_id, conversation_id),
            ).fetchone()
        if not row:
            return []
        return [
            ChatMessage(
                role=item["role"],
                content=item["content"],
                routing_events=tuple(item.get("routing_events", [])),
            )
            for item in json.loads(row[0])
        ]

    def save(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ChatMessage],
    ) -> None:
        payload = json.dumps([asdict(message) for message in messages])
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    user_id, conversation_id, messages_json, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, conversation_id) DO UPDATE SET
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    conversation_id,
                    payload,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


class CosmosChatStore:
    def __init__(
        self,
        endpoint: str,
        key: str | None,
        database_name: str,
        container_name: str,
        create_resources: bool = True,
    ):
        try:
            from azure.cosmos import CosmosClient, PartitionKey
        except ImportError as error:
            raise RuntimeError(
                "Install requirements-storage.txt for Cosmos DB support"
            ) from error
        if key:
            credential = key
        else:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
        client_options = (
            {"connection_mode": "Gateway"} if not create_resources else {}
        )
        client = CosmosClient(
            endpoint,
            credential=credential,
            **client_options,
        )
        if create_resources:
            database = client.create_database_if_not_exists(database_name)
            self._container = database.create_container_if_not_exists(
                id=container_name,
                partition_key=PartitionKey(path="/user_id"),
            )
        else:
            database = client.get_database_client(database_name)
            self._container = database.get_container_client(container_name)

    def list_conversations(self, user_id: str) -> list[str]:
        items = self._container.query_items(
            query=(
                "SELECT c.id FROM c WHERE c.user_id = @user_id "
                "ORDER BY c.updated_at DESC"
            ),
            parameters=[{"name": "@user_id", "value": user_id}],
            partition_key=user_id,
        )
        return [item["id"] for item in items]

    def load(self, user_id: str, conversation_id: str) -> list[ChatMessage]:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            item = self._container.read_item(
                item=conversation_id,
                partition_key=user_id,
            )
        except CosmosResourceNotFoundError:
            return []
        return [
            ChatMessage(
                role=value["role"],
                content=value["content"],
                routing_events=tuple(value.get("routing_events", [])),
            )
            for value in item.get("messages", [])
        ]

    def save(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ChatMessage],
    ) -> None:
        self._container.upsert_item(
            {
                "id": conversation_id,
                "user_id": user_id,
                "messages": [asdict(message) for message in messages],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )


class FabricCosmosChatStore(CosmosChatStore):
    def __init__(
        self,
        endpoint: str,
        database_name: str,
        container_name: str,
    ):
        super().__init__(
            endpoint=endpoint,
            key=None,
            database_name=database_name,
            container_name=container_name,
            create_resources=False,
        )


class SqlAlchemyChatStore:
    def __init__(self, url: str):
        try:
            from sqlalchemy import (
                Column,
                DateTime,
                MetaData,
                String,
                Table,
                Text,
                create_engine,
            )
        except ImportError as error:
            raise RuntimeError(
                "Install requirements-storage.txt for SQL support"
            ) from error
        self._engine = create_engine(url)
        self._metadata = MetaData()
        self._table = Table(
            "orchestrator_chat_history",
            self._metadata,
            Column("user_id", String(320), primary_key=True),
            Column("conversation_id", String(64), primary_key=True),
            Column("messages_json", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self._metadata.create_all(self._engine)

    def close(self) -> None:
        self._engine.dispose()

    def list_conversations(self, user_id: str) -> list[str]:
        from sqlalchemy import select

        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._table.c.conversation_id)
                .where(self._table.c.user_id == user_id)
                .order_by(self._table.c.updated_at.desc())
            ).all()
        return [row[0] for row in rows]

    def load(self, user_id: str, conversation_id: str) -> list[ChatMessage]:
        from sqlalchemy import select

        with self._engine.connect() as connection:
            row = connection.execute(
                select(self._table.c.messages_json).where(
                    self._table.c.user_id == user_id,
                    self._table.c.conversation_id == conversation_id,
                )
            ).first()
        if not row:
            return []
        return [
            ChatMessage(
                role=item["role"],
                content=item["content"],
                routing_events=tuple(item.get("routing_events", [])),
            )
            for item in json.loads(row[0])
        ]

    def save(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ChatMessage],
    ) -> None:
        from sqlalchemy import delete, insert

        values = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages_json": json.dumps(
                [asdict(message) for message in messages]
            ),
            "updated_at": datetime.now(timezone.utc),
        }
        with self._engine.begin() as connection:
            connection.execute(
                delete(self._table).where(
                    self._table.c.user_id == user_id,
                    self._table.c.conversation_id == conversation_id,
                )
            )
            connection.execute(insert(self._table).values(**values))


def create_chat_store() -> ChatStore:
    provider = os.getenv("CHAT_STORAGE_PROVIDER", "none").casefold()
    if provider == "none":
        return NullChatStore()
    if provider == "sqlite":
        return SqliteChatStore(
            os.getenv("CHAT_SQLITE_PATH", "data/chat_history.db")
        )
    if provider == "cosmos":
        return CosmosChatStore(
            endpoint=os.environ["COSMOS_ENDPOINT"],
            key=os.getenv("COSMOS_KEY"),
            database_name=os.getenv("COSMOS_DATABASE", "foundry-demo"),
            container_name=os.getenv("COSMOS_CONTAINER", "chat-history"),
        )
    if provider == "fabric-cosmos":
        return FabricCosmosChatStore(
            endpoint=os.environ["FABRIC_COSMOS_ENDPOINT"],
            database_name=os.environ["FABRIC_COSMOS_DATABASE"],
            container_name=os.environ["FABRIC_COSMOS_CONTAINER"],
        )
    if provider == "sql":
        return SqlAlchemyChatStore(os.environ["CHAT_SQL_URL"])
    raise ValueError(f"Unsupported CHAT_STORAGE_PROVIDER: {provider}")


def new_conversation_id() -> str:
    return uuid4().hex
