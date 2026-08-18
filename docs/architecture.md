# Architecture

## Runtime flow

```text
User
  |
  | Device-code sign-in
  v
Streamlit application
  |-- Fabric REST discovery: determine accessible configured domains
  |
  |-- Foundry Router Agent (no Fabric tools)
  |      returns route or clarification as JSON
  |
  |-- Authorization intersection
  |      requested domains AND user-accessible domains
  |
  |-- Foundry Domain Agent(s)
         exactly one Fabric IQ tool per agent
             |
             `-- Fabric data agent using delegated user identity
  |
  `-- Foundry Synthesizer Agent
         combines authorized evidence for cross-domain comparisons
```

## Security boundary

The router classifies the question but does not have direct access to domain
data. Before invoking a domain agent, the application verifies that the
signed-in user can see the configured Fabric data-agent item.

Each domain agent contains one Fabric IQ connection configured with
`UserEntraToken`. Foundry forwards delegated identity, and Fabric evaluates the
caller's actual license, workspace role, item access, and underlying-source
permissions.

The application never substitutes an administrative identity for the caller.

## Why not attach every Fabric tool to one agent?

Foundry can enumerate attached MCP tools before the model selects one. If a
caller cannot access one attached server, tool discovery can fail before an
otherwise authorized domain is invoked. Single-domain agents avoid that
failure mode and make the authorization boundary visible.

## Configuration lifecycle

1. `discover_fabric_agents.py` calls Fabric REST APIs and creates an ignored
   local domain catalog.
2. An administrator reviews routing descriptions and instructions.
3. `deploy_agents.py` creates delegated Fabric IQ connections, isolated domain
   agents, and the router agent.
4. The ignored deployment mapping tells the UI which prompt agents to invoke.
