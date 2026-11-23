# CLAUDE.md — AI yordamchi uchun qoidalar

Bu fayl Claude Code (va boshqa AI yordamchilar) loyiha bilan ishlashdan oldin o'qiydigan qoidalar.

## Muloqot
- Muloqot tili: **o'zbek (lotin)**. Kod, identifikatorlar va commit xabarlari: ingliz tilida.
- Ish uslubi: har bir modul **savol-javob** bilan boshlanadi. Har qarorda 2–3 variant,
  afzallik/kamchilik va tavsiya beriladi; tanlovni foydalanuvchi qiladi.
- Bir qadam tugamaguncha (foydalanuvchi ishga tushirib tasdiqlamaguncha) keyingisiga o'tilmaydi.
- Kodni foydalanuvchi o'zi ishga tushiradi va natijani aytadi.

## Ishni boshlashdan oldin o'qing
1. `docs/DECISIONS.md` — qabul qilingan qarorlar. **Ularni o'zboshimchalik bilan o'zgartirmang.**
2. `docs/ENGINEERING.md` — standartlar va "tayyor" mezoni.
3. `docs/ARCHITECTURE.md` — qatlamlar va papkalar.
4. Tegishli modul hujjati: `docs/modules/<modul>.md`.

## Qat'iy qoidalar
- Pul: faqat `Decimal` + `Numeric(14, 2)`. `float` taqiqlangan.
- Vaqt: faqat timezone-aware (`timestamptz`, UTC). `datetime.now()` / `utcnow()` taqiqlangan —
  `app.core.time.utcnow()` ishlatiladi.
- Tashqi kiruvchi ma'lumot faqat Pydantic sxema orqali o'tadi (`dict` qabul qilinmaydi).
- Biznes-mantiq faqat `service.py` da; SQL faqat `repository.py` da; router faqat HTTP bilan ishlaydi.
- Har bir sxema o'zgarishi — Alembic migratsiyasi bilan. `create_all()` ishlatilmaydi.
- Pul, qoldiq, narx, chegirma, parol, ruxsatlarga oid har bir amal audit jurnaliga yoziladi.
- `print()` emas — `structlog` logger.
- Yangi kod testlarsiz "tayyor" hisoblanmaydi.
- Maxfiy ma'lumot (parol, kalit) kodga yozilmaydi — faqat `.env`.
