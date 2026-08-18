# Foundry + Fabric Domain Orchestrator Demo

> [!CAUTION]
> **DEMONSTRATION AND EXAMPLE SOFTWARE ONLY - NOT FOR PRODUCTION USE.**
> This repository intentionally favors an understandable demonstration over a
> production security, reliability, observability, deployment, and compliance
> posture. Review the limitations in [SECURITY.md](SECURITY.md) before use.

A configurable Streamlit demonstration showing how a Microsoft Foundry router
can select among independently governed Microsoft Fabric data agents while
Fabric evaluates the signed-in user's delegated permissions.

## What the demo shows

- A single **Sign in** button authenticates any user in the configured tenant.
- Fabric REST APIs discover data agents visible to the configuring user.
- A Foundry router chooses the relevant business domain.
- Each Fabric data agent is isolated behind its own single-tool Foundry agent.
- The application prevents inaccessible domains from being invoked.
- Routing evidence shows domain selection without exposing private
  chain-of-thought.
- Branding and sample prompts are configuration-driven.
- Chat history can remain ephemeral or persist to SQLite, Azure Cosmos DB,
  Azure SQL Database, Fabric SQL Database, or Azure SQL Managed Instance.

## Why the agents are isolated

Attaching every Fabric MCP endpoint directly to one prompt agent can fail for
partially authorized users because Foundry may enumerate all tools before
routing. This project uses:

1. A **router agent** with no Fabric tools.
2. One **domain agent per Fabric data agent**, containing exactly one Fabric
   IQ tool.
3. A **synthesizer agent** that compares authorized multi-domain evidence.
4. Application-side authorization validation before invoking a selected domain.

The router still makes the domain decision in Foundry. Fabric remains the
authority for downstream data access.

See [docs/architecture.md](docs/architecture.md) for the full flow.

## Prerequisites

- Python 3.11 or 3.12.
- Azure CLI authenticated to the tenant that owns the Foundry project.
- A Microsoft Foundry project and deployed model.
- **Foundry User** access for every demo user.
- Microsoft Fabric licensing for every demo user.
- One or more published Fabric data agents.
- Read access to each data agent and every underlying Fabric source.
- Fabric delegated consent required by Fabric IQ, including
  `DataAgent.Execute.All` where applicable.

## Quick start

### 1. Clone and create the environment

```powershell
git clone https://github.com/nickTinMicrosoft/foundry-fabric-domain-orchestrator-demo.git
Set-Location foundry-fabric-domain-orchestrator-demo
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env_sample .env
```

On macOS or Linux, activate the virtual environment using the equivalent shell
commands and run `python` instead of the Windows executable path.

### 2. Configure `.env`

Fill in:

- `FOUNDRY_PROJECT_ENDPOINT`
- `FOUNDRY_MODEL_NAME`
- `FOUNDRY_AGENT_NAME_PREFIX`
- Azure subscription, resource group, account, and project identifiers
- `DEMO_TENANT_ID`

The `.env` file and every `.env.*` variant are ignored. Only `.env_sample` is
tracked. Never place secrets or tenant-specific values in tracked files.

### 3. Discover Fabric data agents

```powershell
.\.venv\Scripts\python.exe scripts\discover_fabric_agents.py
```

Complete device-code authentication. The script lists data agents visible to
that identity and writes `config/domains.local.json`, which is ignored by Git.

Review each generated domain:

- Give it a concise routing `description`.
- Add domain-specific `instructions`.
- Remove agents that should not participate in the demo.
- Keep each `key` unique.

### 4. Deploy the Foundry agents

Authenticate the Azure CLI as a user allowed to create Foundry prompt-agent
versions:

```powershell
az login
.\.venv\Scripts\python.exe scripts\deploy_agents.py
```

The deployment creates:

- One router prompt agent.
- One prompt agent per configured Fabric data agent.
- One tool-free synthesizer prompt agent for cross-domain answers.
- One delegated `UserEntraToken` Fabric IQ connection per domain.
- `config/deployment.local.json`, containing the deployed agent-name mapping.

### 5. Run the demo

```powershell
.\start-demo.ps1
```

Open the Streamlit URL, select **Sign in**, authenticate, and ask a question.

## Configure the demo controls

Copy `config/demo.sample.json` to `config/demo.local.json`. Change:

- Application title and subtitle.
- Production warning.
- Sample prompt buttons.
- Number of prior messages supplied as conversation context.
- Whether routing evidence is displayed.

The local configuration is ignored by Git.

## Chat-history storage

The default is `CHAT_STORAGE_PROVIDER=none`.

| Provider | Configuration |
| --- | --- |
| SQLite | `CHAT_STORAGE_PROVIDER=sqlite` and `CHAT_SQLITE_PATH` |
| Azure Cosmos DB | Install `requirements-storage.txt`; set `COSMOS_*` |
| Azure SQL Database | Install storage requirements; set `CHAT_SQL_URL` |
| Fabric SQL Database | Install storage requirements; set `CHAT_SQL_URL` |
| Azure SQL Managed Instance | Install storage requirements; set `CHAT_SQL_URL` |

SQL backends use a SQLAlchemy URL and the installed ODBC driver. See
[docs/storage.md](docs/storage.md).

## Repository structure

```text
app.py                         Streamlit UI
src/auth.py                    Generic delegated device-code authentication
src/fabric.py                  Fabric workspace and data-agent discovery
src/orchestrator.py            Foundry router and isolated domain invocation
src/storage.py                 Pluggable chat-history providers
scripts/discover_fabric_agents.py
scripts/deploy_agents.py
config/*.sample.json           Shareable configuration templates
docs/                          Architecture, setup, and storage guidance
```

## Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
