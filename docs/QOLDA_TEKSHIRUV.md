# Qo'lda tekshiruv ro'yxati (0–3-bosqichlar)

Har bir holatni o'zingiz yaratib ko'ring va natijani belgilang: `[ ]` → `[x]`.
Frontend tayyor bo'lgach ham shu ro'yxat bo'yicha qayta o'ting — hech narsa unutilmasin.

Xabarlar **koddan aynan ko'chirilgan**. Kod o'zgarsa — bu fayl ham yangilanadi.

Jurnal matnlari jadvalda qisqartirilgan. To'liq shakli doim:
**"Kim: amal — kimga. Tafsilot. Sabab: …"** (masalan: "Ali Valiyev: maosh o'zgardi — Anvar Karimov. Maosh: 3 000 000 → 3 500 000").

Xato javobi doim bir xil shaklda keladi:
```
{"error": {"code": "KOD", "message": "Xabar", "details": {...}, "request_id": "..."}}
```

---

## 0. Tayyorgarlik

- [ ] Server: `uv run uvicorn app.main:app --reload` → http://localhost:8000/docs
      (8000 band bo'lsa: `--port 8001`)
- [ ] `GET /health` → `{"status": "ok", "database": "ok"}`
- [ ] Superadmin yo'q bo'lsa: `uv run python -m app.cli create-superadmin`
- [ ] Sinov uchun yarating: 1 ta **admin** xodim + login, 2 ta **kassir** xodim + login
- [ ] Swagger'da token: `POST /auth/login` → `access_token` → **Authorize 🔒**

Redis va Docker **kerak emas** (A-032).

---

## 1. Kirish (auth)

| # | Holat | Kutilgan natija | Jurnalda | 🔔 |
|---|---|---|---|---|
| 1.1 | [ ] To'g'ri login va parol | 200, `access_token`, `role` | 🟢 info: "X: tizimga kirdi" | — |
| 1.2 | [ ] Username KATTA harf bilan (`ANVAR`) | 200 — katta-kichik harf farqsiz (A-016) | 🟢 | — |
| 1.3 | [ ] Xato parol | 401 `INVALID_CREDENTIALS` — "Login yoki parol xato" | **yo'q** (faqat log, AU-004) | — |
| 1.4 | [ ] Mavjud bo'lmagan username, 15 marta | Har safar 401 `INVALID_CREDENTIALS` — "Login yoki parol xato". Blok **chiqmaydi** | yo'q | — |
| 1.5 | [ ] 9 marta xato parol | Har safar 401; hali kira oladi. Parollar ro'yxatida `failed_attempts: 9` | yo'q | — |
| 1.6 | [ ] **10-chi** xato parol | 423 `ACCOUNT_LOCKED` — "Hisob bloklandi, administratorga murojaat qiling" | 🔴 critical: "Tizim: hisob bloklandi — login «anvar» (Anvar Karimov)" | **+1**: "login «anvar» (Anvar Karimov) bloklandi" |
| 1.7 | [ ] Blokda **to'g'ri** parol | 423 `ACCOUNT_LOCKED` (o'sha xabar) | yo'q | o'zgarmaydi |
| 1.8 | [ ] 10 daqiqa, 1 soat kuting | Blok **o'zi ochilmaydi** (A-032) | — | ochiq turadi |
| 1.9 | [ ] 5 xato → to'g'ri parol → yana 9 xato | Blok **bo'lmaydi** (to'g'ri parol hisoblagichni 0 qiladi) | — | — |
| 1.10 | [ ] Admin ishlab turibdi, keyin uning logini bloklanadi | Ochiq sessiya **ishlashda davom etadi**, faqat yangi kirish to'xtaydi | 🔴 | +1 (admin blokini faqat superadmin ochadi, A-019) |
| 1.11 | [ ] Kassir 1-kompyuterda kirgan, 2-kompyuterdan kiradi | 1-dagi eski token → 401 `SESSION_INVALID` — "Sessiya yaroqsiz, qaytadan kiring" (A-014) | 🟢 ikkita kirish | — |
| 1.12 | [ ] Token'siz himoyalangan manzil | 401 `UNAUTHORIZED` — "Tizimga kirish talab qilinadi" | — | — |
| 1.13 | [ ] Kassir admin bo'limiga (`GET /employees`, `/accounts`, `/audit-logs`, `/problems`) | 403 `FORBIDDEN` — "Bu amal uchun ruxsat yo'q" | — | — |
| 1.14 | [ ] `POST /auth/logout`, keyin o'sha token | 204, keyin 401 `SESSION_INVALID` | — | — |
| 1.15 | [ ] Eski refresh token qayta ishlatildi (o'g'irlik) | 401 `REFRESH_TOKEN_REUSED` — "Xavfsizlik sababli barcha qurilmalardan chiqarildingiz, qaytadan kiring" | 🔴 "Token qayta ishlatildi (o'g'irlik)" | — |
| 1.16 | [ ] `GET /auth/me` | `account_id`, `role`, `employee_id` | — | — |
| 1.17 | [ ] `GET /auth/me/positions` (kassir) | Faqat **o'zining** lavozim/maosh davrlari, yangisi tepada (AU-020) | — | — |
| 1.18 | [ ] `GET /auth/me/positions` (superadmin) | `[]` | — | — |

**1.15 izoh:** refresh token cookie'da — Swagger'da qiyin. Frontend tayyor bo'lgach tekshiriladi.

---

## 2. Blokni ochish

| # | Holat | Kutilgan natija | Jurnalda | 🔔 |
|---|---|---|---|---|
| 2.1 | [ ] `POST /accounts/{id}/unlock` — body'siz yoki `{"reason": ""}` yoki `{"reason": "   "}` | 422 `VALIDATION_ERROR` — "Ma'lumotlar noto'g'ri", `details.fields` da `reason` | yo'q | o'zgarmaydi |
| 2.2 | [ ] `{"reason": "Parolini unutgan"}` | 200, `state: "active"`, `failed_attempts: 0` | 🔴 "Ali Valiyev: blok ochildi — login «anvar» (Anvar Karimov). Doimiy blok: ha → yo'q. Sabab: Parolini unutgan" | **−1**; `status=resolved` ro'yxatida: `resolution: "auto"`, `resolved_by` — admin |
| 2.3 | [ ] Blok ochilgach to'g'ri parol | 200 | 🟢 | — |
| 2.4 | [ ] Admin boshqa **admin**ning blokini ochmoqchi | 403 `FORBIDDEN` — "Bu lavozimdagi xodimning loginini boshqarishga ruxsatingiz yo'q" | — | — |
| 2.5 | [ ] Superadmin admin'ning blokini ochadi | 200 | 🔴 (superadmin amali — admin ko'rmaydi) | −1 |
| 2.6 | [ ] Superadmin bloklandi → `uv run python -m app.cli unlock-superadmin` | "✅ Superadmin blokdan chiqarildi: ..." | 🔴 "Tizim: superadmin bloki ochildi" (faqat superadmin ko'radi) | yopiladi, `resolved_by: null` (Tizim) |
| 2.7 | [ ] Superadmin bloklanganda admin 🔔 ga qaraydi | Admin **ko'rmaydi** (son ham o'zgarmaydi) | — | — |

---

## 3. Xodimlar

| # | Holat | Kutilgan natija | Jurnalda |
|---|---|---|---|
| 3.1 | [ ] Xodim qo'shish (forma + rasm) | 201 | 🟢 info: "Xodim qo'shildi. Ism: …; Familiya: …; Telefon: +998 90 …; Lavozim: Kassir; Maosh: 3 000 000" |
| 3.2 | [ ] Band telefon | 409 `PHONE_TAKEN` — "Bu telefon raqami boshqa xodimga tegishli" | — |
| 3.3 | [ ] Noto'g'ri telefon (`123`) | 422 `VALIDATION_ERROR`, maydon xabari: "Telefon raqami noto'g'ri. Namuna: 90 002 12 21" | — |
| 3.4 | [ ] Telefon har xil yozuvda: `90 002 12 21`, `+998 (90) 002-12-21` | Qabul qilinadi, bazada `+998900021221` (E-011) | — |
| 3.5 | [ ] Yoshi 5 dan kichik yoki 100 dan katta | 422, "Xodimning yoshi 5 dan 100 gacha bo'lishi kerak" | — |
| 3.6 | [ ] Rasm GIF, matn fayl yoki 5 MB dan katta | 400 `INVALID_PHOTO` — "Rasm JPG yoki PNG formatida, 5 MB gacha bo'lishi kerak" | — |
| 3.7 | [ ] Familiyani o'zgartirish | 200 | 🟢 "Shaxsiy ma'lumotlar o'zgardi. Familiya: Karimov → Valiyev" |
| 3.8 | [ ] O'sha qiymatni qayta yuborish (hech narsa o'zgarmadi) | 200 | **yozuv yo'q** |
| 3.9 | [ ] Rasmni almashtirish | 200, yangi `photo_url` | 🟢 "Rasm almashtirildi" |
| 3.10 | [ ] Lavozim/maosh — hech narsa o'zgarmagan | 400 `NOTHING_CHANGED` — "Lavozim ham, maosh ham o'zgarmagan" | — |
| 3.11 | [ ] Lavozim sanasi joriy davrdan oldin | 400 `INVALID_POSITION_DATE` — "Yangi lavozim sanasi joriy lavozim boshlangan sanadan oldin bo'lishi mumkin emas" | — |
| 3.12 | [ ] Faqat maosh oshdi | 200; xodim tizimdan **chiqarilmaydi** | 🟡 "Maosh o'zgardi … Maosh: 3 000 000 → 3 500 000" |
| 3.13 | [ ] Lavozim o'zgardi (kassir → omborchi) | 200; xodim **barcha qurilmalardan chiqariladi** | 🟡 "Lavozim o'zgardi … Lavozim: Kassir → Omborchi; Maosh: …" (bitta yozuv) |
| 3.14 | [ ] Arxivlash | 200; login ishlamaydi (401 `INVALID_CREDENTIALS`), sessiyalar yopiladi | 🟡 "Xodim arxivlandi" |
| 3.15 | [ ] Arxivlangan xodimga login yaratish | 400 `EMPLOYEE_ARCHIVED` — "Xodim arxivda. Avval arxivdan qaytaring" | — |
| 3.16 | [ ] Arxivlangan xodim lavozimini o'zgartirish | 400 `EMPLOYEE_ARCHIVED` | — |
| 3.17 | [ ] Qayta arxivlash | 200 | **yozuv yo'q** |
| 3.18 | [ ] Arxivdan qaytarish | 200; o'sha login yana ishlaydi | 🟡 "Xodim arxivdan qaytarildi" |
| 3.19 | [ ] O'chirish — logini hech qachon bo'lmagan | 204; butunlay o'chadi; kartochka 404 | 🔴 "Xodim o'chirildi. Ism: Anvar → —; …" |
| 3.20 | [ ] O'chirish — logini bo'lgan | 204; "O'chirilgan xodim #12" bo'lib qoladi, ro'yxatlarda yo'q, telefon bo'shaydi | 🔴 "Xodim o'chirildi. Ism: Anvar → O'chirilgan; …" |
| 3.21 | [ ] Admin boshqa adminni tahrirlash/o'chirish | 403 `FORBIDDEN` — "Bu lavozimdagi xodimni boshqarishga ruxsatingiz yo'q" | — |
| 3.22 | [ ] Xodimga **superadmin** lavozimini berish | 403 `FORBIDDEN` — "Bu lavozimni xodimga berib bo'lmaydi" | — |
| 3.23 | [ ] Mavjud bo'lmagan xodim | 404 `NOT_FOUND` — "Xodim topilmadi" | — |
| 3.24 | [ ] `GET /roles` (admin) | 5 ta lavozim, superadmin **ko'rinmaydi** | — |

