from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def create_manual_user(client: TestClient, admin_headers: dict, username: str) -> str:
    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": username,
            "real_name": "管理员补签测试",
            "identifier": f"MANUAL-{username}",
            "password": "ManualPass123!",
            "role": "USER",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_manual_device(client: TestClient, admin_headers: dict, code: str) -> None:
    response = client.post(
        "/api/v1/admin/devices",
        headers=admin_headers,
        json={"code": code, "name": "补签测试终端", "location": "实验室"},
    )
    assert response.status_code == 201, response.text


def test_admin_can_create_closed_manual_attendance(client: TestClient, admin_headers: dict):
    user_id = create_manual_user(client, admin_headers, "manual-closed")
    create_manual_device(client, admin_headers, "MANUAL-CLOSED")
    check_in = datetime.now(timezone.utc) - timedelta(hours=3)
    check_out = check_in + timedelta(hours=2, minutes=15)

    response = client.post(
        "/api/v1/admin/attendance-sessions/manual",
        headers=admin_headers,
        json={
            "user_id": user_id,
            "check_in_at": check_in.isoformat(),
            "check_out_at": check_out.isoformat(),
            "reason": "摄像头故障，已核对门禁记录",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "CLOSED"
    assert body["duration_seconds"] == 8100
    assert body["corrected"] is True
    assert body["correction_reason"] == "摄像头故障，已核对门禁记录"


def test_admin_manual_open_attendance_blocks_second_open_record(client: TestClient, admin_headers: dict):
    user_id = create_manual_user(client, admin_headers, "manual-open")
    create_manual_device(client, admin_headers, "MANUAL-OPEN")
    check_in = datetime.now(timezone.utc) - timedelta(minutes=30)
    payload = {
        "user_id": user_id,
        "check_in_at": check_in.isoformat(),
        "reason": "忘记打卡，管理员核实在场",
    }

    first = client.post("/api/v1/admin/attendance-sessions/manual", headers=admin_headers, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "OPEN"

    second = client.post("/api/v1/admin/attendance-sessions/manual", headers=admin_headers, json=payload)
    assert second.status_code == 409, second.text


def test_manual_attendance_rejects_future_or_invalid_times(client: TestClient, admin_headers: dict):
    user_id = create_manual_user(client, admin_headers, "manual-invalid")
    create_manual_device(client, admin_headers, "MANUAL-INVALID")
    now = datetime.now(timezone.utc)

    future = client.post(
        "/api/v1/admin/attendance-sessions/manual",
        headers=admin_headers,
        json={
            "user_id": user_id,
            "check_in_at": (now + timedelta(minutes=1)).isoformat(),
            "reason": "测试未来时间校验",
        },
    )
    assert future.status_code == 422, future.text

    invalid_order = client.post(
        "/api/v1/admin/attendance-sessions/manual",
        headers=admin_headers,
        json={
            "user_id": user_id,
            "check_in_at": now.isoformat(),
            "check_out_at": (now - timedelta(minutes=1)).isoformat(),
            "reason": "测试时间顺序校验",
        },
    )
    assert invalid_order.status_code == 422, invalid_order.text
