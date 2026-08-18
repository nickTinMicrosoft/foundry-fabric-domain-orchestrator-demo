import base64
import json
from dataclasses import dataclass
from typing import Callable

from azure.identity import DeviceCodeCredential


AI_SCOPE = "https://ai.azure.com/.default"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


@dataclass
class AuthenticatedUser:
    username: str
    credential: DeviceCodeCredential

    def close(self) -> None:
        self.credential.close()


def _decode_username(access_token: str) -> str:
    segments = access_token.split(".")
    if len(segments) < 2:
        raise RuntimeError("The identity token did not contain JWT claims")
    payload = segments[1] + "=" * (-len(segments[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    username = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("unique_name")
    )
    if not username:
        raise RuntimeError("The authenticated username was not present")
    return str(username)


def authenticate_user(
    tenant_id: str,
    prompt_callback: Callable,
) -> AuthenticatedUser:
    credential = DeviceCodeCredential(
        tenant_id=tenant_id,
        prompt_callback=prompt_callback,
    )
    token = credential.get_token(AI_SCOPE)
    return AuthenticatedUser(
        username=_decode_username(token.token),
        credential=credential,
    )
