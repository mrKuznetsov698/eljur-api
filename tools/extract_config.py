#!/usr/bin/env python3
"""Extract only Eljur connection constants from a local APK via JADX.

No third-party keys are bundled in this project. The output is account-free but
contains the APK's developer key; keep it local and do not commit it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def parse_constants(source: str) -> dict[str, str]:
    def constant(name: str) -> str:
        match = re.search(r"\b" + re.escape(name) + r'\s*=\s*("(?:[^"\\]|\\.)*")\s*;', source)
        if match is None:
            raise ValueError(f"Eljur constant {name} was not found; inspect APK manually")
        value = json.loads(match[1])
        if not isinstance(value, str) or not value:
            raise ValueError(f"Eljur constant {name} must be a nonempty string")
        return value

    return {
        "vendor": constant("_VENDOR"),
        "base_url": constant("_BASE_URL"),
        "devkey": constant("DEV_KEY"),
        "user_agent": constant("USER_AGENT"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--jadx", default="jadx", help="Path to JADX executable (tested: 1.5.3)")
    parser.add_argument(
        "--output", required=True, type=Path, help="New private config file, e.g. eljur.local.json"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose another filename")
    with tempfile.TemporaryDirectory(prefix="eljur-config-") as tmp:
        source_path = Path(tmp) / "ApiConstants.java"
        completed = subprocess.run(
            [
                args.jadx,
                "--no-res",
                "--single-class",
                "com.team.common.ApiConstants",
                "--single-class-output",
                str(source_path),
                str(args.apk.resolve()),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode or not source_path.is_file():
            # Do not print decompiler output: it may include unrelated embedded constants.
            raise SystemExit("JADX could not decompile ApiConstants; check APK and JADX version")
        config = parse_constants(source_path.read_text())
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(config, output, indent=2)
        output.write("\n")
    print(f"Wrote local config to {args.output}. Keep it out of git.")


if __name__ == "__main__":
    main()
