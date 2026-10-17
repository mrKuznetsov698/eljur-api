"""HTTP serialization and response validation shared by sync and async clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote, quote_plus

import httpx

from .errors import APIError, AuthenticationError, ProtocolError, RateLimitError
from .models import APIResponse, Config

ResponseKind = Literal["v3", "schools", "control_works", "upload"]


@dataclass(frozen=True)
class Call:
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    method: str = "GET"
    body: dict[str, Any] | None = field(default=None, repr=False)
    authenticated: bool = True
    kind: ResponseKind = "v3"
    global_origin: bool = False


def request_kwargs(config: Config, token: str | None, call: Call) -> dict[str, Any]:
    if call.authenticated and not token:
        raise AuthenticationError("Log in or supply auth_token before this request")
    params: dict[str, Any] = {
        "devkey": config.devkey,
        "out_format": "json",
        "vendor": config.vendor,
    }
    if call.authenticated:
        params["auth_token"] = token
    params.update(call.params)
    # Encode boolean query values as lowercase true/false and omit null.
    params = {
        k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items() if v is not None
    }
    origin = "https://global.eljur.ru" if call.global_origin else config.base_url
    return {
        "method": call.method,
        "url": f"{origin}/{call.path.lstrip('/')}",
        "params": params,
        "json": call.body,
        "headers": {"User-Agent": config.user_agent, "Accept": "application/json"},
        "timeout": config.timeout,
        "follow_redirects": False,
    }


def redact(message: str, secrets: list[str]) -> str:
    variants = {v for s in secrets if s for v in (s, quote(s, safe=""), quote_plus(s))}
    for value in sorted(variants, key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    return message


def decode(response: httpx.Response, kind: ResponseKind, secrets: list[str]) -> APIResponse:
    status = response.status_code
    if status < 200 or status >= 300:
        error_type = (
            AuthenticationError
            if status in (401, 403)
            else RateLimitError
            if status == 429
            else APIError
        )
        raise error_type(f"Eljur returned HTTP {status}", http_status=status)
    try:
        raw = response.json()
    except ValueError:
        raise ProtocolError("Eljur returned invalid JSON") from None
    if not isinstance(raw, dict):
        raise ProtocolError("Eljur response must be a JSON object")
    if kind == "v3":
        envelope = raw.get("response")
        if not isinstance(envelope, dict):
            raise ProtocolError("Eljur response envelope is missing")
        state = envelope.get("state")
        if type(state) is not int:
            raise ProtocolError("Eljur response.state must be an integer")
        if state != 200:
            error = envelope.get("error")
            message = redact(error, secrets) if isinstance(error, str) else "Eljur API error"
            error_type = (
                AuthenticationError
                if state in (401, 403)
                else RateLimitError
                if state == 429
                else APIError
            )
            raise error_type(message, state=state, http_status=status)
        if "result" not in envelope:
            raise ProtocolError("Eljur response.result is missing")
        return APIResponse(state, envelope["result"], raw)
    if kind == "schools":
        if raw.get("result") is not True:
            raise APIError("School discovery failed", http_status=status)
        if not isinstance(raw.get("options"), list):
            raise ProtocolError("School discovery options must be a list")
        return APIResponse(200, raw["options"], raw)
    if kind == "upload":
        if raw.get("success") is not True:
            raise APIError("File upload failed", http_status=status)
        if not isinstance(raw.get("file"), str) or not isinstance(raw.get("name"), str):
            raise ProtocolError("Upload response has no file ID or name")
        if not raw["file"] or not raw["name"]:
            raise ProtocolError("Upload response has an empty file ID or name")
    elif kind == "control_works":
        if raw.get("error"):
            raise APIError("Control-work request failed", http_status=status)
        if not isinstance(raw.get("rows"), list):
            raise ProtocolError("Control-work rows must be a list")
    return APIResponse(200, raw, raw)
