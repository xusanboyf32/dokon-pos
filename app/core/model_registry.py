"""Barcha modellar ro'yxati.

Alembic autogenerate faqat import qilingan modellarni "ko'radi".
Yangi modul modeli yaratilganda shu yerga import qo'shiladi, masalan:

    from app.modules.auth import models as auth_models  # noqa: F401

Agar unutilsa — `alembic check` testi buni ushlaydi.
"""

from app.modules.accounts import models as accounts_models  # noqa: F401
from app.modules.employees import models as employees_models  # noqa: F401
