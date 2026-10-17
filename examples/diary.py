"""python examples/diary.py after configuring eljur.local.json."""

import getpass
import json
from datetime import date, timedelta
from pathlib import Path

from eljur_api import Config, DateRange, EljurClient

config = Config(**json.loads(Path("eljur.local.json").read_text()))
with EljurClient(config) as api:
    api.login(input("Eljur login: "), getpass.getpass("Eljur password: "))
    students = api.rules().result["relations"]["students"]
    if not students:
        raise SystemExit("This account has no student relations")
    for student_id, info in students.items():
        print(student_id, info.get("name", ""))
    student_id = input("Student ID from the list above: ").strip()
    if student_id not in students:
        raise SystemExit("Choose an ID returned for this account")
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    diary = api.diary(student_id, DateRange(monday, monday + timedelta(days=6)))
    print(json.dumps(diary.result, ensure_ascii=False, indent=2))
