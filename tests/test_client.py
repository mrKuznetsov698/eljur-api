"""Synthetic protocol fixtures. Never uses the network or real school/student data."""

import asyncio
import json
from datetime import date
from urllib.parse import quote

import httpx
import pytest

from eljur_api import (
    APIError,
    AsyncEljurClient,
    Attachment,
    AuthenticationError,
    Config,
    DateRange,
    EljurClient,
    ProtocolError,
    RateLimitError,
    TransportError,
)

CONFIG = Config(vendor="demo", devkey="test-developer-key")
DAYS = DateRange(date(2026, 10, 12), date(2026, 10, 18))


def ok(result=None):
    return httpx.Response(200, json={"response": {"state": 200, "result": result, "error": None}})


def client(handler, **kwargs):
    return EljurClient(CONFIG, transport=httpx.MockTransport(handler), **kwargs)


def test_login_json_token_expires_and_query():
    def handle(request):
        assert request.method == "POST"
        assert request.url.path == "/apiv3/auth"
        assert dict(request.url.params) == {
            "devkey": CONFIG.devkey,
            "vendor": "demo",
            "out_format": "json",
        }
        assert json.loads(request.content) == {"login": "user", "password": "secret"}
        assert request.headers["content-type"].startswith("application/json")
        return ok({"token": "new-token", "expires": "server-defined"})

    with client(handle) as api:
        token = api.login("user", "secret")
        assert api.auth_token == token.token == "new-token"
        assert token.expires == "server-defined"
        assert "new-token" not in repr(token)
        assert CONFIG.devkey not in repr(CONFIG)
        api.clear_token()
        assert api.auth_token is None


@pytest.mark.parametrize(
    "result", [{}, {"token": ""}, {"token": None}, {"token": "new", "expires": 123}]
)
def test_bad_login_does_not_replace_previous_token(result):
    with client(lambda _: ok(result), auth_token="old") as api:
        with pytest.raises(ProtocolError):
            api.login("user", "secret")
        assert api.auth_token == "old"


def test_authenticated_requests_and_cookie():
    def handle(request):
        assert request.url.host == "demo.eljur.ru"
        assert request.url.params["auth_token"] == "saved-token"
        assert request.headers["Cookie"] == "session=test"
        assert request.headers["User-Agent"] == CONFIG.user_agent
        return ok({"unknown": [None, {"value": "5-", "weight_float": "1.50"}]})

    with client(handle, auth_token="saved-token", cookie="session=test") as api:
        response = api.rules()
        assert response.result["unknown"][1]["value"] == "5-"
        assert response.raw["response"]["result"] == response.result


def test_missing_token_fails_before_network():
    with client(lambda _: pytest.fail("network must not be used")) as api:
        with pytest.raises(AuthenticationError):
            api.rules()


@pytest.mark.parametrize(
    ("invoke", "path", "params"),
    [
        (lambda a: a.rules(), "getrules", {}),
        (
            lambda a: a.periods(weeks=False),
            "getperiods",
            {"weeks": "false", "show_disabled": "true"},
        ),
        (
            lambda a: a.diary("001", DAYS),
            "getdiary",
            {"student": "001", "days": "20261012-20261018", "rings": "1"},
        ),
        (lambda a: a.marks("001", DAYS), "getmarks", {"student": "001", "days": str(DAYS)}),
        (lambda a: a.final_assessments(student="001"), "getfinalassessments", {"student": "001"}),
        (
            lambda a: a.messages(page=2, search="two words", unread_only=True),
            "getmessages",
            {
                "folder": "inbox",
                "page": "2",
                "filter": "two words",
                "unreadonly": "yes",
                "limit": "20",
            },
        ),
        (lambda a: a.message("001"), "getmessageinfo", {"id": "001"}),
        (lambda a: a.message_receivers(), "getmessagereceivers", {}),
        (lambda a: a.announcements(page=3), "getboardnotices", {"page": "3", "limit": "20"}),
        (lambda a: a.announcement("002"), "getboardnoticeinfo", {"id": "002"}),
    ],
)
def test_endpoint_contract(invoke, path, params):
    def handle(request):
        assert request.url.path == "/apiv3/" + path
        assert request.method == "GET"
        expected = {
            "devkey": CONFIG.devkey,
            "out_format": "json",
            "vendor": "demo",
            "auth_token": "token",
            **params,
        }
        assert dict(request.url.params) == expected
        return ok({})

    with client(handle, auth_token="token") as api:
        assert invoke(api).state == 200


