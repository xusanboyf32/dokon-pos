# Do'kon POS

Kichik va o'rta oziq-ovqat do'konlari uchun universal savdo tizimi: bir nechta kassa,
ombor, buxgalteriya (kassadan pul qabul qilish), qarzlar, ta'minotchilar, xodimlar va oylik.

## Texnologiyalar

| Qatlam | Texnologiya |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Pydantic v2 |
| Ma'lumotlar bazasi | PostgreSQL 15+, Alembic (migratsiyalar) |
| Kesh / navbat | **Redis 7+** (`EXPIRE ... NX` buyrug'i kerak; Windows'da — WSL Ubuntu ichida), Celery |
| Frontend | React + TypeScript (rasmiy dizayn tizimi bilan) |
| Sifat | pytest, ruff, mypy, GitHub Actions |
| Paket boshqaruvi | uv + pyproject.toml |

## Hujjatlar

| Hujjat | Nima haqida |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Tizim arxitekturasi, papkalar, qatlamlar, ma'lumot oqimi |
| [docs/ENGINEERING.md](docs/ENGINEERING.md) | Kod yozish standartlari, testlash, unumdorlik, git tartibi, "tayyor" mezoni |
| [docs/API_CONVENTIONS.md](docs/API_CONVENTIONS.md) | API qoidalari: URL, javob/xato formati, pagination, filtr |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Qabul qilingan barcha qarorlar va ochiq savollar |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Modullar ketma-ketligi va holati |
| [docs/modules/auth.md](docs/modules/auth.md) | Auth moduli to'liq spetsifikatsiyasi |

## Ishga tushirish (lokal)

> Bu bo'lim skelet tayyor bo'lgach to'ldiriladi.

```powershell
uv sync                      # kutubxonalarni o'rnatish
copy .env.example .env       # sozlamalarni nusxalash va to'ldirish
uv run alembic upgrade head  # bazani migratsiya qilish
uv run python -m app.cli create-superadmin
uv run uvicorn app.main:app --reload
```
