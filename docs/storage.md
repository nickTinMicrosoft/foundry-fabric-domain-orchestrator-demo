# Chat-history storage

Chat storage is optional and selected with `CHAT_STORAGE_PROVIDER`.

## None

`none` keeps the current conversation only in Streamlit session memory.
Nothing is written by the storage adapter.

## SQLite

```dotenv
CHAT_STORAGE_PROVIDER=sqlite
CHAT_SQLITE_PATH=data/chat_history.db
```

SQLite is suitable for a local single-process demonstration. It is not the
recommended backend for a scaled or multi-instance deployment.

## Azure Cosmos DB

Install optional dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-storage.txt
```

Configure:

```dotenv
CHAT_STORAGE_PROVIDER=cosmos
COSMOS_ENDPOINT=https://YOUR-ACCOUNT.documents.azure.com:443/
COSMOS_KEY=YOUR-KEY
COSMOS_DATABASE=foundry-demo
COSMOS_CONTAINER=chat-history
```

The demo partitions documents by signed-in username. For production, use
managed identity where supported, avoid account keys, and define retention and
deletion policies.

## SQL backends

The same SQLAlchemy adapter supports Azure SQL Database, Fabric SQL Database,
and Azure SQL Managed Instance:

```dotenv
CHAT_STORAGE_PROVIDER=sql
CHAT_SQL_URL=mssql+pyodbc://...
```

Install a supported Microsoft ODBC Driver for SQL Server and provide a valid
SQLAlchemy URL. Prefer passwordless Entra authentication and secret references
over passwords embedded in connection strings.

The adapter creates `orchestrator_chat_history` with a composite key of
`user_id` and `conversation_id`.