### Xodim "Tarix" tabi — `GET /employees/{id}/history`

- [ ] Xodimning o'ziga **va** loginiga oid yozuvlar bitta ro'yxatda, yangisi tepada (AU-019)
- [ ] Boshqa xodimning yozuvlari aralashmaydi
- [ ] Tizimga kirishlar standart **yashirin**; `include_logins=true` — ko'rinadi
- [ ] Muhimlikdan qat'i nazar hammasi ko'rinadi (info ham)
- [ ] `limit=3` → `next_cursor` bilan keyingi sahifa
- [ ] O'chirilgan yoki yo'q xodim → 404 "Xodim topilmadi"

---

## 4. Parollar (loginlar)

| # | Holat | Kutilgan natija | Jurnalda |
|---|---|---|---|
| 4.1 | [ ] Login yaratish | 201; javobda parol **yo'q** | 🟡 "Login yaratildi. Login: vali; Xodim: 12" |
| 4.2 | [ ] Username `ab`, `vali!`, kirill harf | 400 `INVALID_USERNAME` — "Username 3–50 belgi: lotin harf, raqam, pastki chiziq (_) va nuqta (.)" | — |
| 4.3 | [ ] Parol 3 belgi yoki 65 belgi | 400 `INVALID_PASSWORD` — "Parol 4–64 belgidan iborat bo'lishi kerak" | — |
| 4.4 | [ ] "Yangi parol" ≠ "Takrorlang" | 400 `PASSWORD_MISMATCH` — "Parollar bir xil emas" | — |
| 4.5 | [ ] Band username (o'chirilgan loginniki ham) | 409 `USERNAME_TAKEN` — "Bu username band (o'chirilgan loginlar nomi ham qayta berilmaydi)" | — |
| 4.6 | [ ] Faol logini bor xodimga ikkinchi login | 409 `ACCOUNT_EXISTS` — "Bu xodimning faol logini bor. Parolni almashtiring yoki avval loginni o'chiring" | — |
| 4.7 | [ ] Parolni almashtirish | 200; xodim **barcha qurilmalardan chiqadi** | 🟡 "Parol almashtirildi" — **parolning o'zi jurnalda yo'q** |
| 4.8 | [ ] Loginni o'chirish | 204 | 🟡 "Login o'chirildi" |
| 4.9 | [ ] O'chirilgan loginga parol yoki blok ochish | 400 `ACCOUNT_DELETED` — "Login o'chirilgan. Kerak bo'lsa, xodimga yangi login yarating" | — |
| 4.10 | [ ] Ro'yxat: holatlar | `active` / `locked` / `deleted`; har qatorda `failed_attempts` (masalan 7) | — |
| 4.11 | [ ] Ro'yxatda superadmin | **ko'rinmaydi** | — |
| 4.12 | [ ] `status=locked` filtri | faqat bloklanganlar | — |

