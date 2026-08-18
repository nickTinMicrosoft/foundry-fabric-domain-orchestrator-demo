import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from azure.core.credentials import TokenCredential

from src.auth import FABRIC_SCOPE
from src.config import DomainConfig


FABRIC_API = "https://api.fabric.microsoft.com/v1"


@dataclass(frozen=True)
class FabricDataAgent:
    workspace_id: str
    workspace_name: str
    data_agent_id: str
    data_agent_name: str
    description: str


class FabricApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class FabricClient:
    def __init__(self, credential: TokenCredential):
        self._credential = credential

    def _get(self, url: str) -> dict[str, Any]:
        token = self._credential.get_token(FABRIC_SCOPE).token
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise FabricApiError(
                f"Fabric returned HTTP {error.code}: {detail}",
                status_code=error.code,
            ) from error
        except urllib.error.URLError as error:
            raise FabricApiError("Unable to reach the Fabric REST API") from error

    def _list(self, url: str) -> list[dict[str, Any]]:
        values = []
        next_url = url
        while next_url:
            payload = self._get(next_url)
            values.extend(payload.get("value", []))
            continuation = payload.get("continuationToken")
            next_link = payload.get("continuationUri")
            if next_link:
                next_url = next_link
            elif continuation:
                separator = "&" if "?" in url else "?"
                next_url = (
                    f"{url}{separator}continuationToken="
                    f"{urllib.parse.quote(continuation)}"
                )
            else:
                next_url = ""
        return values

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._list(f"{FABRIC_API}/workspaces")

    def list_data_agents(self) -> tuple[FabricDataAgent, ...]:
        agents = []
        for workspace in self.list_workspaces():
            workspace_id = workspace["id"]
            workspace_name = workspace.get("displayName", workspace_id)
            try:
                items = self._list(
                    f"{FABRIC_API}/workspaces/{workspace_id}/dataAgents"
                )
            except FabricApiError:
                items = self._list(
                    f"{FABRIC_API}/workspaces/{workspace_id}/items?type=DataAgent"
                )
            for item in items:
                agents.append(
                    FabricDataAgent(
                        workspace_id=workspace_id,
                        workspace_name=workspace_name,
                        data_agent_id=item["id"],
                        data_agent_name=(
                            item.get("displayName")
                            or item.get("name")
                            or item["id"]
                        ),
                        description=item.get("description", ""),
                    )
                )
        return tuple(agents)

    def can_access_domain(self, domain: DomainConfig) -> bool:
        try:
            item = self._get(
                f"{FABRIC_API}/workspaces/{domain.workspace_id}"
                f"/dataAgents/{domain.data_agent_id}"
            )
            return item.get("id") == domain.data_agent_id
        except FabricApiError as error:
            if error.status_code in (401, 403, 404):
                return False
            raise
