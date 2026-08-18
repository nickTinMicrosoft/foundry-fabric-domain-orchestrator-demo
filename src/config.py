import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DomainConfig:
    key: str
    label: str
    workspace_id: str
    workspace_name: str
    data_agent_id: str
    data_agent_name: str
    description: str
    instructions: str

    @property
    def server_label(self) -> str:
        return f"domain-{self.key}"

    @property
    def server_url(self) -> str:
        return (
            "https://api.fabric.microsoft.com/v1/mcp/workspaces/"
            f"{self.workspace_id}/dataagents/{self.data_agent_id}/agent"
        )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "domain"


def _read_json(local_name: str, sample_name: str) -> dict[str, Any]:
    local_path = ROOT / "config" / local_name
    path = local_path if local_path.exists() else ROOT / "config" / sample_name
    return json.loads(path.read_text(encoding="utf-8"))


def load_demo_config() -> dict[str, Any]:
    return _read_json("demo.local.json", "demo.sample.json")


def load_domains() -> tuple[DomainConfig, ...]:
    payload = _read_json("domains.local.json", "domains.sample.json")
    domains = []
    seen_keys = set()
    for item in payload.get("domains", []):
        domain = DomainConfig(
            key=slugify(item["key"]),
            label=item["label"].strip(),
            workspace_id=item["workspace_id"].strip(),
            workspace_name=item.get("workspace_name", "").strip(),
            data_agent_id=item["data_agent_id"].strip(),
            data_agent_name=item.get("data_agent_name", "").strip(),
            description=item["description"].strip(),
            instructions=item["instructions"].strip(),
        )
        if domain.key in seen_keys:
            raise ValueError(f"Duplicate domain key: {domain.key}")
        seen_keys.add(domain.key)
        domains.append(domain)
    return tuple(domains)


def load_deployment() -> dict[str, Any]:
    path = ROOT / "config" / "deployment.local.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
