# Audit moduli

Bog'liq qarorlar: DECISIONS.md → AU-001…AU-020, D-010.

**Vazifasi:** kim, qachon, nima qildi, qanchadan qanchaga, nega — o'zgartirib bo'lmaydigan jurnal.
Log (structlog) — dasturchi uchun; audit — do'kon egasi uchun.

## 1. Asosiy qoidalar

| Qoida | Qaror |
|---|---|
| Faqat qo'shiladi: UPDATE / DELETE / TRUNCATE baza triggeri bilan taqiqlangan | AU-010 |
| Amal bilan BITTA tranzaksiyada yoziladi; audit yozilmasa — amal ham bekor (fail-closed) | AU-009 |
| Faqat katalogdagi amallar (`AuditAction`); umumiy `*.updated` yo'q | AU-008 |
| Muhimlik katalogdan: info / important / critical | AU-005 |
| Faqat o'zgargan maydonlar `{"maydon": [eski, yangi]}`; parol/hash/token hech qachon | AU-002 |
| Shaxsiy ma'lumotlar to'liq qiymati bilan | AU-013 |
| Sezgir amallarda sabab majburiy (hozir: blokni ochish) | AU-006 |
| Har bir xato login yozilmaydi — faqat blok | AU-004 |
| Oddiy savdo yozilmaydi (chekning o'zi hujjat) | AU-007 |
| Bitta biznes-amal = bitta yozuv | AU-011 |
| Admin superadminga oid yozuvlarni ko'rmaydi | AU-001 |
| Doimiy saqlanadi | AU-003 |

## 2. Jadval: audit_events

| Ustun | Tur | Izoh |
|---|---|---|
| id | bigint identity | |
| occurred_at | timestamptz, `now()` | tranzaksiya vaqti |
| actor_account_id | FK → user_accounts, RESTRICT, null | null — "Tizim" |
| actor_role | varchar + CHECK, null | amal paytidagi rol |
| action | varchar(64) + CHECK format `modul.amal` | ro'yxat kodda (catalog.py) |
| severity | varchar + CHECK | info / important / critical |
| entity_type, entity_id | varchar(32), bigint | ("employee", 12), ("account", 7) |
| changes | jsonb, null | SQL NULL (JSON `null` emas) |
| reason | varchar(500), null, CHECK bo'sh emas | |
| superadmin_only | boolean | |
| request_id, ip, user_agent | varchar, null | so'rov kontekstidan (ContextVar) |
| kassa_id | bigint, null | FK 7-bosqichda |

Indekslar: `(occurred_at, id)`, `(entity_type, entity_id, occurred_at)`, `(actor_account_id, occurred_at)`.

## 3. Yozish (kod ichida)

```python
await audit.record(
    session,
    actor=current_user,              # None → "Tizim"
    action=AuditAction.EMPLOYEE_SALARY_CHANGED,
    entity=("employee", employee.id),
    changes={"salary": (old, new)},  # o'zgarmaganlar o'zi tashlanadi
    reason=None,                     # katalog majburiy desa — ReasonRequiredError
    concerns_superadmin=False,
)
await session.commit()               # amal bilan birga
```

## 4. Katalog (hozirgi amallar)

| Amal | Muhimlik | Kim |
|---|---|---|
| auth.login_success | info | o'zi |
| auth.locked_permanent | critical | Tizim |
| auth.token_reuse_detected | critical | Tizim |
| auth.locked_temporary | important | *(eski tizim, faqat o'qish uchun)* |
| account.created / password_reset / deleted | important | admin |
| account.unlocked | critical, **sabab majburiy** | admin |
| account.superadmin_created / superadmin_unlocked | critical | Tizim (CLI) |
| employee.created / personal_info_changed / photo_changed | info | admin |
| employee.role_changed / salary_changed / archived / restored | important | admin |
| employee.deleted | critical | admin |

## 5. Endpoint'lar

| Metod | URL | Kim | Tavsif |
|---|---|---|---|
| GET | /api/v1/audit-logs | superadmin, admin | jurnal; cursor (`limit` ≤ 100, `cursor`); filtrlar: `date_from/to` (Toshkent), `actor_employee_id`, `module`, `action` (bir nechta), `min_severity` (standart important), `entity_type`, `entity_id` |
| GET | /api/v1/employees/{id}/history | superadmin, admin | xodim va uning loginiga oid yozuvlar; `include_logins` (standart false) |

Har yozuvda `summary` — tayyor o'zbekcha gap (AU-017):
*"Ali Valiyev: maosh o'zgardi — Anvar Karimov. Maosh: 3 000 000 → 3 500 000"*.
Ismlar `accounts/names.py` orqali, bitta so'rov bilan (N+1 yo'q).

## 6. Testlar
- Katalog: har amalda spec, format, generic nom yo'q.
- Baza: UPDATE/DELETE/TRUNCATE rad etiladi; CHECK'lar.
- `record()`: maydonlar, Tizim, superadmin yashirinligi, sabab, `changes` SQL NULL, rollback birga.
- Har sezgir amal uchun "amal → aynan shu yozuv" (AU-012).
- API: ruxsat, standart filtr, filtrlar birga, cursor bo'shliqsiz, buzuq cursor 422, superadmin yashirin.
