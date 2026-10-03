"""Credentials and the shared HTTP client for Azure AI Search and Azure OpenAI.

Auth uses the container's managed identity (DefaultAzureCredential). Set
AZURE_SEARCH_API_KEY / AZURE_OPENAI_API_KEY to use keys instead, for example
in local development.
"""

from __future__ import annotations

import os

import httpx


class Auth:
    def __init__(self, key_env: str, scope: str):
        self.key = os.environ.get(key_env)
        self.scope = scope
        self._cred = None

    @property
    def cred(self):
        # Created on first use, so FAKE_AZURE runs and tests never build one.
        if self._cred is None:
            from azure.identity.aio import DefaultAzureCredential

            self._cred = DefaultAzureCredential()
        return self._cred

    async def headers(self) -> dict:
        if self.key:
            return {"api-key": self.key}
        token = await self.cred.get_token(self.scope)
        return {"Authorization": f"Bearer {token.token}"}


search_auth = Auth("AZURE_SEARCH_API_KEY", "https://search.azure.com/.default")
aoai_auth = Auth("AZURE_OPENAI_API_KEY", "https://cognitiveservices.azure.com/.default")
http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
