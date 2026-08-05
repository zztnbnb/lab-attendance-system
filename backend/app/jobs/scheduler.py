from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.entities import AttendanceSession, AttendanceStatus
from app.services.audit import add_audit


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lab-attendance-scheduler")


async def mark_missing_checkouts() -> int:
    cutoff = utcnow() - timedelta(hours=settings.missing_checkout_hours)
    async with SessionLocal() as db:
        sessions = (
            await db.execute(
                select(AttendanceSession)
                .where(
                    AttendanceSession.status == AttendanceStatus.OPEN,
                    AttendanceSession.check_in_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for item in sessions:
            item.status = AttendanceStatus.MISSING_CHECKOUT
            add_audit(
                db,
                action="ATTENDANCE_MARKED_MISSING_CHECKOUT",
                target_type="attendance_session",
                target_id=item.id,
                before={"status": AttendanceStatus.OPEN.value},
                after={"status": AttendanceStatus.MISSING_CHECKOUT.value},
                reason=f"超过 {settings.missing_checkout_hours} 小时未签退",
            )
        await db.commit()
        return len(sessions)


async def run() -> None:
    logger.info("scheduler started")
    while True:
        try:
            count = await mark_missing_checkouts()
            if count:
                logger.info("marked %s missing checkouts", count)
        except Exception:
            logger.exception("missing-checkout job failed")
        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(run())
