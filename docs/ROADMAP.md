# Yo'l xaritasi

Har bir bosqich `ENGINEERING.md` dagi "tayyor" mezonidan o'tgandagina yopiladi.

| # | Bosqich | Tarkibi | Holat |
|---|---|---|---|
| 0 | Hujjatlar | README, CLAUDE.md, ARCHITECTURE, ENGINEERING, API_CONVENTIONS, DECISIONS | ✅ |
| 1 | Skelet | uv + pyproject, config, async DB, logging, xato formati, `/health`, Alembic, pytest, CI | ✅ |
| 2 | Auth | employees, accounts, sessions, login/refresh/logout, lockout (Redis), ruxsatlar, CLI, Xodimlar/Parollar CRUD | ✅ |
| 3 | Audit va Muammolar | audit jurnali, filtrlar, superadmin yashirinligi; 🔔 Muammolar (N-001…N-005), birinchi tur — akkaunt bloklandi | ⬜ |
| 4 | Katalog | brend, kategoriya, birlik, mahsulot (pg_trgm qidiruv), narx tarixi (C-001) | ⬜ |
| 5 | Ta'minotchilar | ta'minotchilar, ularning akkauntlari | ⬜ |
| 6 | Ombor | kirim, yaroqlilik muddati, do'konga jo'natish, qaytarish | ⬜ |
| 7 | Kassa | kassalar, savatlar, savdo, chegirma, to'lov, chek (uzluksiz raqam, O-004), qaytarish, Z-hisobot (O-003), katta chegirma muammosi | ⬜ |
| 8 | Mijozlar va qarzlar | mijozlar, qarz, qarz to'lovi | ⬜ |
| 9 | Buxgalteriya | kassadan qabul, kamomad, seyf, xarajatlar | ⬜ |
| 10 | Oylik | ish kunlari, oylik, bonus, jarima | ⬜ |
| 11 | Hisobotlar | Celery, kunlik/oylik hisobotlar, eksport | ⬜ |
| 12 | Frontend | React + TS, har rol sahifalari | ⬜ |
| 13 | Deploy | Docker Compose, CD, kunlik zaxira nusxa (O-001), Sentry (O-002) | ⬜ |

Frontend har bir backend moduli bilan parallel ham qurilishi mumkin — bu alohida hal qilinadi.
