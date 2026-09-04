# Microsoft Teams integration

This guide describes the planned migration from the local Streamlit interface
to a native Microsoft Teams conversational application hosted on Azure App
Service. It is an implementation plan only; the current repository continues
to run Streamlit.

## Target architecture

```text
Teams user
  |
  | Teams SSO token
  v
Microsoft 365 Agents SDK application on Azure App Service
  |
  | On-behalf-of user credential
  v
Application orchestration service
  |-- Foundry router agent
  |-- Foundry domain agent(s) --> Fabric data agents
  `-- Foundry synthesizer agent

App Service managed identity
  |
  `-- Cosmos DB in Microsoft Fabric --> chat history
```

The identity paths must remain separate:

- The Teams user's delegated identity calls Foundry and Fabric. Fabric
  continues to enforce that user's license, workspace role, data-agent access,
  and source permissions.
- The App Service managed identity reads and writes application-owned chat
  history. It must never replace the user identity for business-data queries.

## 1. Extract a UI-independent application service

Move the request-processing block from `app.py` into a reusable service, for
example:

```python
result = orchestration_service.ask(
    user_id=user_object_id,
    conversation_id=teams_conversation_id,
    question=message_text,
    credential=on_behalf_of_credential,
)
```

The service should own history loading, context-window selection, accessible
domain discovery, orchestration, routing-event conversion, and history saving.
Keep `FoundryOrchestrator`, `FabricClient`, and the `ChatStore` implementations
independent of Teams and Streamlit.

Streamlit can call this service during migration. Remove Streamlit only after
the Teams path passes delegated-access testing.

## 2. Create the Teams message endpoint

Add a Python application using the
[Microsoft 365 Agents SDK](https://learn.microsoft.com/microsoft-365/agents-sdk/).
Expose an HTTPS endpoint such as `/api/messages` and configure the Teams bot to
send activities to it.

The message handler should:

1. Validate the incoming activity and tenant.
2. Obtain the signed-in user's Teams SSO token.
3. Build an on-behalf-of credential for Foundry and Fabric.
4. Call the UI-independent orchestration service.
5. Return the answer to the originating Teams conversation.
6. Render routing evidence as concise text or an Adaptive Card without
   exposing prompts, tokens, internal identifiers, or chain-of-thought.

Start with personal chat scope. Add group chat and channel scope only after
defining how shared conversation history and user-specific authorization should
behave.

## 3. Configure Entra ID and Teams SSO

Create an Entra application registration for the Teams application:

1. Expose an API scope for Teams SSO.
2. Preauthorize the Microsoft Teams desktop, web, and mobile clients according
   to the current Teams SSO guidance.
3. Configure the OAuth connection required by the Microsoft 365 Agents SDK.
4. Use a certificate or managed secret reference for the confidential
   on-behalf-of exchange.
5. Request only the delegated scopes required for Foundry and Fabric.

On the server, create `OnBehalfOfCredential` from the validated Teams user
assertion. Pass that credential to `FoundryOrchestrator` and `FabricClient`,
which request their own resource-specific access tokens.

Every Teams user still requires:

- **Foundry User** access to the configured Foundry project.
- A Microsoft Fabric license.
- Access to each selected Fabric data agent and its underlying data sources.
- Required delegated consent for Foundry and Fabric.

See the
[Teams bot SSO overview](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/authentication/bot-sso-overview)
for the current registration and token-exchange steps.

## 4. Use stable Teams and Entra identifiers

Do not use a display name or email address as the durable history key.

- `user_id`: signed-in user's Entra object ID.
- `conversation_id`: a namespaced combination of tenant ID, Teams
  conversation ID, and installation scope.

For group or channel conversations, decide whether history is shared while
authorization remains per user. Never reuse one participant's delegated
credential for another participant.

## 5. Deploy to Azure App Service

Deploy the Teams API as a continuously running web application. Configure:

- HTTPS only.
- A fixed startup command for the selected Python ASGI server.
- Health and readiness endpoints.
- App Service application settings for Foundry, domain, tenant, and storage
  configuration.
- Key Vault references for any confidential client credential.
- System-assigned managed identity.
- Application Insights logging with token and prompt-content scrubbing.

Do not deploy `.env`, `config/*.local.json`, credentials, or local chat data.
Move curated domain configuration to deployment-safe application settings or a
controlled configuration artifact.

## 6. Configure chat history

The recommended hosted setting is:

```dotenv
CHAT_STORAGE_PROVIDER=fabric-cosmos
FABRIC_COSMOS_ENDPOINT=https://YOUR-ENDPOINT.cosmos.fabric.microsoft.com:443/
FABRIC_COSMOS_DATABASE=YOUR-FABRIC-DATABASE-ARTIFACT
FABRIC_COSMOS_CONTAINER=chat-history
```

Before deployment, an administrator must create the Fabric Cosmos DB artifact
and the `chat-history` container with partition key `/user_id`. Grant the App
Service managed identity **Write** permission on that Fabric item. See
[storage.md](storage.md#cosmos-db-in-microsoft-fabric).

## 7. Create the Teams application package

Create a Teams app manifest containing:

- The Entra application ID.
- Bot registration and personal scope.
- The App Service domain in `validDomains`.
- SSO `webApplicationInfo`.
- Color and outline icons.

Upload the package to a development tenant, validate it in personal chat, and
publish it through the organization's Teams admin catalog after review.

## 8. Validate before replacing Streamlit

Test at least these identities:

| User | Expected result |
| --- | --- |
| Access to Sales and IoT | Both domains available; cross-domain synthesis succeeds |
| Sales only | Sales succeeds; IoT is never invoked |
| IoT only | IoT succeeds; Sales is never invoked |
| Neither domain | Both domains denied without leaking data |

Also verify token expiry and refresh, consent failures, tenant restrictions,
conversation isolation, Cosmos history retention/deletion, duplicate Teams
activity handling, and App Service restart behavior.

## Migration sequence

1. Extract the reusable orchestration service.
2. Add the Microsoft 365 Agents SDK adapter.
3. Configure Teams SSO and on-behalf-of authentication.
4. Deploy the API to App Service.
5. Create the Teams app package.
6. Provision and authorize the chosen history store.
7. Run the permission-boundary test matrix.
8. Retire Streamlit after Teams is accepted.
