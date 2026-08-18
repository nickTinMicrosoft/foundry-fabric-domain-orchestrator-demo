import os

import streamlit as st
from azure.core.exceptions import ClientAuthenticationError
from dotenv import load_dotenv
from openai import APIStatusError

from src.auth import AuthenticatedUser, authenticate_user
from src.config import load_demo_config, load_deployment, load_domains
from src.fabric import FabricApiError, FabricClient
from src.orchestrator import FoundryOrchestrator
from src.storage import ChatMessage, create_chat_store, new_conversation_id


load_dotenv()
demo = load_demo_config()
domains = load_domains()
deployment = load_deployment()

st.set_page_config(
    page_title=demo["app_title"],
    page_icon="S",
    layout="wide",
)


@st.cache_resource
def chat_store():
    return create_chat_store()


def device_prompt(verification_uri: str, user_code: str, _: object) -> None:
    st.info(f"Open {verification_uri} and enter `{user_code}`.")


def routing_evidence(events: list[dict]) -> None:
    if not demo.get("show_routing_evidence", True):
        return
    with st.expander("Orchestrator execution evidence", expanded=True):
        st.caption(
            "Observable routing outcomes, not private model chain-of-thought."
        )
        for event in events:
            st.markdown(
                f"**{event['domain']}** - {event['status']}: "
                f"{event['outcome']}"
            )


if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = new_conversation_id()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "accessible_domain_keys" not in st.session_state:
    st.session_state.accessible_domain_keys = None

authenticated_user: AuthenticatedUser | None = (
    st.session_state.authenticated_user
)
store = chat_store()

st.title(demo["app_title"])
st.caption(demo["app_subtitle"])
st.error(demo["production_warning"])

with st.sidebar:
    st.header("Identity")
    if not authenticated_user:
        if st.button("Sign in", type="primary", use_container_width=True):
            try:
                authenticated_user = authenticate_user(
                    os.environ["DEMO_TENANT_ID"],
                    device_prompt,
                )
                st.session_state.authenticated_user = authenticated_user
                st.session_state.accessible_domain_keys = None
                st.rerun()
            except ClientAuthenticationError as error:
                st.error(f"Authentication failed: {error.message}")
    else:
        st.success(f"Signed in as {authenticated_user.username}")
        saved_conversations = store.list_conversations(
            authenticated_user.username
        )
        conversation_options = [st.session_state.conversation_id] + [
            conversation_id
            for conversation_id in saved_conversations
            if conversation_id != st.session_state.conversation_id
        ]
        selected_conversation = st.selectbox(
            "Conversation",
            options=conversation_options,
            format_func=lambda value: (
                f"Current - {value[:8]}"
                if value == st.session_state.conversation_id
                else f"Saved - {value[:8]}"
            ),
        )
        if selected_conversation != st.session_state.conversation_id:
            st.session_state.conversation_id = selected_conversation
            st.session_state.messages = store.load(
                authenticated_user.username,
                selected_conversation,
            )
            st.rerun()
        if st.button("Sign out", use_container_width=True):
            authenticated_user.close()
            st.session_state.authenticated_user = None
            st.session_state.messages = []
            st.session_state.accessible_domain_keys = None
            st.rerun()

    st.divider()
    st.header("Demo prompts")
    selected_prompt = None
    for sample in demo.get("sample_prompts", []):
        if st.button(
            sample["label"],
            disabled=not authenticated_user,
            use_container_width=True,
        ):
            selected_prompt = sample["prompt"]

    st.divider()
    if st.button(
        "Start new conversation",
        disabled=not authenticated_user,
        use_container_width=True,
    ):
        st.session_state.conversation_id = new_conversation_id()
        st.session_state.messages = []
        st.rerun()

if not deployment:
    st.warning(
        "No local deployment configuration was found. Run "
        "`python scripts/discover_fabric_agents.py`, review the generated "
        "domain configuration, then run `python scripts/deploy_agents.py`."
    )

accessible_keys: set[str] = set()
if authenticated_user:
    fabric = FabricClient(authenticated_user.credential)
    if st.session_state.accessible_domain_keys is None:
        discovered_keys = set()
        for domain in domains:
            if fabric.can_access_domain(domain):
                discovered_keys.add(domain.key)
        st.session_state.accessible_domain_keys = discovered_keys
    accessible_keys = set(st.session_state.accessible_domain_keys)
    with st.sidebar:
        st.header("Available domains")
        for domain in domains:
            if domain.key in accessible_keys:
                st.success(domain.label)
            else:
                st.error(f"{domain.label}: not accessible")
        if st.button("Refresh domain access", use_container_width=True):
            st.session_state.accessible_domain_keys = None
            st.rerun()

if authenticated_user and not st.session_state.messages:
    st.session_state.messages = store.load(
        authenticated_user.username,
        st.session_state.conversation_id,
    )

for message in st.session_state.messages:
    with st.chat_message(message.role):
        if message.role == "assistant":
            routing_evidence(list(message.routing_events))
        st.markdown(message.content)

typed_prompt = st.chat_input(
    "Ask a question across your authorized Fabric domains",
    disabled=not authenticated_user or not deployment,
)
prompt = selected_prompt or typed_prompt

if prompt and authenticated_user and deployment:
    user_message = ChatMessage(role="user", content=str(prompt))
    st.session_state.messages.append(user_message)
    with st.chat_message("user"):
        st.markdown(str(prompt))

    with st.chat_message("assistant"):
        try:
            orchestrator = FoundryOrchestrator(
                endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                router_agent_name=deployment["router_agent_name"],
                synthesizer_agent_name=deployment[
                    "synthesizer_agent_name"
                ],
                domain_agent_names=deployment["domain_agent_names"],
                credential=authenticated_user.credential,
            )
            context_limit = int(demo.get("history_context_messages", 8))
            history = [
                {"role": message.role, "content": message.content}
                for message in st.session_state.messages[-context_limit:-1]
            ]
            result = orchestrator.ask(
                question=str(prompt),
                domains=domains,
                accessible_domain_keys=accessible_keys,
                history=history,
            )
            events = [
                {
                    "domain": event.domain,
                    "status": event.status,
                    "outcome": event.outcome,
                }
                for event in result.routing_events
            ]
            answer = result.answer
        except APIStatusError as error:
            events = []
            answer = (
                "Foundry could not complete the request "
                f"(status `{error.status_code}`). Verify the project role, "
                "model deployment, Fabric license, and data-agent access."
            )
        except FabricApiError:
            events = []
            answer = (
                "Fabric access discovery failed. Verify the signed-in user's "
                "license and workspace access, then refresh domain access."
            )
        except (KeyError, ValueError, RuntimeError):
            events = []
            answer = (
                "The demo configuration or routing response was invalid. "
                "Review the local domain and deployment configuration."
            )
        routing_evidence(events)
        st.markdown(answer)

    st.session_state.messages.append(
        ChatMessage(
            role="assistant",
            content=answer,
            routing_events=tuple(events),
        )
    )
    store.save(
        authenticated_user.username,
        st.session_state.conversation_id,
        st.session_state.messages,
    )
