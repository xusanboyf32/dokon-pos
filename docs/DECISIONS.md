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
| A-008 | Parol hech qachon ko'rsatilmaydi; admin faqat yangi parol qo'yadi (dastlabki promptdagi "ko'z tugmasi" talabi xavfsizlik sababli bekor qilindi) |
| A-009 | Parol kamida 4 belgi (batafsil: A-017) |
| A-010 | Username kichik harfda, unikal, **qayta ishlatilmaydi** (ketgan xodimning username'i yangi xodimga berilmaydi) |
| A-011 | Lockout: 5 ketma-ket xato yoki 1 daqiqada 5+ urinish → 10 daqiqa blok. Shundan keyin 3 xato → doimiy blok (admin ochadi; superadmin'ni faqat server buyrug'i ochadi). Faol sessiyalar uzilmaydi |
| A-012 | Profil faqat ko'rish uchun; barcha ma'lumotlarni (telefon ham) admin kiritadi |
| A-013 | Superadmin kodda emas — CLI buyrug'i bilan yaratiladi |
| A-014 | Bir kassir bir vaqtda bitta joyda: yangi login eski sessiyani yopadi |
| A-015 | Bir kassada bir vaqtda bitta kassir; band kassaga boshqa kassir kira olmaydi; admin majburan bo'shatishi mumkin (jurnalga yoziladi) |
| A-016 | Username: 3–50 belgi, lotin harf, raqam, `_` va `.`; katta-kichik harf farqsiz |
| A-017 | Parol: 4–64 belgi, katta-kichik harf farqlanadi; berishda "Yangi parol" + "Takrorlang" — mos kelmasa saqlanmaydi |
| A-018 | Blok vaqtidagi urinishlar hisoblanmaydi va blokni uzaytirmaydi; blok vaqtida to'g'ri parol ham rad etiladi. Xabarlar: "Hisob vaqtincha bloklandi, 10 daqiqadan keyin urinib ko'ring" / "Hisob bloklandi, administratorga murojaat qiling" |
| A-019 | Blokni ochish: past rollarni — admin va superadmin; admin'ni — faqat superadmin; superadmin'ni — faqat server buyrug'i. Har blok va ochish jurnalga |
| A-020 | "Rollar / Lavozimlar" bo'limi faqat ro'yxat (nom, xodimlar soni, sana), CRUD yo'q (E-007) |
| A-021 | Sessiya muddati 24 soat tanlandi (12 emas): do'kon ~14 soat ishlaydi, 12 soatda kassir savdo o'rtasida chiqarib yuborilardi |
| A-022 | Parollar ro'yxatida holat: faol / vaqtincha bloklangan (qachongacha) / doimiy bloklangan + "Blokni ochish" tugmasi |
| A-023 | Bloklash gibrid: hisoblagichlar va 10 daqiqalik blok — Redis (TTL); doimiy blok — PostgreSQL (`locked_at`), Redis qayta ishga tushsa ham saqlanadi |
| A-024 | Redis ishlamasa — FAIL-OPEN: himoya vaqtincha o'chadi, login ishlaydi, logga ogohlantirish. Sabab: kassa to'xtab qolmasligi kerak |
| A-025 | Mavjud bo'lmagan username ham sanaladi va bloklanadi (blok xabaridan username mavjudligini bilib bo'lmasin) |
| A-026 | Blokdan keyingi "sinov davri" 24 soat eslab qolinadi |
| A-027 | Login nomini admin o'zi yozadi; tizim faqat qoidani (A-016) va unikallikni tekshiradi |
| A-028 | Arxivdagi xodimga login yaratilmaydi — avval xodim arxivdan qaytariladi |
| A-029 | O'chirilgan login qaytarilmaydi. Kerak bo'lsa xodimga yangi login yaratiladi — boshqa nom bilan (A-010) |
| A-030 | Xodim (admin ham) o'z parolini o'zi almashtirmaydi: kassir/omborchi/buxgalternikini admin, adminnikini superadmin almashtiradi |
| A-031 | "Parollar" ro'yxatida holat: faol / vaqtincha blok (qachongacha, Redis TTL) / doimiy blok / o'chirilgan. "Blokni ochish" ikkalasini ham ochadi va hisoblagichlarni tozalaydi |

## Xodimlar

