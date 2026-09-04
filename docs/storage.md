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
COSMOS_KEY=
COSMOS_DATABASE=foundry-demo
COSMOS_CONTAINER=chat-history
```

When `COSMOS_KEY` is blank, the demo uses `DefaultAzureCredential`. Assign the
runtime identity the Cosmos DB Built-in Data Contributor role. For local
development, an authenticated Azure CLI identity is supported by the default
credential chain. Set `AZURE_TOKEN_CREDENTIALS=AzureCliCredential` to use only
Azure CLI authentication locally. Account keys remain supported when
explicitly configured.

The demo partitions documents by signed-in username. For production, use
managed identity, avoid account keys, and define retention and deletion
policies.

## Cosmos DB in Microsoft Fabric

Use `fabric-cosmos` to connect to a Cosmos DB database artifact that an
administrator has already created in Microsoft Fabric:

```dotenv
CHAT_STORAGE_PROVIDER=fabric-cosmos
FABRIC_COSMOS_ENDPOINT=https://YOUR-ENDPOINT.cosmos.fabric.microsoft.com:443/
FABRIC_COSMOS_DATABASE=YOUR-FABRIC-DATABASE-ARTIFACT
FABRIC_COSMOS_CONTAINER=chat-history
```

Install `requirements-storage.txt`, which requires `azure-cosmos` 4.14 or
later. Copy the **Endpoint for Cosmos DB NoSQL database** from the Fabric
database's **Settings > Connection** page.

This provider intentionally does not create a database or container. Before
enabling it, create the Fabric Cosmos DB database and a container named by
`FABRIC_COSMOS_CONTAINER` with partition key `/user_id`. The provider uses the
same `list`, `load`, and `save` behavior as Azure Cosmos DB.

Cosmos DB in Fabric supports Microsoft Entra authentication only. For an App
Service deployment, grant the App Service managed identity **Write** permission
on the Fabric Cosmos DB item, and ensure the Fabric tenant permits service
principals to use Fabric APIs. `DefaultAzureCredential` then uses that managed
identity. The provider explicitly uses the only supported connection mode,
**Gateway**. For local development, sign in with Azure CLI and optionally set:

```dotenv
AZURE_TOKEN_CREDENTIALS=AzureCliCredential
```

The storage identity is separate from the delegated Teams or Streamlit user
identity used for Foundry and Fabric data-agent queries. Users should not need
direct access to the history database merely to use the application.

Review the workspace boundary carefully: Microsoft currently documents that
Fabric item permissions for Cosmos DB apply to all Cosmos DB artifacts in the
workspace. Use a dedicated workspace when that access scope is too broad.

Microsoft references:

- [Cosmos DB in Microsoft Fabric overview](https://learn.microsoft.com/fabric/database/cosmos-db/overview)
- [Authenticate from Azure services](https://learn.microsoft.com/fabric/database/cosmos-db/how-to-authenticate)
- [Authorization and Fabric item permissions](https://learn.microsoft.com/fabric/database/cosmos-db/authorization)

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
