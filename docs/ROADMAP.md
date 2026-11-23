# Yo'l xaritasi

Har bir bosqich `ENGINEERING.md` dagi "tayyor" mezonidan o'tgandagina yopiladi.

| # | Bosqich | Tarkibi | Holat |
|---|---|---|---|
| 0 | Hujjatlar | README, CLAUDE.md, ARCHITECTURE, ENGINEERING, API_CONVENTIONS, DECISIONS | ✅ |
| 1 | Skelet | uv + pyproject, config, async DB, logging, xato formati, `/health`, Alembic, pytest sozlamasi | ⏳ |
| 2 | Auth | employees, accounts, sessions, login/refresh/logout, lockout, ruxsatlar, CLI | ⬜ |
| 3 | Audit | audit jurnali, filtrlar, superadmin yashirinligi | ⬜ |
| 4 | Katalog | brend, kategoriya, birlik, mahsulot (pg_trgm qidiruv) | ⬜ |
| 5 | Ta'minotchilar | ta'minotchilar, ularning akkauntlari | ⬜ |
| 6 | Ombor | kirim, yaroqlilik muddati, do'konga jo'natish, qaytarish | ⬜ |
| 7 | Kassa | kassalar, savatlar, savdo, chegirma, to'lov, chek, qaytarish | ⬜ |
| 8 | Mijozlar va qarzlar | mijozlar, qarz, qarz to'lovi | ⬜ |
| 9 | Buxgalteriya | kassadan qabul, kamomad, seyf, xarajatlar | ⬜ |
| 10 | Oylik | ish kunlari, oylik, bonus, jarima | ⬜ |
| 11 | Hisobotlar | Celery, kunlik/oylik hisobotlar, eksport | ⬜ |
| 12 | Frontend | React + TS, har rol sahifalari | ⬜ |
| 13 | Deploy | Docker, CI/CD, monitoring | ⬜ |

Frontend har bir backend moduli bilan parallel ham qurilishi mumkin — bu alohida hal qilinadi.
