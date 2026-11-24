"""Swagger'da qo'lda sinash uchun sun'iy ma'lumot (faqat lokal baza).

    uv run python -m scripts.seed_demo

Yaratadi (bor bo'lsa — tegmaydi, qayta ishga tushirish xavfsiz):

    | Login   | Parol    | Kim            | Lavozim |
    |---------|----------|----------------|---------|
    | admin1  | admin123 | Ali Valiyev    | admin   |
    | kassir1 | 1234     | Anvar Karimov  | kassir  |
    | kassir2 | 1234     | Vali Rahimov   | kassir  |

Ma'lumot bazaga to'g'ridan-to'g'ri yoziladi — shuning uchun audit jurnaliga tushmaydi.
Production'da ishlamaydi.
"""

import asyncio
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.security import hash_password
from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.employees.models import Employee, EmployeePosition

DEMO = [
    # username, parol, ism, familiya, telefon, lavozim, maosh
    ("admin1", "admin123", "Ali", "Valiyev", "+998900000101", "admin", "6000000.00"),
    ("kassir1", "1234", "Anvar", "Karimov", "+998900000102", "kassir", "3000000.00"),
    ("kassir2", "1234", "Vali", "Rahimov", "+998900000103", "kassir", "3000000.00"),
]


async def seed() -> None:
    async with SessionFactory() as session:
        for username, password, first, last, phone, role, salary in DEMO:
            exists = await session.scalar(
                select(UserAccount.id).where(UserAccount.username == username)
            )
            if exists:
                print(f"  — {username}: allaqachon bor, tegilmadi")
                continue
            employee = Employee(
                first_name=first,
                last_name=last,
                birth_date=date(2000, 1, 15),
                gender="male",
                phone=phone,
                role=role,
                salary=Decimal(salary),
                photo_path="employees/demo.jpg",  # sinov uchun — fayl shart emas
            )
            session.add(employee)
            await session.flush()
            session.add(
                EmployeePosition(
                    employee_id=employee.id,
                    role=role,
                    salary=Decimal(salary),
                    valid_from=utcnow().date(),
                )
            )
            session.add(
                UserAccount(
                    employee_id=employee.id,
                    username=username,
                    password_hash=hash_password(password),
                )
            )
            print(f"  ✅ {username} / {password} — {first} {last} ({role}), xodim #{employee.id}")
        await session.commit()
    await engine.dispose()


def main() -> int:
    if get_settings().environment == "production":
        print("❌ Production bazasida sun'iy ma'lumot yaratilmaydi")
        return 1
    print("Sun'iy ma'lumot yaratilmoqda...")
    asyncio.run(seed())
    print("Tayyor. Swagger: http://localhost:8000/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
