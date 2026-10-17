"""Stable exceptions; messages never include request URLs or response bodies."""


class EljurError(Exception):
    """Base exception for the library."""


class TransportError(EljurError):
    """Connection, timeout, or TLS failure. A request may have reached the server."""


class ProtocolError(EljurError):
    """The server returned a malformed or unexpected response."""


class APIError(EljurError):
    """Eljur rejected a request at HTTP or application level."""

    def __init__(
        self, message: str, *, state: int | None = None, http_status: int | None = None
    ) -> None:
        super().__init__(message)
        self.state = state
        self.http_status = http_status


class AuthenticationError(APIError):
    """A token is missing or the server rejected authentication."""


class RateLimitError(APIError):
    """The server rejected a request due to rate limiting; no automatic retry occurs."""