| # | Qaror |
|---|---|
| E-001 | Xodim maydonlari — hammasi majburiy: ism, familiya, tug'ilgan sana (yosh hisoblanadi), jins, telefon, lavozim, oylik maosh, rasm |
| E-002 | Lavozim xodim yaratilayotganda tanlanadi; "Lavozimlar" bo'limi uni o'zgartiradi |
| E-003 | Telefon raqami unikal (bir xil ism-familiyali xodimlar telefon orqali farqlanadi) |
| E-004 | Rasm: JPG/PNG, 5 MB gacha, server 512×512 ga kichraytiradi; diskda saqlanadi, bazada faqat yo'li |
| E-005 | Arxiv: xodim ro'yxatdan "Arxiv" bo'limiga o'tadi, login ishlamaydi va barcha sessiyalar yopiladi; arxivdan qaytarilsa — o'sha login yana ishlaydi |
| E-006 | Xodim ismi boshqa jadvallarga nusxalanmaydi — hamma joy `employee_id` orqali oladi |
| E-007 | "Lavozimlar" = o'zgarmas ma'lumotnoma (1C "Должности" kabi), "Rollar" bo'limi bilan bitta. Lavozim xodim formasida select orqali tanlanadi; o'zgartirish — xodim kartochkasidagi tugma (tasdiqlash + jurnal + qayta kirish) |
| E-008 | Xodim formasi 3 guruhda: Shaxsiy ma'lumotlar (ism, familiya, sana, jins, rasm), Aloqa (telefon), Ish (lavozim, maosh) |
| E-009 | O'chirish: tarixi yo'q xodim butunlay o'chadi (qator, lavozim tarixi, rasm). Tarixi bor xodim anonimlashtiriladi: ism → "O'chirilgan xodim #id", telefon va rasm o'chadi, loginlar o'chiriladi, sessiyalar yopiladi; qator qoladi (sotuv/kassa unga bog'langan), hech qaysi ro'yxatda ko'rinmaydi, telefon bo'shaydi. Hozircha "tarix" = kamida bir marta login berilgan; har modul qo'shilganda kengayadi |
| E-010 | Lavozim va maosh tarixi (`employee_positions`, 1C "Кадровое перемещение"): har o'zgarishda eski davr `valid_to = yangi sana − 1 kun` bilan yopiladi, yangisi ochiladi; ochiq davr bittadan ko'p bo'lmaydi (baza indeksi). O'sha kunning o'zida o'zgartirish — joriy davrni tuzatadi. Lavozim o'zgarsa xodim barcha qurilmalardan chiqariladi; faqat maosh o'zgarsa — yo'q |
| E-011 | Telefon istalgan yozuvda qabul qilinadi ("90 002 12 21", "+998 (90) …"), bazada `+998XXXXXXXXX`, ekranda `+998 90 002 12 21` |
| E-012 | Rasm ochiq URL orqali beriladi (`/media/employees/<tasodifiy>.jpg`); fayl nomi tasodifiy (uuid), ketma-ket terib topib bo'lmaydi. Rasm doim JPEG ga o'giriladi |
| E-013 | Ro'yxat sanalari bo'yicha filtr Toshkent vaqtida hisoblanadi (UTC'da emas) |
| E-014 | Xodim yoshi 5 dan 100 gacha (to'liq yillar bo'yicha, Toshkent sanasi bilan) |

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
| B-004 | "Katta kassir" vazifasini buxgalter roli bajaradi: kassadagi pulni sanab qabul qiladi, pul avtomatik seyfga o'tadi (alohida rol qo'shilmaydi — R-001) |
| P-001 | Oylik: ishlangan kunlar, kunlik soat, oylik, bonus, jarima — admin kiritadi |

## Audit jurnali

