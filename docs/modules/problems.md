# Muammolar moduli (🔔)

Bog'liq qarorlar: DECISIONS.md → N-001…N-009, A-032.

**Vazifasi:** admin bajarishi kerak bo'lgan ishlar ro'yxati. Jurnal emas, xabar lentasi emas.

## 1. Besh qoida (N-008)

1. **Faqat harakat talab qiladigan narsa.** "Admin nima qilishi kerak?" — javob yo'q bo'lsa, faqat audit.
2. **Bitta tezkor tugma** (`action`), masalan "Blokni ochish".
3. **Sabab bartaraf etilsa — o'zi yopiladi.** Qo'lda yopish faqat odam qarori kerak joyda.
4. **Spam yo'q:** takrorlansa — yangi qator emas, `occurrences` +1 (N-002).
5. **Tarix saqlanadi:** yopilgan o'chirilmaydi — kim, qachon, qanday yopgani qoladi.

## 2. Turlar

| Tur | Admin nima qiladi | Qanday yopiladi | Holat |
|---|---|---|---|
| `account_locked` — Akkaunt bloklandi | Blokni ochadi | o'zi (blok ochilganda) | ✅ |
| Katta chegirma | Chekni ko'radi | qo'lda (N-009) | Kassa |
| Kamomad | Qabulni tekshiradi | qo'lda | Buxgalteriya |
| Qoldiq tugayapti | Buyurtma beradi | o'zi | Ombor |
| Yaroqlilik muddati yaqin | Sotadi / hisobdan chiqaradi | o'zi | Ombor |

## 3. Jadval: problems

| Ustun | Tur | Izoh |
|---|---|---|
| id | bigint identity | |
| type | varchar + CHECK | `ProblemType` |
| status | varchar + CHECK | open / resolved |
| entity_type, entity_id | varchar, bigint | tezkor tugma shu orqali |
| subject_employee_id | FK → employees, SET NULL | "Xodim" filtri |
| group_key | varchar(100) | `account_locked:account:7`; **qisman unikal indeks** `WHERE status='open'` |
| occurrences | int ≥ 1 | |
| first_occurred_at, last_occurred_at | timestamptz | |
| resolved_at, resolved_by_account_id, resolution, resolution_note | | `resolution`: auto / reviewed; CHECK holat bilan mos |
| superadmin_only | boolean | admin ko'rmaydi |

Ochish — `INSERT … ON CONFLICT DO UPDATE` (upsert): ikki so'rov bir vaqtda kelsa ham bitta qator.

## 4. Hayot sikli (akkaunt bloklandi)

```
10-chi xato parol (A-032) → locked_at + audit 🔴 + report_account_locked()  — bitta tranzaksiya
admin "Blokni ochish" + sabab → audit 🔴 + resolve_account_locked(actor)  — resolution=auto
superadmin CLI unlock          → resolve_account_locked(None)              — resolved_by=null (Tizim)
```

## 5. Endpoint'lar

| Metod | URL | Kim | Tavsif |
|---|---|---|---|
| GET | /api/v1/problems/count | superadmin, admin | `{"open": N}` — 🔔 raqami |
| GET | /api/v1/problems | superadmin, admin | `status` (open — standart / resolved / all), `type`, `employee_id`, `date_from/to`, `page`, `size`; eng yangisi tepada |

## 6. Testlar
- Blok → muammo ochiladi (sarlavha, tugma, xodim); blok ochilsa → yopiladi, kim ochgani.
- Qayta blok → yangi qator; guruhlash → `occurrences`.
- Superadmin muammosi admin uchun yashirin; CLI ochganda `resolved_by=null`.
- Filtrlar, sahifalash, kassir 403.
