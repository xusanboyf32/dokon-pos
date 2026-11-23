"""SQL bilan bog'liq kichik yordamchilar (barcha modullar uchun umumiy)."""


def escape_like(text: str) -> str:
    """LIKE/ILIKE uchun: % va _ maxsus belgi emas, oddiy belgi bo'lsin.

    Ishlatish: column.ilike(f"%{escape_like(q)}%", escape="\\\\")
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
