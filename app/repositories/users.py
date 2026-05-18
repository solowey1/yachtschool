from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    language: str,
) -> User:
    user = await get_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            language=language,
        )
        session.add(user)
        await session.flush()
        return user
    user.username = username
    user.first_name = first_name
    if not user.language:
        user.language = language
    return user


async def all_active(session: AsyncSession) -> list[User]:
    res = await session.execute(select(User).where(User.daily_enabled.is_(True)))
    return list(res.scalars().all())
