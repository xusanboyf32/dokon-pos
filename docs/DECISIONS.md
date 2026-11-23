# Qarorlar jurnali

Har bir qaror raqamlangan. Qaror o'zgarsa — eski yozuv o'chirilmaydi, "O'zgartirildi: #N" deb yangi qaror qo'shiladi.

## Umumiy va texnik

| # | Qaror | Sabab |
|---|---|---|
| D-001 | Backend faqat Python (FastAPI); frontend React + TypeScript | Tezlikni baza va tarmoq belgilaydi, til emas |
| D-002 | Modular monolith: `app/modules/<modul>/` (router, service, repository, models, schemas) | Har modul o'z joyida; keyin ajratish oson |
| D-003 | Paket boshqaruvi: uv + pyproject.toml *(taklif — tasdiqlanishi kerak)* | Tez, `uv.lock` bilan bir xil muhit |
| D-004 | PostgreSQL + SQLAlchemy 2.0 async + asyncpg + Alembic | Ishonchli, bloklash/constraint'lar, migratsiya |
| D-005 | Pul: `Numeric(14,2)` + `Decimal`, UZS | Float'da tiyinlar yo'qoladi |
| D-006 | Vaqt: `timestamptz`, UTC'da saqlash, Toshkent vaqtida ko'rsatish | Vaqt zonasi siljishi bo'lmaydi |
| D-007 | Redis: lockout/rate-limit, Celery broker. **Qoldiq keshlanmaydi** — doim bazadan | Spetsifikatsiya talabi |
| D-008 | Mahsulot nomi unikal (bitta harf farqi = yangi mahsulot); ID'lar `IDENTITY` bilan ketma-ket | Parallel qo'shishda ham xatosiz |
| D-009 | Biznes-ob'ektlar soft delete; pul/savdo yozuvlari hech qachon o'chirilmaydi | Tarix va audit |
| D-010 | Audit jurnali: faqat qo'shiladi, tahrirlanmaydi, o'chirilmaydi | Nazorat, kamomad tekshiruvi |
| D-011 | Muhim kassa ma'lumotlari serverda; tizim internet/lokal tarmoq orqali ishlaydi *(offline rejim — ochiq savol, Q-005)* | — |

## Rollar va ruxsatlar

