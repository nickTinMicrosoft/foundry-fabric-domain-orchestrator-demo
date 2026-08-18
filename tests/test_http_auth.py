import json
import os
import unittest
from unittest.mock import patch

from scripts.deploy_agents import create_connection
from src.fabric import FabricClient


class FakeToken:
    token = "test-token"


class FakeCredential:
    def get_token(self, *scopes):
        return FakeToken()


class FakeResponse:
    status = 200

    def __init__(self, payload=None):
        self._payload = payload or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class HttpAuthorizationTests(unittest.TestCase):
    def test_fabric_request_uses_bearer_token(self):
        def fake_urlopen(request, timeout):
            self.assertEqual(
                "Bearer test-token",
                request.get_header("Authorization"),
            )
            return FakeResponse({"value": []})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            payload = FabricClient(FakeCredential())._get(
                "https://api.fabric.microsoft.com/v1/workspaces"
            )
        self.assertEqual({"value": []}, payload)

    def test_arm_connection_request_uses_bearer_token(self):
        environment = {
            "AZURE_SUBSCRIPTION_ID": "subscription",
            "AZURE_RESOURCE_GROUP": "resource-group",
            "FOUNDRY_ACCOUNT_NAME": "account",
            "FOUNDRY_PROJECT_NAME": "project",
        }

        def fake_urlopen(request, timeout):
            self.assertEqual(
                "Bearer test-token",
                request.get_header("Authorization"),
            )
            return FakeResponse()

        with (
            patch.dict(os.environ, environment, clear=False),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            connection_id = create_connection(
                FakeCredential(),
                "connection",
                "https://example.test/mcp",
            )
        self.assertTrue(connection_id.endswith("/connections/connection"))


if __name__ == "__main__":
    unittest.main()
