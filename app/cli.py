"""Server buyruqlari.

    uv run python -m app.cli create-superadmin
    uv run python -m app.cli unlock-superadmin

Parol ekranda ko'rinmaydi (getpass) va terminal tarixiga yozilmaydi.
"""

import argparse
import asyncio
import sys
from collections.abc import Coroutine
from getpass import getpass
from typing import Any

from app.core.database import SessionFactory, engine
from app.core.exceptions import AppError
from app.modules.accounts.superadmin import create_superadmin, unlock_superadmin


async def _create_superadmin(username: str, password: str, confirmation: str) -> None:
    async with SessionFactory() as session:
        account = await create_superadmin(session, username, password, confirmation)
    print(f"✅ Superadmin yaratildi: {account.username}")


async def _unlock_superadmin() -> None:
    async with SessionFactory() as session:
        account = await unlock_superadmin(session)
    print(f"✅ Superadmin blokdan chiqarildi: {account.username}")


async def _run(command: Coroutine[Any, Any, None]) -> None:
    try:
        await command
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Do'kon POS buyruqlari")
    parser.add_argument("command", choices=["create-superadmin", "unlock-superadmin"])
    args = parser.parse_args(argv)

    # Klaviaturadan o'qish (input/getpass) bloklovchi amal — u async koddan TASHQARIDA
    if args.command == "create-superadmin":
        username = input("Superadmin username: ")
        password = getpass("Parol: ")
        confirmation = getpass("Parolni takrorlang: ")
        command = _create_superadmin(username, password, confirmation)
    else:
        command = _unlock_superadmin()

    try:
        asyncio.run(_run(command))
    except AppError as error:
        print(f"❌ {error.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