def test_send_payload_and_paired_attachments():
    def handle(request):
        assert request.method == "POST"
        assert request.url.path == "/apiv3/sendmessage"
        assert request.url.params["id"] == "123"
        assert json.loads(request.content) == {
            "subject": "Test",
            "text": "Body",
            "users_to": "7,8",
            "fid": ["file-a", "file-b"],
            "filename": ["a.txt", "b.txt"],
        }
        return ok(None)

    with client(handle, auth_token="token") as api:
        api.send_message(
            sender_id=123,
            recipients=["7", "8"],
            subject="Test",
            text="Body",
            attachments=[Attachment("file-a", "a.txt"), Attachment("file-b", "b.txt")],
        )


def test_school_directory_has_no_school_credentials_or_cookie():
    def handle(request):
        if request.url.path == "/apiv3/getrules":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "sid=private; Domain=.eljur.ru; Path=/"},
                json={"response": {"state": 200, "result": {}}},
            )
        assert request.url.host == "global.eljur.ru"
        assert request.url.path == "/api/schools/mobileapp"
        assert "auth_token" not in request.url.params
        assert "Cookie" not in request.headers
        assert request.url.params["value"] == "Example School"
        return httpx.Response(200, json={"result": True, "options": [{"domain": "demo"}]})

    with client(handle, auth_token="token", cookie="sid=explicit") as api:
        api.rules()
        assert api.schools("Example School").result == [{"domain": "demo"}]


def test_control_works_separate_response_shape():
    def handle(request):
        assert request.url.path == "/journal-cw-ajax-action"
        assert request.url.params["method"] == "cw.get_by_student_id"
        assert request.url.params["student_id"] == "001"
        assert request.url.params["dateStart"] == "2026-10-12"
        return httpx.Response(200, json={"rows": [], "datesState": {}, "error": None})

    with client(handle, auth_token="token") as api:
        assert (
            api.control_works("001", date_start="2026-10-12", date_end="2026-10-18").result["rows"]
            == []
        )


def test_upload_is_multipart_and_isolated_from_school_credentials():
    def handle(request):
        if request.url.path == "/apiv3/getrules":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "sid=private; Path=/"},
                json={"response": {"state": 200, "result": {}}},
            )
        assert request.url == "https://demo.eljur.ru/upload?signature=example"
        assert request.method == "POST"
        assert "Cookie" not in request.headers
        assert b'name="userfile"; filename="test.txt"' in request.content
        assert b"file-content" in request.content
        return httpx.Response(200, json={"success": True, "file": "file-id", "name": "test.txt"})

    with client(handle, auth_token="token", cookie="sid=explicit") as api:
        api.rules()
        result = api.upload_file(
            "https://demo.eljur.ru/upload?signature=example",
            filename="test.txt",
            content=b"file-content",
        ).result
        assert Attachment(result["file"], result["name"]).file_id == "file-id"


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, APIError),
        (302, APIError),
    ],
)
def test_http_errors_never_follow_redirect_or_leak_body(status, exc):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, text="private body", headers={"Location": "https://other.test"}
        )

    with client(handle, auth_token="token") as api:
        with pytest.raises(exc) as caught:
            api.rules()
        assert caught.value.http_status == status
        assert "private body" not in str(caught.value)
        assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"response": []},
        {"response": {"state": "200"}},
        {"response": {"state": True}},
        {"response": {"state": 200}},
    ],
)
def test_malformed_payload(payload):
    with client(lambda _: httpx.Response(200, json=payload), auth_token="token") as api:
        with pytest.raises(ProtocolError):
            api.rules()


def test_invalid_json():
    with client(
        lambda _: httpx.Response(200, text="<html>Login</html>"), auth_token="token"
    ) as api:
        with pytest.raises(ProtocolError):
            api.rules()


def test_api_error_redacts_credentials_and_encoded_token():
    token = "private-token/&"
    message = f"bad user password {token} {quote(token, safe='')} {CONFIG.devkey}"
    with client(
        lambda _: httpx.Response(200, json={"response": {"state": 401, "error": message}}),
        auth_token=token,
    ) as api:
        with pytest.raises(AuthenticationError) as caught:
            api.login("user", "password")
        assert caught.value.state == 401
        for secret in [token, quote(token, safe=""), CONFIG.devkey, "password", "user"]:
            assert secret not in str(caught.value)


