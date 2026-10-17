"""Read marks asynchronously using ELJUR_TOKEN and ELJUR_STUDENT from the environment."""

import asyncio
import json
import os
from datetime import date
from pathlib import Path

from eljur_api import AsyncEljurClient, Config, DateRange


async def main() -> None:
    config = Config(**json.loads(Path("eljur.local.json").read_text()))
    async with AsyncEljurClient(config, auth_token=os.environ["ELJUR_TOKEN"]) as api:
        today = date.today()
        marks = await api.marks(os.environ["ELJUR_STUDENT"], DateRange(today.replace(day=1), today))
        print(json.dumps(marks.result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