---

## 5. Audit jurnali — `GET /audit-logs`

- [ ] Standart (`min_severity=important`) — kirishlar **ko'rinmaydi**
- [ ] `min_severity=info` — kirishlar ham ko'rinadi
- [ ] `min_severity=critical` — faqat bloklar, blok ochish, o'chirish, o'g'irlik
- [ ] `actor_employee_id` — faqat shu xodim **qilgan** amallar ("Amallari" tugmasi)
- [ ] `module=account` / `employee` / `auth`
- [ ] `action` bir nechta: `employee.archived` + `employee.restored`
- [ ] `entity_type=employee&entity_id=12`
- [ ] `date_from`, `date_to` — **Toshkent** kuni bo'yicha (23:30 dagi yozuv o'sha kunga tushadi)
- [ ] Filtrlar birga ishlaydi (VA)
- [ ] `limit=1` → `next_cursor` → keyingi yozuv; oxirida `has_more: false`, `next_cursor: null`
- [ ] Buzuq `cursor` → 422 `INVALID_CURSOR` — "Sahifa belgisi (cursor) noto'g'ri"
- [ ] Admin superadminning amallarini **ko'rmaydi**; superadmin hammasini ko'radi
- [ ] `occurred_at` UTC'da (`...Z`) — frontend +5 soat qilib ko'rsatadi
- [ ] Bazani himoya: psql'da `UPDATE audit_events SET reason='x';` →
      xato "audit_events faqat qo'shiladi: UPDATE taqiqlangan" (DELETE, TRUNCATE ham)