def test_transport_error_is_not_retried_or_exposed():
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret URL " + str(request.url), request=request)

    with client(handle, auth_token="token") as api:
        with pytest.raises(TransportError) as caught:
            api.send_message(sender_id=0, recipients=["1"], subject="s", text="t")
        assert "auth_token" not in str(caught.value)
        assert caught.value.__suppress_context__
        assert len(calls) == 1


@pytest.mark.parametrize("days", ["20261012", "20260230-20260301", "20261018-20261012"])
def test_invalid_date_ranges(days):
    with client(lambda _: pytest.fail("network"), auth_token="token") as api:
        with pytest.raises(ValueError):
            api.diary("1", days)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://demo.test",
        "https://u:p@demo.test",
        "https://demo.test/path",
        "https://demo.test?key=foo",
    ],
)
def test_invalid_base_urls(base_url):
    with pytest.raises(ValueError):
        Config(vendor="demo", devkey="key", base_url=base_url)


def test_async_login_endpoints_and_upload():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/apiv3/auth":
            return ok({"token": "async-token", "expires": None})
        if request.url.path == "/upload":
            assert b'name="userfile"' in request.content
            return httpx.Response(200, json={"success": True, "file": "f", "name": "n"})
        assert request.url.params["auth_token"] == "async-token"
        return ok({})

    async def run():
        async with AsyncEljurClient(CONFIG, transport=httpx.MockTransport(handle)) as api:
            await api.login("user", "secret")
            await api.rules()
            await api.diary("001", DAYS)
            await api.upload_file("https://files.example.test/upload", filename="n", content=b"x")

    asyncio.run(run())
    assert len(calls) == 4


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("schools", {"result": False, "options": []}),
        ("schools", {"result": True, "options": {}}),
        ("control_works", {"rows": [], "error": "rejected"}),
        ("control_works", {"rows": {}}),
        ("upload", {"success": False}),
        ("upload", {"success": True, "file": "", "name": "n"}),
        ("upload", {"success": True, "file": "id", "name": None}),
    ],
)
def test_non_v3_failures(kind, payload):
    with client(lambda _: httpx.Response(200, json=payload), auth_token="token") as api:
        with pytest.raises((APIError, ProtocolError)):
            if kind == "schools":
                api.schools("school")
            elif kind == "control_works":
                api.control_works("1", date_start="start", date_end="end")
            else:
                api.upload_file("https://upload.test/file", filename="n", content=b"x")


def test_async_errors_and_cookie_isolation():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/apiv3/getrules":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "sid=private; Domain=.eljur.ru; Path=/"},
                json={"response": {"state": 200, "result": {}}},
            )
        if request.url.path == "/api/schools/mobileapp":
            assert "Cookie" not in request.headers
            assert "auth_token" not in request.url.params
            return httpx.Response(200, json={"result": True, "options": []})
        if request.url.path == "/apiv3/getmessages":
            return httpx.Response(200, json={"response": {"state": 429, "error": "slow down"}})
        raise httpx.ConnectError("private URL " + str(request.url), request=request)

    async def run():
        async with AsyncEljurClient(
            CONFIG, transport=httpx.MockTransport(handle), auth_token="token", cookie="sid=explicit"
        ) as api:
            await api.rules()
            await api.schools("school")
            with pytest.raises(RateLimitError):
                await api.messages()
            with pytest.raises(TransportError):
                await api.login("user", "secret")
            with pytest.raises(TransportError):
                await api.upload_file("https://upload.test/file", filename="n", content=b"x")
            assert api.auth_token == "token"

    asyncio.run(run())
    assert len(calls) == 5


def test_config_extractor_uses_only_eljur_constants():
    import runpy
    from pathlib import Path

    parse_constants = runpy.run_path(str(Path(__file__).parents[1] / "tools/extract_config.py"))[
        "parse_constants"
    ]
    config = parse_constants("""
        public static final String DEV_KEY = "synthetic-key";
        public static final String USER_AGENT = "test-agent";
        private static String _BASE_URL = "https://demo.eljur.ru";
        private static String _VENDOR = "demo";
        public static final String UNRELATED_KEY = "do-not-export";
    """)
    assert config == {
        "vendor": "demo",
        "devkey": "synthetic-key",
        "base_url": "https://demo.eljur.ru",
        "user_agent": "test-agent",
    }
    with pytest.raises(ValueError, match="Eljur constant"):
        parse_constants("unrelated source")
