"""Endpoint definitions shared by the blocking and asynchronous facades."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from typing import Generic, Literal, TypeVar

from ._protocol import Call
from .models import Attachment, DateRange

T = TypeVar("T")


def days_value(days: DateRange | str) -> str:
    value = str(days)
    # Accept explicit YYYYMMDD-YYYYMMDD ranges.
    parts = value.split("-")
    if len(parts) != 2 or any(len(p) != 8 or not p.isdigit() for p in parts):
        raise ValueError("days must be a DateRange or YYYYMMDD-YYYYMMDD")
    start, end = (date(int(p[:4]), int(p[4:6]), int(p[6:])) for p in parts)
    if end < start:
        raise ValueError("days end must be on or after start")
    return value


def positive(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


class Endpoints(Generic[T], ABC):
    @abstractmethod
    def _call(self, call: Call) -> T: ...

    def schools(self, query: str) -> T:
        """Search the global school directory. Returns result as a list of options."""
        if not query.strip():
            raise ValueError("school search query must not be empty")
        return self._call(
            Call(
                "api/schools/mobileapp",
                {"value": query},
                authenticated=False,
                kind="schools",
                global_origin=True,
            )
        )

    def rules(self) -> T:
        """Account profile, roles, relations.students, permissions, and uploadFileUrl."""
        return self._call(Call("apiv3/getrules"))

    def periods(self, *, weeks: bool = True, show_disabled: bool = True) -> T:
        """Academic periods; include weeks and disabled periods by default."""
        return self._call(
            Call(
                "apiv3/getperiods",
                {
                    "weeks": weeks,
                    "show_disabled": show_disabled,
                },
            )
        )

    def diary(self, student: str, days: DateRange | str, *, rings: bool = True) -> T:
        """Diary including homework, assessments, lesson times, and attachment links."""
        if not student:
            raise ValueError("student must not be empty")
        return self._call(
            Call(
                "apiv3/getdiary",
                {
                    "student": student,
                    "days": days_value(days),
                    "rings": int(rings),
                },
            )
        )

    def marks(self, student: str, days: DateRange | str) -> T:
        """Subject marks with averages, weights, and comments preserved as sent."""
        if not student:
            raise ValueError("student must not be empty")
        return self._call(Call("apiv3/getmarks", {"student": student, "days": days_value(days)}))

    def final_assessments(self, *, student: str | None = None) -> T:
        return self._call(Call("apiv3/getfinalassessments", {"student": student}))

    def messages(
        self,
        *,
        folder: Literal["inbox", "sent"] = "inbox",
        unread_only: bool = False,
        limit: int = 20,
        page: int = 1,
        search: str | None = None,
    ) -> T:
        """One message page. search maps to the filter query parameter."""
        if folder not in ("inbox", "sent"):
            raise ValueError("folder must be inbox or sent")
        positive(limit, "limit")
        positive(page, "page")
        return self._call(
            Call(
                "apiv3/getmessages",
                {
                    "folder": folder,
                    "unreadonly": "yes" if unread_only else "no",
                    "limit": limit,
                    "page": page,
                    "filter": search,
                },
            )
        )

    def message(self, message_id: str) -> T:
        """Fetch a message. The server may mark it read; this behavior is unverified."""
        if not message_id:
            raise ValueError("message_id must not be empty")
        return self._call(Call("apiv3/getmessageinfo", {"id": message_id}))

    def message_receivers(self) -> T:
        return self._call(Call("apiv3/getmessagereceivers"))

    def send_message(
        self,
        *,
        sender_id: int,
        recipients: Sequence[str],
        subject: str,
        text: str,
        attachments: Sequence[Attachment] = (),
    ) -> T:
        """Send explicitly; sender_id maps to the person ID query parameter id.

        No retry is made, including after a connection failure. A timeout may occur
        after the server accepted a message; check sent messages before retrying.
        """
        if type(sender_id) is not int or sender_id < 0:
            raise ValueError("sender_id must be a nonnegative integer")
        if isinstance(recipients, str) or not recipients:
            raise ValueError("recipients must be a nonempty sequence of user IDs")
        if any(not r or "," in r for r in recipients):
            raise ValueError("recipient IDs must be nonempty and contain no commas")
        return self._call(
            Call(
                "apiv3/sendmessage",
                {"id": sender_id},
                method="POST",
                body={
                    "subject": subject,
                    "text": text,
                    "users_to": ",".join(recipients),
                    "fid": [a.file_id for a in attachments],
                    "filename": [a.filename for a in attachments],
                },
            )
        )

    def announcements(self, *, limit: int = 20, page: int = 1) -> T:
        positive(limit, "limit")
        positive(page, "page")
        return self._call(Call("apiv3/getboardnotices", {"limit": limit, "page": page}))

    def announcement(self, notice_id: str) -> T:
        if not notice_id:
            raise ValueError("notice_id must not be empty")
        return self._call(Call("apiv3/getboardnoticeinfo", {"id": notice_id}))

    def control_works(
        self, student: str, *, date_start: str, date_end: str, lesson_id: str = ""
    ) -> T:
        """Web AJAX endpoint, not v3. Date strings are passed through unmodified.

        The date format and whether a web cookie is required need school-level
        verification. Pass a cookie through the client constructor if necessary.
        """
        if not student or not date_start or not date_end:
            raise ValueError("student, date_start, and date_end must not be empty")
        return self._call(
            Call(
                "journal-cw-ajax-action",
                {
                    "method": "cw.get_by_student_id",
                    "student_id": student,
                    "dateStart": date_start,
                    "dateEnd": date_end,
                    "lesson_id": lesson_id,
                },
                kind="control_works",
            )
        )
