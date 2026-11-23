from datetime import UTC, datetime, timedelta

import pytest

from app.core.time import to_tashkent, utcnow


def test_utcnow_is_timezone_aware_utc() -> None:
    now = utcnow()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_to_tashkent_adds_five_hours() -> None:
    utc_time = datetime(2026, 11, 23, 19, 30, tzinfo=UTC)

    local = to_tashkent(utc_time)

    # Toshkent UTC+5 — kun ham almashadi (19:30 UTC → ertasi 00:30)
    assert (local.day, local.hour, local.minute) == (24, 0, 30)
    assert local.utcoffset() == timedelta(hours=5)
    assert local == utc_time  # bu bitta vaqt lahzasi, faqat boshqa mintaqada


def test_to_tashkent_rejects_naive_datetime() -> None:
    naive = datetime(2026, 11, 23, 12, 0)  # noqa: DTZ001 — ataylab timezone'siz

    with pytest.raises(ValueError, match="Timezone'siz"):
        to_tashkent(naive)
