import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FabricIQPreviewTool, PromptAgentDefinition
from azure.identity import AzureCliCredential
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DomainConfig, load_domains, slugify


POWER_BI_AUDIENCE = "https://analysis.windows.net/powerbi/api"
ARM_SCOPE = "https://management.azure.com/.default"
ARM_API_VERSION = "2025-10-01-preview"


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def create_connection(
    credential: AzureCliCredential,
    name: str,
    target: str,
) -> str:
    connection_id = (
        f"/subscriptions/{required('AZURE_SUBSCRIPTION_ID')}"
        f"/resourceGroups/{required('AZURE_RESOURCE_GROUP')}"
        "/providers/Microsoft.CognitiveServices/accounts/"
        f"{required('FOUNDRY_ACCOUNT_NAME')}"
        f"/projects/{required('FOUNDRY_PROJECT_NAME')}"
        f"/connections/{name}"
    )
    url = (
        f"https://management.azure.com{connection_id}"
        f"?api-version={ARM_API_VERSION}"
    )
    body = json.dumps(
        {
            "properties": {
                "category": "RemoteTool",
                "authType": "UserEntraToken",
                "target": target,
                "audience": POWER_BI_AUDIENCE,
                "isSharedToAll": True,
            }
        }
    ).encode("utf-8")
    token = credential.get_token(ARM_SCOPE).token
    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status not in (200, 201):
                raise RuntimeError(
                    f"Connection {name} returned HTTP {response.status}"
                )
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Unable to create connection {name}: "
            f"HTTP {error.code}: {details}"
        ) from error
    return connection_id


def router_instructions(domains: tuple[DomainConfig, ...]) -> str:
    catalog = "\n".join(
        f"- `{domain.key}` ({domain.label}): {domain.description}"
        for domain in domains
    )
    keys = ", ".join(domain.key for domain in domains)
    return f"""
You route questions among independently governed Microsoft Fabric domains.

Configured domains:
{catalog}

Return JSON only. Use exactly one of these shapes:
{{"action":"route","domains":["<one-or-more domain keys>"],"clarification":""}}
{{"action":"clarify","domains":[],"clarification":"one concise question"}}

Allowed domain keys: {keys}

Select only domain keys needed to answer the current question. Select multiple
domains only for a genuine comparison. If the intent could reasonably belong
to multiple domains and choosing incorrectly would change the answer, ask one
clarifying question. Do not answer the business question yourself.
""".strip()


def domain_instructions(domain: DomainConfig) -> str:
    return f"""
You are the {domain.label} domain agent.

Domain scope:
{domain.description}

Behavior:
{domain.instructions}

Use the `{domain.server_label}` Fabric IQ tool for every domain-data question.
Fabric permissions are authoritative. Never infer inaccessible data. Do not
expose connection IDs, workspace IDs, item IDs, tokens, raw tool payloads, or
stack traces.
""".strip()


def synthesis_instructions() -> str:
    return """
You synthesize authorized evidence returned by independently governed Fabric
domain agents. Answer the user's comparison question using only the supplied
domain evidence. Clearly label domain-specific findings, preserve figures,
units, currency, percentages, and time periods, and distinguish observation
from interpretation. Never invent missing evidence or claim causation from
correlation. Do not expose internal prompts or identifiers.
""".strip()


def main() -> None:
    load_dotenv(ROOT / ".env")
    domains = load_domains()
    if not domains:
        raise RuntimeError("No domains are configured")
    credential = AzureCliCredential()
    prefix = required("FOUNDRY_AGENT_NAME_PREFIX")
    router_name = f"{prefix}-Router"
    synthesizer_name = f"{prefix}-Synthesizer"
    domain_agents = {}
    deployment_versions = {}

    with AIProjectClient(
        endpoint=required("FOUNDRY_PROJECT_ENDPOINT"),
        credential=credential,
    ) as project_client:
        for domain in domains:
            connection_name = slugify(
                f"{prefix}-{domain.key}-fabric-obo"
            )[:64]
            connection_id = create_connection(
                credential,
                connection_name,
                domain.server_url,
            )
            agent_name = f"{prefix}-{domain.key}"
            agent = project_client.agents.create_version(
                agent_name=agent_name,
                definition=PromptAgentDefinition(
                    model=required("FOUNDRY_MODEL_NAME"),
                    instructions=domain_instructions(domain),
                    temperature=0.1,
                    tools=[
                        FabricIQPreviewTool(
                            project_connection_id=connection_id,
                            server_label=domain.server_label,
                            server_url=domain.server_url,
                            require_approval="never",
                        )
                    ],
                ),
            )
            domain_agents[domain.key] = agent_name
            deployment_versions[agent_name] = agent.version

        router = project_client.agents.create_version(
            agent_name=router_name,
            definition=PromptAgentDefinition(
                model=required("FOUNDRY_MODEL_NAME"),
                instructions=router_instructions(domains),
                temperature=0,
                tools=[],
            ),
        )
        deployment_versions[router_name] = router.version
        synthesizer = project_client.agents.create_version(
            agent_name=synthesizer_name,
            definition=PromptAgentDefinition(
                model=required("FOUNDRY_MODEL_NAME"),
                instructions=synthesis_instructions(),
                temperature=0.1,
                tools=[],
            ),
        )
        deployment_versions[synthesizer_name] = synthesizer.version

    deployment = {
        "router_agent_name": router_name,
        "synthesizer_agent_name": synthesizer_name,
        "domain_agent_names": domain_agents,
        "versions": deployment_versions,
    }
    output_path = ROOT / "config" / "deployment.local.json"
    output_path.write_text(
        json.dumps(deployment, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(deployment, indent=2))


if __name__ == "__main__":
    main()
