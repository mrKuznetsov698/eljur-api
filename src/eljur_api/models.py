"""Stable protocol types. Variable school-specific result data stays lossless JSON."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from .errors import ProtocolError

DEFAULT_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 11; Pixel 4 Build/RP1A.200720.011)"


@dataclass(frozen=True)
class Config:
    vendor: str
    devkey: str = field(repr=False)
    base_url: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", self.vendor):
            raise ValueError("vendor must be a school subdomain, for example hselyceum")
        if not self.devkey.strip():
            raise ValueError("devkey must not be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        base = self.base_url or f"https://{self.vendor}.eljur.ru"
        parsed = urlsplit(base)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("base_url must be an HTTPS origin without credentials, path, or query")
        # A single, immutable school origin avoids accidental cross-account requests.
        object.__setattr__(self, "base_url", base.rstrip("/"))


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("end must be on or after start")

    def __str__(self) -> str:
        return (
            f"{self.start.year:04d}{self.start.month:02d}{self.start.day:02d}-"
            f"{self.end.year:04d}{self.end.month:02d}{self.end.day:02d}"
        )


@dataclass(frozen=True)
class AuthToken:
    token: str = field(repr=False)
    # Keep the server's expires string as-is: its format/timezone is not established.
    expires: str | None = None

    @classmethod
    def from_response(cls, response: APIResponse) -> AuthToken:
        result = response.result
        if not isinstance(result, dict) or not isinstance(result.get("token"), str):
            raise ProtocolError("Authentication response has no token")
        if not result["token"]:
            raise ProtocolError("Authentication response has an empty token")
        expires = result.get("expires")
        if expires is not None and not isinstance(expires, str):
            raise ProtocolError("Authentication expires must be a string or null")
        return cls(result["token"], expires)


@dataclass(frozen=True)
class APIResponse:
    """An API v3 result or a normalized non-v3 result, with original JSON available.

    Inspect ``raw`` for the exact server response. ``result`` preserves unknown fields,
    object keys, nulls, and lists without coercing marks or student IDs to numbers.
    """

    state: int
    result: Any = field(repr=False)
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class Attachment:
    """An already-uploaded file ID and its paired server filename."""

    file_id: str
    filename: str

    def __post_init__(self) -> None:
        if not self.file_id or not self.filename:
            raise ValueError("attachment file_id and filename must not be empty")
