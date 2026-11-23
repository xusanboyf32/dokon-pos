"""Xodim rasmlari (E-004, E-012).

- Faqat JPG/PNG, 5 MB gacha.
- Server rasmni 512×512 ga sig'diradi va JPEG qilib saqlaydi (hajm kichik, format bir xil).
- Fayl nomi tasodifiy: ketma-ket terib (1.jpg, 2.jpg …) hammasini yig'ib bo'lmaydi.
"""

import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.exceptions import AppError

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 512
ALLOWED_FORMATS = {"JPEG", "PNG"}
SUBDIR = "employees"


class InvalidPhotoError(AppError):
    code = "INVALID_PHOTO"
    message = "Rasm JPG yoki PNG formatida, 5 MB gacha bo'lishi kerak"


def save_photo(content: bytes) -> str:
    """Rasmni tekshiradi, kichraytiradi, saqlaydi. Bazaga yoziladigan nisbiy yo'lni qaytaradi."""
    if not content or len(content) > MAX_BYTES:
        raise InvalidPhotoError()
    try:
        image = Image.open(io.BytesIO(content))
        image.load()  # fayl haqiqatan rasmmi — kengaytmaga emas, mazmuniga qaraymiz
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidPhotoError() from exc
    if image.format not in ALLOWED_FORMATS:
        raise InvalidPhotoError()

    result = image.convert("RGB")
    result.thumbnail((MAX_SIDE, MAX_SIDE))

    relative = f"{SUBDIR}/{uuid.uuid4().hex}.jpg"
    target = Path(get_settings().media_root) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target, format="JPEG", quality=85, optimize=True)
    return relative


def delete_photo(relative_path: str | None) -> None:
    if relative_path:
        (Path(get_settings().media_root) / relative_path).unlink(missing_ok=True)


def photo_url(relative_path: str | None) -> str | None:
    if relative_path is None:
        return None
    return f"{get_settings().media_url.rstrip('/')}/{relative_path}"