---

## 6. 🔔 Muammolar — `GET /problems/count`, `GET /problems`

- [ ] Boshida `{"open": 0}`
- [ ] Kassir 10 marta xato → `{"open": 1}`
- [ ] Ro'yxatda: `title` "login «anvar» (Anvar Karimov) bloklandi", `type_label` "Akkaunt bloklandi",
      `action`: `{"kind": "unlock_account", "label": "Blokni ochish", "account_id": …}`
- [ ] Blok ochildi → `{"open": 0}`; standart ro'yxat bo'sh
- [ ] `status=resolved` — yopilgan muammo: `resolution: "auto"`, `resolved_by` — kim ochgan, `action: null`
- [ ] Yana bloklandi → **yangi** qator (eski yopilgani tarixda qoladi); `status=all` — ikkalasi
- [ ] `employee_id`, `type`, `date_from/to` filtrlari
- [ ] `size=1` → `total`, `pages` to'g'ri
- [ ] Superadmin muammosi admin uchun **ko'rinmaydi** (son ham)
- [ ] Kassir → 403

---

## 7. Frontend uchun eslatmalar (unutmaslik kerak)

- [ ] 🔔 soni — `GET /problems/count` ni har 30–60 soniyada yangilash
- [ ] Muammo yonida tezkor tugma (`action`) → "Blokni ochish" oynasi, **sabab maydoni majburiy**
- [ ] Parollar ro'yxatida "7/10 xato urinish" (`failed_attempts`) — blokka yaqinlashganini ko'rsatish
- [ ] 423 xatosi — login sahifasida aniq ko'rsatish: "Hisob bloklandi, administratorga murojaat qiling"
- [ ] Audit: `summary` — bitta qator; `severity` → 🟢 🟡 🔴; "Yana yuklash" (`has_more`, `next_cursor`)
- [ ] Barcha vaqtlar UTC'dan **Toshkent**ga (+5) o'girib ko'rsatiladi (D-006)
- [ ] Xodim kartochkasi: "Tarix" tabi + "Kirishlarni ko'rsatish" katakchasi + "Amallari" tugmasi
- [ ] "Mening sahifam": lavozim/maosh tarixi (`/auth/me/positions`)
- [ ] Access token 15 daqiqa — frontend fonda o'zi yangilaydi (A-004)
- [ ] Pul ko'rinishi: "3 500 000 so'm" (bazada "3500000.00")

---

## Natija

Sana: ____________  Tekshirdi: ____________

Topilgan muammolar:
1.
2.
3.
