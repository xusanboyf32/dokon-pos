# API qoidalari

## 1. URL'lar

- Prefiks: `/api/v1`
- Resurslar ko'plikda, kebab-case: `/api/v1/employees`, `/api/v1/kassa-carts`
- Resurs ekran nomi bo'yicha emas, **biznes tushunchasi** bo'yicha nomlanadi
  (`/employees`, ~~`/xodimlar-sahifasi`~~).
- CRUD bo'lmagan amallar — fe'l bilan alohida sub-resurs:
  `POST /accounts/{id}/reset-password`, `POST /accounts/{id}/unlock`, `PUT /employees/{id}/role`

| Metod | Ma'nosi | Muvaffaqiyat kodi |
|---|---|---|
| GET | O'qish | 200 |
| POST | Yaratish / amal | 201 (yaratish), 200 (amal) |
| PATCH | Qisman yangilash | 200 |
| PUT | To'liq almashtirish (masalan rol) | 200 |
| DELETE | O'chirish (soft) | 204 |

## 2. Javob formati

Muvaffaqiyatli javob — to'g'ridan-to'g'ri ob'ekt yoki sahifa (qo'shimcha "data" o'rami yo'q):

```json
{ "id": 12, "first_name": "Anvar", "role": "kassir", "created_at": "2026-11-23T08:30:00Z" }
```

Vaqtlar ISO-8601, UTC (`Z`). Frontend Toshkent vaqtida ko'rsatadi.
Pul summalari **string** sifatida qaytariladi (`"37000.00"`) — JSON number'dagi aniqlik yo'qolishining oldini olish uchun.

## 3. Xato formati (hamma joyda bir xil)

```json
{
  "error": {
    "code": "REASON_REQUIRED",
    "message": "Bu amal uchun sabab ko'rsatilishi shart",
    "details": { "field": "reason" },
    "request_id": "7f3c2a..."
  }
}
```

| HTTP | Qachon | Misol `code` |
|---|---|---|
| 400 | Biznes-qoida buzildi | `DISCOUNT_TOO_LARGE` |
| 401 | Token yo'q/yaroqsiz | `TOKEN_EXPIRED`, `INVALID_CREDENTIALS` |
| 403 | Ruxsat yo'q | `FORBIDDEN` |
| 404 | Topilmadi | `NOT_FOUND` |
| 409 | To'qnashuv | `USERNAME_TAKEN`, `PRODUCT_NAME_EXISTS`, `KASSA_BUSY` |
| 422 | Sxema tekshiruvi | `VALIDATION_ERROR` (maydonlar ro'yxati bilan) |
| 423 | Bloklangan | `ACCOUNT_LOCKED` |
| 429 | Juda ko'p urinish | `TOO_MANY_ATTEMPTS` |
| 500 | Kutilmagan xato | `INTERNAL_ERROR` (tafsilot faqat logda) |

`code` — frontend uchun barqaror identifikator; `message` — foydalanuvchiga ko'rsatiladigan matn.

## 4. Pagination

**Offset** (kichik ro'yxatlar):
```
GET /api/v1/brands?page=2&size=20
→ { "items": [...], "total": 134, "page": 2, "size": 20, "pages": 7 }
```

**Cursor** (katta ro'yxatlar: cheklar, audit jurnali):
```
GET /api/v1/audit-logs?limit=50&cursor=eyJpZCI6MTAyM30
→ { "items": [...], "next_cursor": "eyJpZCI6OTczfQ", "has_more": true }
```

`size`/`limit` maksimal 100.

## 5. Qidiruv, filtr, tartib

```
GET /api/v1/products?search=cola&category_id=3&brand_id=5&unit=litr
                    &created_from=2026-11-01&created_to=2026-11-30
                    &sort=-created_at&page=1&size=20
```

- `search` — matnli qidiruv (nom, shtrix-kod).
- Filtrlar — maydon nomi bilan; sana oralig'i `_from` / `_to`.
- `sort` — maydon nomi, `-` kamayish tartibi. Standart: `-created_at`.

## 6. Idempotentlik

Pul bilan bog'liq POST so'rovlar (savdo, to'lov, pul qabul qilish) `Idempotency-Key` sarlavhasini qabul qiladi.
Bir xil kalit bilan takroriy so'rov ikkinchi marta bajarilmaydi — birinchi natija qaytariladi
(masalan, internet uzilib, kassir tugmani ikki marta bosganda).
