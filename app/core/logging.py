"""Loglar (structlog).

- local: o'qishga qulay rangli format
- production: JSON (log tizimlari oson tahlil qiladi)
Har bir log yozuvida so'rovning `request_id` si bo'ladi (middleware qo'shadi).
"""

import logging

import structlog


def configure_logging(level: str, *, json_logs: bool) -> None:
    level_no = logging.getLevelNamesMapping()[level]
    logging.basicConfig(format="%(message)s", level=level_no)

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # request_id va h.k.
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        cache_logger_on_first_use=True,
    )
