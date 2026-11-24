"""Audit jurnali uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


async def add(session: AsyncSession, event: AuditEvent) -> AuditEvent:
    """Yozuvni chaqiruvchining tranzaksiyasiga qo'shadi. Commit — chaqiruvchida (AU-009)."""
    session.add(event)
    await session.flush()
    return event