| # | Qaror |
|---|---|
| R-001 | 6 ta qat'iy rol: superadmin, admin, kassir, omborchi, buxgalter, ta'minotchi. Yangi rol qo'shilmaydi |
| R-002 | Ruxsatlar kodda: Role → Permission xaritasi (`core/permissions.py`). Har bir xodimga alohida ruxsat berilmaydi |
| R-003 | Superadmin — bitta (dasturchi). Hammaga ko'rinmaydi (ro'yxatlarda ham, jurnalda ham) |
| R-004 | Superadmin hamma narsani, jumladan admin'larni boshqaradi |
| R-005 | Admin superadmin va boshqa admin'larni boshqara olmaydi; qolgan hamma narsani boshqaradi |
| R-006 | Kassir, omborchi, buxgalter, ta'minotchi — bir xil (eng past) boshqaruv darajasi |
| R-007 | Kategoriya, brend, birlik, mahsulot: superadmin, admin, omborchi teng to'liq CRUD; ro'yxatda "qo'shgan" ustuni |
| R-008 | Omborchi sotuv narxini ko'rmaydi; sotuv narxini buxgalter (va admin) belgilaydi |
| R-009 | Buxgalter: Seyf va Xarajatlarga to'liq kirish; Cheklar va Ombor qoldig'iga kirish yo'q |
| R-010 | Ta'minotchi: faqat ko'rish (Mening sahifam, Kirimlar, Qaytarishlar, To'lovlar, Balans) |

## Auth

| # | Qaror |
|---|---|
| A-001 | Uch jadval: `employees` (Xodimlar), `user_accounts` (Parollar), `auth_sessions` |
| A-002 | Lavozim (rol) xodimda saqlanadi; "Lavozimlar" bo'limi orqali beriladi |
| A-003 | Akkaunt yoki xodimga, yoki ta'minotchiga bog'lanadi (bittasiga — CHECK constraint) |
| A-004 | Access token 15 daqiqa, frontend fonda avtomatik yangilaydi (foydalanuvchi sezmaydi) |
| A-005 | Refresh token 24 soat, **logindan boshlab mutlaq** (rotation muddatni uzaytirmaydi), httpOnly cookie |
| A-006 | Refresh token rotation; eski token qayta ishlatilsa — akkauntning barcha sessiyalari yopiladi |
| A-007 | Parol yoki lavozim o'zgarsa `token_version` oshadi → barcha qurilmalardan chiqariladi. Tarix (savdo, oylik) saqlanadi |
| A-008 | Parol hech qachon ko'rsatilmaydi; admin faqat yangi parol qo'yadi |
| A-009 | Parol kamida 4 belgi |
| A-010 | Username kichik harfda, unikal, **qayta ishlatilmaydi** (ketgan xodimning username'i yangi xodimga berilmaydi) |
| A-011 | Lockout: 5 ketma-ket xato yoki 1 daqiqada 5+ urinish → 10 daqiqa blok. Shundan keyin 3 xato → doimiy blok (admin ochadi; superadmin'ni faqat server buyrug'i ochadi). Faol sessiyalar uzilmaydi |
| A-012 | Profil faqat ko'rish uchun; barcha ma'lumotlarni (telefon ham) admin kiritadi |
| A-013 | Superadmin kodda emas — CLI buyrug'i bilan yaratiladi |
| A-014 | Bir kassir bir vaqtda bitta joyda: yangi login eski sessiyani yopadi |
| A-015 | Bir kassada bir vaqtda bitta kassir; band kassaga boshqa kassir kira olmaydi; admin majburan bo'shatishi mumkin (jurnalga yoziladi) |

## Kassa va savdo

| # | Qaror |
|---|---|
| K-001 | Savatlar serverda (bazada) saqlanadi — F5, chiroq o'chishi, kompyuter almashishidan keyin ham saqlanadi |
| K-002 | Savatga qo'shilgan paytdagi narx qotadi; narx o'zgarsa savatdagi mahsulot eski narxda sotiladi |
| K-003 | Ikki xil umumiy chegirma: summa yoki foiz. 100% chegirma taqiqlangan |
| K-004 | 10 000 so'mdan katta chegirmalar admin ro'yxatida qizil bilan belgilanadi |
| K-005 | To'lov: naqd, karta, terminal, aralash; qarz faqat mijoz tanlanganda |
| K-006 | Chekdan keyin savat "Yakunlangan" bo'lib qoladi (qayta chop etish mumkin); kassir "Ekranni tozalash" bosadi. Chekni bekor qilish yo'q |
| K-007 | Qoldiq yo'q mahsulot kassada kulrang ko'rinadi |
| K-008 | Barcha kassalar uchun bitta umumiy do'kon qoldig'i |
| K-009 | Kg mahsulotlar: tarozi yorlig'idagi shtrix-kod og'irlikni o'z ichiga oladi |

## Ombor, buxgalteriya, oylik

| # | Qaror |
|---|---|
| W-001 | Tovar yo'li: ta'minotchi → ombor → omborchi do'konga jo'natadi → kassir qabul qiladi → umumiy do'kon qoldig'i |
| W-002 | Yaroqlilik muddatini omborchi kiritadi; muddati o'tgan tovar kirim narxida zarar sifatida hisobdan chiqariladi |
| W-003 | Ta'minotchiga qaytarish ombordan |
| B-001 | Buxgalter har kassadan ekrandagi summalarga qarab pul qabul qiladi; kamomad kassirning oyligidan ushlanadi; ortiqcha pul yozilmaydi |
| B-002 | Pul yo'li: kassa → buxgalter qabuli → seyf; har bosqich to'liq audit bilan |
| B-003 | Seyf: naqd/karta/terminal; xarajatlar (ijara, svet, gaz, ehson, oylik) seyfdan |
| P-001 | Oylik: ishlangan kunlar, kunlik soat, oylik, bonus, jarima — admin kiritadi |

## Kerak emas (ataylab chiqarilgan)

Avtomobil/avtoraqam modullari, operator va programist rollari, fiskal chek, smena moduli,
sodiqlik ballari, kredit limiti, ko'p tillilik, ulgurji narx, qarzni hisobdan chiqarish,
qo'lda qoldiq tuzatish, zaxira nusxa UI, SMS/eslatmalar.

---

## Ochiq savollar

| # | Savol | Variantlar |
|---|---|---|
| Q-001 | Foizli chegirmani yaxlitlash qoidasi | 100 yoki 1000 so'mga; yuqoriga / pastga / eng yaqiniga |
| Q-002 | Kassadagi parallel savatlar soni | 15 yoki 17 |
| Q-003 | Qisman qaytarish (3 kg dan 1 kg) | Ruxsat bormi? |
| Q-004 | Qarzga olingan tovar qaytsa | Pul qaytariladimi yoki qarzdan ayiriladimi? |
| Q-005 | Internet uzilganda kassa | Faqat online yoki offline-first |
| Q-006 | "Oylik" kassa summasi 30 kundan keyin | Taklif: ma'lumot o'chirilmaydi, ekrandagi raqam oxirgi qabuldan beri harakatlardan hisoblanadi |