| # | Qaror |
|---|---|
| AU-001 | Jurnalni superadmin va admin ko'radi. Admin superadminning amallarini va superadminga oid yozuvlarni ko'rmaydi (R-003) |
| AU-002 | Faqat o'zgargan maydonlar yoziladi: `{"maydon": [eski, yangi]}`. Parol, hash va tokenlar hech qachon yozilmaydi — faqat "parol almashtirildi" |
| AU-003 | Jurnal doimiy saqlanadi, o'chirilmaydi (D-010). Hajm oshsa — oylar bo'yicha partitioning, o'chirish emas |
| AU-004 | Har bir xato login jurnalga yozilmaydi (faqat structlog). Jurnalga: muvaffaqiyatli login, vaqtincha/doimiy blok, blokni ochish. Sabab: A-025 tufayli begona odam jurnalni "spam" bilan to'ldira oladi |
| AU-005 | 3 ta muhimlik darajasi: info / important / critical. Jurnal standart filtri — important va undan yuqori |
| AU-006 | Sezgir amallarda sabab majburiy (blokni ochish, kassani majburan bo'shatish, katta chegirma va h.k.). Qaysi amalda majburiyligi katalogda belgilanadi |
| AU-007 | Oddiy savdo auditga yozilmaydi — chekning o'zi o'zgarmas hujjat. Yoziladi: chegirma, qaytarish, qo'lda narx o'zgartirish |
| AU-008 | Amallar qat'iy katalogda (`AuditAction`): har amalda nom (`employee.salary_changed`), muhimlik, sabab majburiyligi, o'zbekcha matn shabloni. Umumiy nomlar (`*.updated`) ishlatilmaydi |
| AU-009 | Yozuv amal bilan bitta tranzaksiyada saqlanadi. Audit yozib bo'lmasa — amal ham bekor (fail-closed; A-024 ning teskarisi, chunki bu nazorat vositasi) |
| AU-010 | Baza darajasida trigger UPDATE, DELETE va TRUNCATE ni taqiqlaydi. Noto'g'ri yozuv tahrirlanmaydi — ustiga tuzatuvchi yangi yozuv qo'shiladi (storno kabi) |
| AU-011 | Bitta biznes-amal = bitta yozuv (masalan, 20 qatorli chek uchun 20 ta emas, bitta yozuv) |
| AU-012 | Har sezgir endpoint uchun test: "amal bajarildi → aynan shu `action` bilan yozuv bor" |

## Muammolar (admin bildirishnomalari)

| # | Qaror |
|---|---|
| N-001 | Admin panel tepasida 🔔 — **ochiq muammolar** soni (o'qilmagan xabarlar emas). Bosilsa — "Muammolar" ro'yxati |
| N-002 | Bir xil muammo takrorlanmaydi — bitta yozuvga guruhlanadi ("anvar bloklandi — 3 marta, oxirgisi 10:02") |
| N-003 | Muammo sababi bartaraf etilganda O'ZI yopiladi (masalan blok ochilganda). Yopilganlar o'chirilmaydi — tarixda: kim, qachon hal qildi |
| N-004 | Filtrlar: holat (ochiq — standart / hal qilingan / hammasi), tur, sana oralig'i, xodim; eng yangisi tepada; pagination. Har yozuvda tezkor amal tugmasi (masalan "Blokni ochish") |
| N-005 | Muammo turlari har modulda qo'shib boriladi. Hozirgi ro'yxat: akkaunt bloklandi (auth); 10 000 so'mdan katta chegirma (kassa). Rejada: kamomad, yaroqlilik muddati, qoldiq tugashi, qaytarishlar ko'payishi |
| N-006 | Muammo turiga qarab yopiladi: sababi texnik bo'lsa (blok) — o'zi yopiladi; odam qarori kerak bo'lsa (katta chegirma) — faqat admin "Asosli / Asossiz" + izoh bilan yopadi. Yopish ham auditga yoziladi |
| N-007 | *(Kassa'da yakunlanadi)* Katta chegirma: savdo to'xtamaydi, sabab majburiy, keyin admin ko'radi (oldindan PIN-tasdiq emas). Chegara: summa **yoki** foiz (masalan 10 000 so'm yoki 10%), qiymati sozlamada |

## Operatsion va nazorat talablari

| # | Qaror | Bosqich |
|---|---|---|
| O-001 | **Majburiy:** bazaning avtomatik zaxira nusxasi — har kecha `pg_dump`, server tashqarisidagi joyga, oxirgi 30 kun saqlanadi; tiklash yo'riqnomasi sinab ko'rilgan bo'lishi shart | Deploy |
| O-002 | **Majburiy:** production xatolarini kuzatish (Sentry) — xato bo'lsa darhol xabar | Deploy |
| O-003 | **Majburiy:** kun yakuni hisoboti (Z-hisobot) — kassa yopilganda: savdolar, naqd/karta/terminal, qaytarishlar, chegirmalar | Kassa |
| O-004 | **Majburiy:** chek raqamlari har kassada uzluksiz (#000001, #000002…), bo'shliqsiz | Kassa |
| C-001 | Narx o'zgarishlari tarixi: har mahsulot bo'yicha kim, qachon, qaysi narxdan qaysi narxga | Katalog |

Keyinroq ko'rib chiqiladi (hozir rejada emas): kassa ekranini PIN bilan qulflash, faol sessiyalar sahifasi,
rasmiy hujjatlar (logo, STIR, QR, PDF), versiyalar va CHANGELOG, Excel eksport, Telegram bildirishnomalari,
dashboard grafiklari, audit jurnali uchun hash zanjiri (o'chirilgan qatorni aniqlash).

## Kerak emas (ataylab chiqarilgan)

Avtomobil/avtoraqam modullari, operator va programist rollari, fiskal chek, smena moduli,
sodiqlik ballari, kredit limiti, ko'p tillilik, ulgurji narx, qarzni hisobdan chiqarish,
qo'lda qoldiq tuzatish, zaxira nusxa UI (zaxira nusxaning o'zi majburiy — O-001), SMS.

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
