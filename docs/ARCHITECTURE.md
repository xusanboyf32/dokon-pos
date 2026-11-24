# Arxitektura

## 1. Umumiy ko'rinish

```
 Brauzer (React + TS)
   │  HTTPS, JSON, access token (Authorization: Bearer)
   │  refresh token — httpOnly cookie
   ▼
 FastAPI (modular monolith)
   ├── PostgreSQL  — asosiy ma'lumotlar (yagona haqiqat manbai)
   ├── Redis       — Celery broker (11-bosqich); login himoyasi bazada (A-032)
   └── Celery      — fon vazifalari (hisobotlar, PDF, yaroqlilik ogohlantirishi)
```

Tizim bitta serverda ishlaydigan **modular monolith**: bitta ilova, lekin ichida mustaqil modullar.
Keyinchalik kerak bo'lsa modulni alohida servisga ajratish oson.

## 2. Papkalar tuzilmasi

```
dokon-pos/
├── app/
│   ├── main.py                 FastAPI ilovasi, router'larni ulash, middleware
│   ├── cli.py                  server buyruqlari (create-superadmin, unlock-superadmin)
│   ├── core/                   butun loyiha uchun umumiy
│   │   ├── config.py           Settings (pydantic-settings, .env)
│   │   ├── database.py         async engine, session, Base, tranzaksiya yordamchilari
│   │   ├── security.py         parol hash (argon2), JWT
│   │   ├── time.py             utcnow(), Toshkent vaqt zonasi
│   │   ├── money.py            Decimal yordamchilari, yaxlitlash
│   │   ├── exceptions.py       AppError ierarxiyasi + global handler
│   │   ├── pagination.py       Page/Cursor sxemalari
│   │   ├── logging.py          structlog sozlamasi, request_id
│   │   └── permissions.py      Role → Permission xaritasi
│   ├── modules/
│   │   ├── auth/               login, refresh, logout, sessiyalar, blok (A-032)
│   │   ├── employees/          xodimlar, lavozim berish
│   │   ├── accounts/           parollar (user_accounts)
│   │   ├── audit/              audit jurnali
│   │   ├── catalog/            brend, kategoriya, birlik, mahsulot
│   │   ├── suppliers/          ta'minotchilar
│   │   ├── warehouse/          ombor, kirim, do'konga jo'natish
│   │   ├── kassa/              kassalar, savatlar, savdo, chek, qaytarish
│   │   ├── clients/            mijozlar, qarzlar
│   │   ├── accounting/         buxgalter qabuli, seyf, xarajatlar
│   │   └── payroll/            oylik, jarima, bonus
│   └── workers/                Celery vazifalari
├── alembic/                    migratsiyalar
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── docs/
├── .env.example
└── pyproject.toml
```

Har bir modul ichida bir xil fayllar:

| Fayl | Vazifasi | Nimani qilmaydi |
|---|---|---|
| `router.py` | HTTP: so'rovni qabul qiladi, sxemani tekshiradi, service'ni chaqiradi, javob qaytaradi | Biznes-mantiq, SQL |
| `service.py` | Biznes-qoidalar: "admin admin'ni o'zgartira olmaydi", narx hisoblash, tranzaksiya chegarasi | HTTP, to'g'ridan-to'g'ri SQL |
| `repository.py` | Bazaga so'rovlar (SELECT/INSERT/UPDATE) | Biznes-qoidalar |
| `models.py` | SQLAlchemy jadvallari | — |
| `schemas.py` | Pydantic: kiruvchi/chiquvchi ma'lumot | — |
| `dependencies.py` | FastAPI Depends (masalan, joriy foydalanuvchi) | — |

**Modullar orasidagi qoida:** modul boshqa modulning `service`'ini chaqirishi mumkin,
lekin boshqa modulning `repository` yoki `models`'iga to'g'ridan-to'g'ri yozmaydi.

## 3. So'rov oqimi

```
HTTP so'rov
  → middleware (request_id, log)
  → router (Pydantic tekshiruv, ruxsat tekshiruvi — Depends)
  → service (biznes-qoidalar, BITTA tranzaksiya)
      → repository (SQL)
      → audit.record(...)  (xuddi shu tranzaksiyada)
  → commit / rollback
  → javob (Pydantic response model)
```

- **Tranzaksiya chegarasi service darajasida.** Bitta biznes-amal = bitta tranzaksiya.
  Masalan savdo: chek + qatorlar + qoldiq kamayishi + to'lov + audit — hammasi birga yoki hech biri.
- Xatolar `AppError` sifatida ko'tariladi va global handler ularni yagona formatga o'giradi
  (qarang: API_CONVENTIONS.md).

## 4. Ma'lumotlar bo'yicha umumiy qoidalar

| Mavzu | Qoida |
|---|---|
| Birlamchi kalit | `id BIGINT GENERATED ALWAYS AS IDENTITY` — parallel qo'shishda ham ketma-ket va takrorlanmas |
| Vaqt | Har jadvalda `created_at`, `updated_at` — `timestamptz`, UTC, `server_default=now()` |
| Kim qildi | O'zgaruvchi jadvallarda `created_by_id`, `updated_by_id` |
| O'chirish | Biznes-ob'ektlar soft delete (`deleted_at`). Pul/savdo yozuvlari hech qachon o'chirilmaydi |
| Pul | `Numeric(14, 2)` + `Decimal`, valyuta UZS |
| Miqdor | `Numeric(12, 3)` — kg/litr uchun 3 xona (dona ham shu turda) |
| Unikallik | Bazada `UNIQUE` constraint (Python tekshiruvi faqat chiroyli xabar uchun) |
| Matn qidiruvi | `pg_trgm` + GIN indeks |
| Enum | Python `StrEnum` + bazada `VARCHAR` + `CHECK` (migratsiyasi oson) |

## 5. Pul harakati (ledger) tamoyili

Balanslar (kassadagi pul, mijoz qarzi, ta'minotchiga qarz, seyf) **alohida ustunda yangilanib
turmaydi** — ular harakatlar jurnalidan hisoblanadi yoki harakat bilan bir tranzaksiyada
yangilanadigan snapshot bilan tekshiriladi. Har bir pul harakati — o'chirib bo'lmaydigan yozuv:
summa, tur (naqd/karta/terminal), kim, qachon, nima sababdan.

## 6. Auth qisqacha
To'liq: [modules/auth.md](modules/auth.md).
- `employees` / `user_accounts` / `auth_sessions` — uchta alohida jadval.
- Access token 15 daqiqa (JSON javobda), refresh token 24 soat (httpOnly cookie, rotation).
- Rol — xodimda; ruxsatlar kodda (`core/permissions.py`).

## 7. Fon vazifalari (Celery)
- Kunlik/oylik hisobotlarni tayyorlash, PDF/Excel eksport.
- Yaroqlilik muddati yaqinlashgan mahsulotlar ro'yxati.
- Eski sessiyalarni tozalash.

Kassa yo'lidagi (savdo, skanerlash) hech bir amal fon vazifasini **kutmaydi**.
