# Eljur API client

A reusable **Python 3.10+** library for Eljur, based on protocol analysis of the supplied Nice Eljur Android APK. Blocking and asynchronous clients share the same endpoint definitions. No Android runtime is required.

**Status:** request contracts recovered from the APK and tested offline. Authenticated live behavior has **not** been verified: no Eljur credentials were supplied. School-specific permissions, token expiry semantics, and the web control-work endpoint may require integration work.

## Install

From this repository:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install .
```

The package is named `eljur-api-client`; the import is `eljur_api`. It has not been published to PyPI.

## Obtain the developer key from your APK

Eljur requires a `devkey` in addition to an account token. This repository does not publish the third-party application's embedded keys. The included helper extracts just the Eljur connection configuration from your local APK using [JADX 1.5.3](https://github.com/skylot/jadx/releases/tag/v1.5.3):

```sh
python tools/extract_config.py /path/to/nice-eljur.apk \
  --jadx /path/to/jadx/bin/jadx --output eljur.local.json
```

The file is created with mode `0600` and is ignored by git. The helper requires Java and JADX only during extraction; the client itself does not. It does not copy the APK or decompiled sources into the project. You can also construct `Config(vendor="school", devkey="your-key")` directly using a developer key available to you.

The supplied APK defaults to `hselyceum`. For another school, set **both** `vendor` and `base_url` in the extracted config, or omit `base_url` to use `https://<vendor>.eljur.ru`. For an institution with a custom hostname, use its actual HTTPS origin and vendor.

## Login and read the diary

```python
import getpass
import json
from datetime import date
from pathlib import Path
from eljur_api import Config, DateRange, EljurClient

config = Config(**json.loads(Path("eljur.local.json").read_text()))
with EljurClient(config) as api:
    token = api.login(input("Login: "), getpass.getpass("Password: "))
    profile = api.rules().result
    students = profile["relations"]["students"]
    for student_id, info in students.items():
        print(student_id, info.get("name"))

    # Select a student ID returned for this account; no global/default student.
    student_id = input("Student ID: ")
    if student_id not in students:
        raise ValueError("Choose a student returned for this account")
    diary = api.diary(student_id, DateRange(date(2026, 10, 12), date(2026, 10, 18)))
    print(diary.result)
```

`login()` returns `AuthToken(token, expires)` and stores the token in memory. To reuse a caller-managed token, construct `EljurClient(config, auth_token=...)`. The SDK never saves credentials or tokens to disk. `clear_token()` forgets the token locally; it does not revoke it on the server. The APK provides no verified logout/refresh operation.

## Async use

```python
from eljur_api import AsyncEljurClient

async with AsyncEljurClient(config, auth_token=saved_token) as api:
    profile = await api.rules()
    marks = await api.marks(student_id, "20261001-20261031")
```

Every endpoint below works on both clients. On the async client, await the result.

| Method | Purpose |
| --- | --- |
| `schools(query)` | Search the global school directory without an account token |
| `rules()` | Profile, roles, related students/groups, permissions, upload URL |
| `periods(weeks=True, show_disabled=True)` | Academic periods and weeks |
| `diary(student, days, rings=True)` | Schedule, homework, lesson assessments and files |
| `marks(student, days)` | Marks by subject, averages, weights and comments |
| `final_assessments(student=None)` | Final/period assessments |
| `messages(folder="inbox", unread_only=False, limit=20, page=1, search=None)` | A page of inbox/sent messages |
| `message(message_id)` | Full message; server read-state side effects are unverified |
| `message_receivers()` | Recipient groups, subgroups and user IDs |
| `send_message(sender_id=..., recipients=[...], subject=..., text=..., attachments=())` | Explicitly send a message |
| `announcements(limit=20, page=1)` | A page of board notices |
| `announcement(notice_id)` | Full notice and file links |
| `control_works(student, date_start=..., date_end=..., lesson_id="")` | Web AJAX control-work listing; experimental |
| `upload_file(url, filename=..., content=b"...", field_name="userfile")` | Multipart upload to the URL from `rules()` |

`days` accepts `DateRange` or `YYYYMMDD-YYYYMMDD`, with real dates and range order validated. Date ranges are explicit to avoid hidden dependence on the machine's timezone. List endpoints return **one page**; increment `page` yourself and use the returned counts. No endpoint is called automatically after login.

## Responses and exceptions

Endpoint methods return `APIResponse(state, result, raw)`. API v3's `response.result` becomes `.result`; `.raw` keeps the complete original JSON. School discovery returns its `options` list as `.result`. Control works and upload use their original top-level objects as `.result`.

Result data is intentionally lossless JSON. The APK itself has incompatible projections of some fields, such as homework, IDs, marks, weights and school-specific relations. The SDK does not cast `"5-"` to a number, collapse dictionary IDs, or discard unknown fields. [Protocol notes](docs/protocol.md) describe the observed shapes.

```python
from eljur_api import AuthenticationError, RateLimitError, EljurError

try:
    response = api.rules()
except AuthenticationError:
    pass  # Ask the account owner to log in again.
except RateLimitError:
    pass  # Apply your application's own backoff policy.
except EljurError as error:
    print(error)
```

`APIError` exposes `state` and `http_status` where known. `ProtocolError` means unexpected JSON; `TransportError` means connection/TLS/timeout failure. Server error strings are redacted for known credentials. HTTP errors omit raw bodies and URLs. The SDK does not log requests; application HTTP debug logging can expose query-string credentials.

No automatic retries, redirects, refreshes, or message sending occur. A timeout during a POST can happen **after** the server accepted it; check server state before resending. HTTPS certificate checks are enabled. Environment proxy settings are ignored by default; supply a configured `httpx.HTTPTransport` / `httpx.AsyncHTTPTransport` through `transport=` if needed.

## Message attachments

This example is **opt-in**: calling `send_message()` sends to the supplied recipients.

```python
from pathlib import Path
from eljur_api import Attachment

profile = api.rules().result
uploaded = api.upload_file(
    profile["uploadFileUrl"],
    filename="notes.txt",
    content=Path("notes.txt").read_bytes(),
    content_type="text/plain",
).result
attachment = Attachment(uploaded["file"], uploaded["name"])

# sender_id is the account/person ID, not the message being replied to.
# Confirm recipients using message_receivers() before passing their IDs.
sent = api.send_message(
    sender_id=int(profile["id"]),
    recipients=[chosen_recipient_id],
    subject="Notes",
    text="Attached.",
    attachments=[attachment],
)
```

School cookies and token/developer-key parameters are never attached to the upload request. The URL may already contain a signed query string, which is preserved. Choose it from your own authenticated response. The byte-content API buffers the file in memory.

For control works, the APK declares an optional Cookie header. Pass `cookie="name=value; ..."` to the constructor if your school requires a web session. The SDK does not implement web login, ESIA/MOS SSO, CAPTCHA handling, or automatic attachment downloads.

## Development

```sh
pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m mypy src
python -m build
```

Tests use synthetic fixtures and `httpx.MockTransport`, with no real students, accounts, keys, or network access. See [reverse-engineering provenance](docs/reverse-engineering.md) for APK hash, recovered classes, limitations, and reproduction commands. The original APK, app source, telemetry backend, and third-party embedded keys are not redistributed.

MIT license covers this original SDK implementation. This is an unofficial project, unaffiliated with Eljur or Nice Eljur.
