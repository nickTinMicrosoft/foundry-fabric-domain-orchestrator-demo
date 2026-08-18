import json
import re
from dataclasses import dataclass
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.core.credentials import TokenCredential

from src.config import DomainConfig


@dataclass(frozen=True)
class RoutingEvent:
    domain: str
    status: str
    outcome: str


@dataclass(frozen=True)
class OrchestratorResult:
    answer: str
    routing_events: tuple[RoutingEvent, ...]


def parse_route(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        object_match = re.search(r"\{.*\}", text, re.DOTALL)
        if object_match:
            text = object_match.group(0)
    payload = json.loads(text)
    action = payload.get("action")
    if action not in {"route", "clarify"}:
        raise ValueError("Router returned an unsupported action")
    domains = payload.get("domains", [])
    if not isinstance(domains, list):
        raise ValueError("Router domains must be a list")
    return {
        "action": action,
        "domains": [str(value) for value in domains],
        "clarification": str(payload.get("clarification") or ""),
    }


class FoundryOrchestrator:
    def __init__(
        self,
        endpoint: str,
        router_agent_name: str,
        synthesizer_agent_name: str,
        domain_agent_names: dict[str, str],
        credential: TokenCredential,
    ):
        self._endpoint = endpoint
        self._router_agent_name = router_agent_name
        self._synthesizer_agent_name = synthesizer_agent_name
        self._domain_agent_names = domain_agent_names
        self._credential = credential

    def _invoke(self, agent_name: str, prompt: str):
        with (
            AIProjectClient(
                endpoint=self._endpoint,
                credential=self._credential,
            ) as project_client,
            project_client.get_openai_client() as openai_client,
        ):
            return openai_client.responses.create(
                input=prompt,
                extra_body={
                    "agent_reference": {
                        "name": agent_name,
                        "type": "agent_reference",
                    }
                },
            )

    def ask(
        self,
        question: str,
        domains: tuple[DomainConfig, ...],
        accessible_domain_keys: set[str],
        history: list[dict[str, str]],
    ) -> OrchestratorResult:
        recent_history = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in history
        )
        router_prompt = (
            "Recent conversation:\n"
            f"{recent_history or '(none)'}\n\n"
            f"Current question:\n{question}"
        )
        route_response = self._invoke(self._router_agent_name, router_prompt)
        route = parse_route(route_response.output_text)
        if route["action"] == "clarify":
            return OrchestratorResult(
                answer=route["clarification"],
                routing_events=(
                    RoutingEvent(
                        domain="Router",
                        status="clarification",
                        outcome="No Fabric domain invoked",
                    ),
                ),
            )

        configured = {domain.key: domain for domain in domains}
        requested = [
            key for key in route["domains"] if key in configured
        ]
        if not requested:
            return OrchestratorResult(
                answer=(
                    "The router did not identify a configured domain. "
                    "Please clarify the business area for the question."
                ),
                routing_events=(
                    RoutingEvent(
                        domain="Router",
                        status="unresolved",
                        outcome="No configured domain selected",
                    ),
                ),
            )

        evidence = []
        denied_sections = []
        events = []
        for key in requested:
            domain = configured[key]
            if key not in accessible_domain_keys:
                denied_sections.append(
                    f"**{domain.label}:** The signed-in user does not have "
                    "access to this Fabric data agent."
                )
                events.append(
                    RoutingEvent(
                        domain=domain.label,
                        status="denied",
                        outcome="Not accessible to signed-in user",
                    )
                )
                continue
            response = self._invoke(
                self._domain_agent_names[key],
                (
                    f"Conversation context:\n{recent_history or '(none)'}\n\n"
                    f"Question:\n{question}"
                ),
            )
            evidence.append((domain.label, response.output_text))
            events.append(
                RoutingEvent(
                    domain=domain.label,
                    status="completed",
                    outcome="Fabric domain response completed",
                )
            )
        if len(evidence) > 1:
            evidence_text = "\n\n".join(
                f"## {label}\n{output}" for label, output in evidence
            )
            synthesis = self._invoke(
                self._synthesizer_agent_name,
                (
                    f"User question:\n{question}\n\n"
                    f"Authorized domain evidence:\n{evidence_text}"
                ),
            )
            answer_sections = [synthesis.output_text]
        else:
            answer_sections = [
                f"### {label}\n\n{output}" for label, output in evidence
            ]
        answer_sections.extend(denied_sections)
        return OrchestratorResult(
            answer="\n\n".join(answer_sections),
            routing_events=tuple(events),
        )
