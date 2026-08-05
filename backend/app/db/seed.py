from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.entities import Role, User


async def seed_initial_admin(db: AsyncSession) -> User:
    existing = (
        await db.execute(select(User).where(User.username == settings.initial_admin_username))
    ).scalar_one_or_none()
    if existing:
        return existing
    admin = User(
        username=settings.initial_admin_username,
        real_name=settings.initial_admin_real_name,
        password_hash=hash_password(settings.initial_admin_password),
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin
