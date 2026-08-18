import argparse
import json
import sys
from pathlib import Path

from azure.identity import DeviceCodeCredential
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.auth import FABRIC_SCOPE
from src.config import slugify
from src.fabric import FabricClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover Fabric data agents visible to the signed-in user."
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "config" / "domains.local.json"),
    )
    arguments = parser.parse_args()
    load_dotenv(ROOT / ".env")

    tenant_id = __import__("os").environ["DEMO_TENANT_ID"]
    credential = DeviceCodeCredential(tenant_id=tenant_id)
    credential.get_token(FABRIC_SCOPE)
    agents = FabricClient(credential).list_data_agents()
    if not agents:
        raise RuntimeError(
            "No Fabric data agents were visible to the signed-in user."
        )

    domains = []
    used_keys = set()
    for agent in agents:
        base_key = slugify(agent.data_agent_name)
        key = base_key
        suffix = 2
        while key in used_keys:
            key = f"{base_key}-{suffix}"
            suffix += 1
        used_keys.add(key)
        domains.append(
            {
                "key": key,
                "label": agent.data_agent_name,
                "workspace_id": agent.workspace_id,
                "workspace_name": agent.workspace_name,
                "data_agent_id": agent.data_agent_id,
                "data_agent_name": agent.data_agent_name,
                "description": (
                    agent.description
                    or "Describe the questions that belong to this domain."
                ),
                "instructions": (
                    "Use the Fabric data agent for every domain-data question. "
                    "Preserve units and time periods. Never invent unavailable "
                    "data."
                ),
            }
        )

    output_path = Path(arguments.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"domains": domains}, indent=2),
        encoding="utf-8",
    )
    print(f"Discovered {len(domains)} data agent(s).")
    print(f"Wrote local configuration to {output_path}")
    print("Review domain descriptions and instructions before deployment.")
    credential.close()


if __name__ == "__main__":
    main()
