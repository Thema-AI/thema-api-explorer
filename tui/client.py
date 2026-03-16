"""HTTP client for authenticating and making API requests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


@dataclass
class APIResponse:
    status_code: int
    headers: dict[str, str]
    body: str
    elapsed_ms: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400


@dataclass
class AuthState:
    access_token: str = ""
    refresh_token: str = ""
    username: str = ""

    @property
    def authenticated(self) -> bool:
        return bool(self.access_token)


@dataclass
class APIClient:
    base_url: str
    auth: AuthState = field(default_factory=AuthState)
    timeout: float = 60

    async def authenticate(self, username: str, password: str) -> APIResponse:
        """Authenticate with username/password via /v1/token (form-data)."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
                resp = await c.post(
                    f"{self.base_url}/v1/token",
                    data={"username": username, "password": password},
                )
            elapsed = (time.monotonic() - start) * 1000
            result = APIResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
                elapsed_ms=elapsed,
            )
            if resp.is_success:
                data = resp.json()
                self.auth = AuthState(
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    username=username,
                )
            return result
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return APIResponse(
                status_code=0,
                headers={},
                body="",
                elapsed_ms=elapsed,
                error=str(exc),
            )

    async def request(
        self,
        method: str,
        path: str,
        query_params: dict[str, str] | None = None,
        json_body: dict | list | None = None,
        form_body: dict[str, str] | None = None,
    ) -> APIResponse:
        """Make an authenticated API request."""
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.auth.authenticated:
            headers["Authorization"] = f"Bearer {self.auth.access_token}"

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
                kwargs: dict = {
                    "headers": headers,
                    "params": query_params or None,
                }
                if json_body is not None:
                    kwargs["json"] = json_body
                elif form_body is not None:
                    kwargs["data"] = form_body
                resp = await c.request(method, url, **kwargs)
            elapsed = (time.monotonic() - start) * 1000
            return APIResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return APIResponse(
                status_code=0,
                headers={},
                body="",
                elapsed_ms=elapsed,
                error=str(exc),
            )
