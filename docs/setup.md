# Detailed setup notes

## Foundry access

End users require **Foundry User** at the project scope. The configuring
administrator also needs permission to create prompt-agent versions and
project connections.

## Fabric access

Each end user requires:

- A Fabric license.
- Access to the published Fabric data agent.
- Access to every underlying data source used by that agent.
- Required delegated OAuth consent.

The discovery script only includes agents visible to the configuring identity.
That does not grant those agents to other users.

## Routing descriptions

Domain descriptions are part of the router's decision boundary. Write them in
business language and clearly distinguish overlapping terms. For example,
separate commercial product performance from deployed-equipment operational
health.

## Redeployment

Run `scripts/deploy_agents.py` after changing domain membership, descriptions,
instructions, model deployment, or agent-name prefix. Foundry creates new
immutable prompt-agent versions and updates the ignored local deployment map.
