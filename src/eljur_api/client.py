"""Blocking and asynchronous clients with identical endpoint methods."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any
from urllib.parse import urlsplit

import httpx

from ._endpoints import Endpoints
from ._protocol import Call, ResponseKind, decode, request_kwargs
from .errors import TransportError
from .models import APIResponse, AuthToken, Config


class _Session:
    def __init__(self, config: Config, auth_token: str | None, cookie: str | None) -> None:
        self.config = config
        if auth_token is not None and not auth_token.strip():
            raise ValueError("auth_token must not be empty")
        self._token = auth_token
        self._cookie = cookie

    @property
    def auth_token(self) -> str | None:
        """Current token for caller-managed persistence. Never stored on disk by the SDK."""
        return self._token

    def clear_token(self) -> None:
        """Forget the local token. This does not revoke it on the server."""
        self._token = None

    def _prepare(self, call: Call) -> dict[str, Any]:
        kwargs = request_kwargs(self.config, self._token, call)
        if self._cookie and not call.global_origin:
            kwargs["headers"]["Cookie"] = self._cookie
        return kwargs

    def _decode(
        self, response: httpx.Response, kind: ResponseKind, extra_secrets: tuple[str, ...] = ()
    ) -> APIResponse:
        secrets = [self.config.devkey, self._token or "", self._cookie or "", *extra_secrets]
        return decode(response, kind, secrets)

    def _upload_kwargs(
        self, url: str, filename: str, content: bytes, field_name: str, content_type: str
    ) -> dict[str, Any]:
        # uploadFileUrl may be a signed URL. Do not add devkey/token or school cookies.
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("upload URL must be HTTPS without credentials or fragment")
        if not filename or not field_name:
            raise ValueError("filename and field_name must not be empty")
        return {
            "method": "POST",
            "url": url,
            "headers": {"User-Agent": self.config.user_agent, "Accept": "application/json"},
            "files": {field_name: (filename, content, content_type)},
            "timeout": self.config.timeout,
            "follow_redirects": False,
        }


class EljurClient(_Session, Endpoints[APIResponse]):
    """Use as a context manager. One client represents one account and school.

    An injected httpx transport enables mock testing or custom connection policy.
    TLS verification is enabled; redirects and automatic retries are disabled.
    """

    def __init__(
        self,
        config: Config,
        *,
        auth_token: str | None = None,
        cookie: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(config, auth_token, cookie)
        self._http = httpx.Client(transport=transport, trust_env=False)
        self._public_http = httpx.Client(transport=transport, trust_env=False)
        self._upload_http = httpx.Client(transport=transport, trust_env=False)

    def __enter__(self) -> EljurClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()
        self._public_http.close()
        self._upload_http.close()

    def _request(self, kwargs: dict[str, Any], *, public: bool = False) -> httpx.Response:
        try:
            client = self._public_http if public else self._http
            return client.request(**kwargs)
        except httpx.RequestError:
            raise TransportError("Eljur request failed at the transport layer") from None

    def _call(self, call: Call) -> APIResponse:
        return self._decode(
            self._request(self._prepare(call), public=call.global_origin), call.kind
        )

    def login(self, login: str, password: str) -> AuthToken:
        """Exchange credentials for a token; update session only after validation."""
        if not login or not password:
            raise ValueError("login and password must not be empty")
        call = Call(
            "apiv3/auth",
            method="POST",
            body={"login": login, "password": password},
            authenticated=False,
        )
        response = self._decode(self._request(self._prepare(call)), "v3", (login, password))
        token = AuthToken.from_response(response)
        self._token = token.token
        return token

    def upload_file(
        self,
        url: str,
        *,
        filename: str,
        content: bytes,
        field_name: str = "userfile",
        content_type: str = "application/octet-stream",
    ) -> APIResponse:
        """Upload to rules().result['uploadFileUrl'] using the userfile multipart field.

        Return result includes file/name for an Attachment. A separate session
        prevents account cookies reaching the upload origin. The caller chooses
        the destination explicitly; no token or developer key is appended.
        """
        kwargs = self._upload_kwargs(url, filename, content, field_name, content_type)
        try:
            response = self._upload_http.request(**kwargs)
        except httpx.RequestError:
            raise TransportError("Eljur file upload failed at the transport layer") from None
        return self._decode(response, "upload", (url,))


class AsyncEljurClient(_Session, Endpoints[Awaitable[APIResponse]]):
    """Asynchronous equivalent. Use async with and await each endpoint method."""

    def __init__(
        self,
        config: Config,
        *,
        auth_token: str | None = None,
        cookie: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(config, auth_token, cookie)
        self._http = httpx.AsyncClient(transport=transport, trust_env=False)
        self._public_http = httpx.AsyncClient(transport=transport, trust_env=False)
        self._upload_http = httpx.AsyncClient(transport=transport, trust_env=False)

    async def __aenter__(self) -> AsyncEljurClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        await self._public_http.aclose()
        await self._upload_http.aclose()

    async def _request(self, kwargs: dict[str, Any], *, public: bool = False) -> httpx.Response:
        try:
            client = self._public_http if public else self._http
            return await client.request(**kwargs)
        except httpx.RequestError:
            raise TransportError("Eljur request failed at the transport layer") from None

    async def _call(self, call: Call) -> APIResponse:
        return self._decode(
            await self._request(self._prepare(call), public=call.global_origin), call.kind
        )

    async def login(self, login: str, password: str) -> AuthToken:
        if not login or not password:
            raise ValueError("login and password must not be empty")
        call = Call(
            "apiv3/auth",
            method="POST",
            body={"login": login, "password": password},
            authenticated=False,
        )
        response = self._decode(await self._request(self._prepare(call)), "v3", (login, password))
        token = AuthToken.from_response(response)
        self._token = token.token
        return token

    async def upload_file(
        self,
        url: str,
        *,
        filename: str,
        content: bytes,
        field_name: str = "userfile",
        content_type: str = "application/octet-stream",
    ) -> APIResponse:
        kwargs = self._upload_kwargs(url, filename, content, field_name, content_type)
        try:
            response = await self._upload_http.request(**kwargs)
        except httpx.RequestError:
            raise TransportError("Eljur file upload failed at the transport layer") from None
        return self._decode(response, "upload", (url,))
