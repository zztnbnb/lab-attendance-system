from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def migrate(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" ")
    activated: list[str] = []
    try:
        user_ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT DISTINCT user_id
                FROM face_profiles
                WHERE status = 'PENDING'
                  AND submitted_at IS NOT NULL
                  AND COALESCE(liveness_score, 0) >= 0.55
                  AND (
                    SELECT COUNT(*) FROM face_templates
                    WHERE face_templates.profile_id = face_profiles.id
                  ) >= 3
                """
            )
        ]
        connection.execute("BEGIN")
        for user_id in user_ids:
            candidates = connection.execute(
                """
                SELECT id FROM face_profiles
                WHERE user_id = ?
                  AND status = 'PENDING'
                  AND submitted_at IS NOT NULL
                  AND COALESCE(liveness_score, 0) >= 0.55
                  AND (
                    SELECT COUNT(*) FROM face_templates
                    WHERE face_templates.profile_id = face_profiles.id
                  ) >= 3
                ORDER BY submitted_at DESC
                """,
                (user_id,),
            ).fetchall()
            chosen_id = candidates[0][0]
            connection.execute(
                """
                UPDATE face_profiles
                SET status = 'REPLACED', reviewed_at = ?
                WHERE user_id = ? AND status IN ('ACTIVE', 'PENDING') AND id <> ?
                """,
                (now, user_id, chosen_id),
            )
            connection.execute(
                """
                UPDATE face_profiles
                SET status = 'ACTIVE', reviewed_at = ?, live_verified_at = ?
                WHERE id = ?
                """,
                (now, now, chosen_id),
            )
            connection.execute(
                "UPDATE enrollment_sessions SET status = 'COMPLETED' WHERE profile_id = ?",
                (chosen_id,),
            )
            connection.execute(
                """
                INSERT INTO audit_logs (
                  id, actor_user_id, actor_device_id, action, target_type,
                  target_id, before_data, after_data, reason, created_at
                ) VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    "FACE_PROFILE_LEGACY_AUTO_ACTIVATED",
                    "face_profile",
                    chosen_id,
                    json.dumps({"status": "PENDING"}),
                    json.dumps({"status": "ACTIVE"}),
                    "Policy changed to activate validated self-enrollment on submission",
                    now,
                ),
            )
            activated.append(chosen_id)
        connection.commit()
        return activated
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    result = migrate(args.database)
    print(json.dumps({"activated": result, "count": len(result)}))
