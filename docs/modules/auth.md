# Auth moduli

Bog'liq qarorlar: DECISIONS.md → R-001…R-006, A-001…A-015.

## 1. Bo'limlar (frontend menyusi)

| Bo'lim | Vazifasi | Backend resursi |
|---|---|---|
| Rollar | 6 ta rol ro'yxati (faqat ko'rish) | `GET /roles` |
| Xodimlar | Xodim qo'shish/tahrirlash: ism, familiya, tug'ilgan sana, jins, telefon, lavozim, maosh, rasm | `employees` |
| Lavozimlar | Xodimga rol berish | `PUT /employees/{id}/role` |
| Parollar | Xodimga (yoki ta'minotchiga) username va parol berish, parolni almashtirish, blokni ochish | `accounts` |
| Mening sahifam | Har bir foydalanuvchi o'z profilini ko'radi (faqat ko'rish) | `GET /auth/me` |

## 2. Jadvallar

### employees
Hamma maydon majburiy (E-001).

| Ustun | Tur | Izoh |
|---|---|---|
| id | bigint identity | |
| first_name, last_name | varchar(100) | |
| birth_date | date | yosh shundan hisoblanadi |
| gender | varchar + CHECK (male/female) | |
| phone | varchar(13), unique | `+998XXXXXXXXX` formatida saqlanadi |
| role | varchar + CHECK | superadmin, admin, kassir, omborchi, buxgalter (ta'minotchi xodim emas) |
| salary | numeric(14,2) + CHECK ≥ 0 | oylik maosh |
| photo_path | varchar(255) | diskdagi fayl yo'li |
| archived_at | timestamptz, null | arxivlangan bo'lsa (E-005) |
| created_at, updated_at | timestamptz | |

### user_accounts
| Ustun | Tur | Izoh |
|---|---|---|
| id | bigint identity | |
| employee_id | bigint → employees, unique, null | |
| supplier_id | bigint → suppliers, unique, null | CHECK: aynan bittasi to'ldirilgan |
| username | varchar(50), unique | doim kichik harfda; qayta ishlatilmaydi (o'chirilgan akkaunt ham username'ni band qilib turadi) |
| password_hash | varchar | argon2 |
| token_version | integer, default 0 | parol/rol o'zgarsa +1 |
| failed_attempts_after_lock | smallint | 10 daqiqalik blokdan keyingi xatolar |
| is_locked | boolean | doimiy blok |
| last_login_at | timestamptz, null | |
| created_at, updated_at, deleted_at | timestamptz | |

### auth_sessions
| Ustun | Tur | Izoh |
|---|---|---|
| id | uuid | |
| account_id | bigint → user_accounts | |
| refresh_token_hash | varchar, unique | token o'zi saqlanmaydi |
| family_id | uuid | rotation zanjiri; o'g'irlik aniqlansa butun oila bekor qilinadi |
| kassa_id | bigint, null | kassir qaysi kassada |
| ip, user_agent | varchar | |
| created_at | timestamptz | |
| absolute_expires_at | timestamptz | login + 24 soat, rotation'da o'zgarmaydi |
| revoked_at | timestamptz, null | |
| revoked_reason | varchar, null | logout / rotated / password_changed / reuse_detected / new_login / admin |

## 3. Endpoint'lar

| Metod | URL | Kim | Tavsif |
|---|---|---|---|
| POST | /api/v1/auth/login | hamma | username + parol → access token + refresh cookie + rol |
| POST | /api/v1/auth/refresh | cookie egasi | yangi access + yangi refresh (rotation) |
| POST | /api/v1/auth/logout | login bo'lgan | joriy sessiyani yopadi |
| GET | /api/v1/auth/me | login bo'lgan | o'z profili |
| GET/POST | /api/v1/employees | superadmin, admin | ro'yxat (qidiruv, filtr: rol, sana) / yaratish |
| GET/PATCH/DELETE | /api/v1/employees/{id} | superadmin, admin | |
| PUT | /api/v1/employees/{id}/role | superadmin, admin | lavozim berish/o'zgartirish |
| GET/POST | /api/v1/accounts | superadmin, admin | parollar ro'yxati (qidiruv: ism, rol; filtr: rol, sana) / akkaunt yaratish |
| POST | /api/v1/accounts/{id}/reset-password | superadmin, admin | yangi parol |
| POST | /api/v1/accounts/{id}/unlock | superadmin, admin | doimiy blokni ochish |
| DELETE | /api/v1/accounts/{id} | superadmin, admin | akkauntni o'chirish (kira olmaydi, tarix qoladi) |

Admin uchun barcha endpoint'larda: superadmin ko'rinmaydi va o'zgartirilmaydi; admin akkauntlari o'zgartirilmaydi.

## 4. Oqimlar

### Login
1. Username kichik harfga o'tkaziladi.
2. Akkaunt doimiy bloklangan → 423.
3. Redis'da vaqtinchalik blok bor → 423 (`locked_until` bilan).
4. Parol tekshiriladi (akkaunt topilmasa ham soxta hash tekshiriladi — vaqt bo'yicha username aniqlanmasligi uchun).
5. Xato → Redis hisoblagichlari oshadi; chegaradan oshsa blok qo'yiladi → 401.
6. To'g'ri → hisoblagichlar tozalanadi; kassir bo'lsa eski sessiyalari yopiladi (A-014);
   yangi sessiya; access token (15 daq) + refresh cookie (24 soat) + rol qaytadi.
7. Audit: `auth.login_success` / `auth.login_failed` / `auth.locked`.

### Har so'rov
Access token tekshiriladi → akkaunt mavjud, o'chirilmagan, bloklanmagan → xodim faol →
`token_version` mos. Aks holda 401.

### Refresh
Cookie'dagi token hash bo'yicha topiladi →
- bekor qilingan sessiya qayta ishlatilsa → butun oila bekor, 401 (`reuse_detected`, audit);
- `absolute_expires_at` o'tgan bo'lsa → 401;
- aks holda eski sessiya `rotated`, yangi sessiya (xuddi shu `family_id`, xuddi shu `absolute_expires_at`).

### Admin amallari
| Amal | Natija |
|---|---|
| Parolni almashtirish | token_version +1, barcha sessiyalar yopiladi, audit |
| Lavozimni o'zgartirish | token_version +1, barcha sessiyalar yopiladi, audit |
| Akkauntni o'chirish | sessiyalar yopiladi; xodim va tarix qoladi |
| Xodimni o'chirish | akkaunt ham o'chiriladi; tarix qoladi |
| Blokni ochish | is_locked=false, hisoblagichlar tozalanadi, audit |

## 5. Lockout (Redis)

| Kalit | TTL | Ma'nosi |
|---|---|---|
| `auth:fail:{username}` | — (muvaffaqiyatda tozalanadi) | ketma-ket xatolar |
| `auth:rate:{username}` | 60 s | oxirgi daqiqadagi urinishlar |
| `auth:lock:{username}` | 600 s | vaqtinchalik blok |

5 ketma-ket xato yoki daqiqada 5+ urinish → `auth:lock` (10 daq). Blokdan keyin yana 3 xato →
bazada `is_locked = true` (doimiy). Superadmin doimiy blokini faqat `python -m app.cli unlock-superadmin` ochadi.

## 6. Testlar (minimal ro'yxat)
- To'g'ri/xato login; username katta-kichik harf.
- 5 xato → 423; 10 daqiqadan keyin ochiladi; yana 3 xato → doimiy blok.
- Refresh rotation; eski refresh qayta ishlatilsa barcha sessiyalar yopiladi.
- Refresh 24 soatdan keyin ishlamaydi, rotation muddatni uzaytirmaydi.
- Parol o'zgargach eski access token 401.
- Kassir ikkinchi joyda kirsa birinchi sessiya yopiladi.
- Admin: admin/superadmin'ni o'zgartira olmaydi, superadmin ro'yxatda ko'rinmaydi.
- O'chirilgan akkauntning username'i qayta ishlatib bo'lmaydi.
- Parallel ikki refresh — faqat bittasi muvaffaqiyatli.
