# Muhandislik standartlari

## 1. Modul "tayyor" mezoni (Definition of Done)

Modul quyidagilarning **hammasi** bajarilgandagina tayyor hisoblanadi:

- [ ] Modul hujjati (`docs/modules/<modul>.md`) yozilgan va qarorlar `DECISIONS.md` ga qo'shilgan
- [ ] Model + Alembic migratsiyasi (yangi bazada ham, mavjud bazada ham ishlaydi)
- [ ] Router / service / repository qatlamlari ajratilgan
- [ ] Barcha kiruvchi ma'lumot Pydantic sxemalari orqali
- [ ] Ruxsatlar tekshirilgan (har endpoint uchun kim kira oladi)
- [ ] Muhim amallar audit jurnaliga yoziladi
- [ ] Testlar: unit + integration + API; pul/qoldiq/auth uchun concurrency va chegaraviy holatlar
- [ ] `ruff check`, `ruff format`, `mypy`, `pytest` — hammasi toza
- [ ] Ro'yxatlarda pagination, qidiruv va filtrlar indeks bilan
- [ ] Swagger'da har endpoint tavsifi va misollari bor

## 2. Testlash strategiyasi

| Tur | Papka | Baza | Qachon |
|---|---|---|---|
| Unit | `tests/unit/` | Yo'q | Sof hisob-kitob: narx, chegirma, yaxlitlash, ruxsat xaritasi |
| Integration | `tests/integration/` | Haqiqiy PostgreSQL (test bazasi) | Repository, constraint'lar, tranzaksiyalar |
| API | `tests/api/` | Haqiqiy PostgreSQL | Endpoint to'liq: status kodlar, ruxsatlar, javob formati |
| Concurrency | `tests/integration/` | Haqiqiy PostgreSQL | Parallel savdo, parallel mahsulot qo'shish, parallel refresh |
| Yuklama | `tests/load/` (keyinroq, locust) | Staging | Bir nechta kassa bir vaqtda |

Qoidalar:
- Testlar **SQLite emas, PostgreSQL** da ishlaydi (constraint va bloklash xatti-harakati bir xil bo'lishi uchun).
- Har test o'z tranzaksiyasida ishlaydi va oxirida rollback qilinadi — testlar bir-biriga ta'sir qilmaydi.
- Test ma'lumotlari factory'lar orqali yaratiladi (qo'lda JSON emas).
- Har bir topilgan bug uchun avval uni takrorlovchi test yoziladi, keyin tuzatiladi.
- Minimal qamrov: `core/` va pul/qoldiq/auth service'lari uchun 90%+, qolganlari 75%+.

## 3. PostgreSQL unumdorligi

- **Async engine + pool**: `pool_size`, `max_overflow` sozlamada; `pool_pre_ping=True`.
- **statement_timeout = 5s** (kassa yo'li), hisobotlar uchun alohida, uzunroq.
- **N+1 taqiqlangan**: ro'yxatlarda `selectinload`/`joinedload`; testda so'rovlar soni tekshiriladi.
- **Bloklash**: qoldiqni kamaytirishda `SELECT ... FOR UPDATE`; bloklar qisqa, tartib doim bir xil
  (deadlock'ning oldini olish uchun mahsulotlar `id` bo'yicha tartiblab bloklanadi).
- **Indekslar**: har bir filtr/qidiruv uchun indeks; yangi og'ir so'rov `EXPLAIN ANALYZE` bilan tekshiriladi.
- **Og'ir ishlar** (oylik hisobot, eksport) — Celery'da, kassa yo'lida emas.

## 4. Qidiruv va filtr

| Holat | Yechim |
|---|---|
| Shtrix-kod | Unikal B-tree indeks, aniq moslik |
| Nom bo'yicha | `pg_trgm` GIN indeks, `ILIKE '%...%'` va o'xshashlik |
| Filtrlar (kategoriya, brend, sana, rol) | Kompozit indekslar |
| Katta ro'yxatlar (cheklar, jurnal) | Keyset (cursor) pagination |
| Kichik ro'yxatlar (brendlar, xodimlar) | Offset pagination |
| Standart tartib | Oxirgi qo'shilgan birinchi (`created_at DESC, id DESC`) |

## 5. Kod uslubi

- Python 3.11+, to'liq type hint'lar, `mypy --strict` modul darajasida.
- `ruff` — lint va format (black o'rniga).
- Nomlar: kodda ingliz tili; foydalanuvchiga ko'rinadigan xabarlar o'zbek tilida.
- Funksiya bir ishni qiladi; service funksiyasi 40–50 qatordan oshsa — bo'linadi.
- Sehrli raqamlar yo'q — konstantalar yoki sozlamalar.
- Loglar: `structlog`, JSON formatda, har birida `request_id`. Parol, token loglanmaydi.

## 6. Xavfsizlik

- Parollar: argon2 (pwdlib). Hech qachon ko'rsatilmaydi va loglanmaydi.
- Barcha kiruvchi ma'lumot Pydantic orqali; `dict` / `**kwargs` bilan model yangilash taqiqlangan.
- CORS: faqat ruxsat etilgan domenlar (`*` taqiqlangan).
- Superadmin kodda yaratilmaydi — faqat CLI.
- Maxfiy qiymatlar faqat `.env` da; `.env.example` da faqat namuna qiymatlar.

## 7. Git tartibi

- `main` — doim ishlaydigan holat. To'g'ridan-to'g'ri `main` ga commit qilinmaydi.
- Har bir vazifa — alohida branch: `feature/auth-login`, `fix/cart-total-rounding`.
- Commit xabarlari (Conventional Commits, ingliz tilida):
  - `feat(auth): add refresh token rotation`
  - `fix(kassa): round percent discount to 100 so'm`
  - `test(catalog): add concurrent product create test`
  - `docs: update DECISIONS with cart storage`
  - `refactor`, `chore`, `perf` — kerak bo'lganda
- Kichik, mantiqiy commit'lar. Bitta commit — bitta o'zgarish.
- Merge'dan oldin: testlar, ruff, mypy toza (keyinroq GitHub Actions avtomatik tekshiradi).

## 8. Migratsiyalar

- Har sxema o'zgarishi — `alembic revision --autogenerate -m "..."`, so'ng qo'lda tekshiriladi.
- Migratsiya ishlayotgan bazani buzmasligi kerak: ustun qo'shish → ma'lumot ko'chirish →
  eski ustunni keyingi relizda o'chirish.
- `downgrade` ham yoziladi.
