from fastapi.testclient import TestClient


def jpeg(name: str, pose: str):
    return ("files", (f"{pose}.jpg", f"{name}|{pose}".encode(), "image/jpeg"))


def test_admin_user_device_enrollment_and_attendance_flow(client: TestClient, admin_headers: dict):
    user_response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "alice",
            "real_name": "测试用户",
            "identifier": "LAB-001",
            "password": "AlicePass123!",
            "role": "USER",
        },
    )
    assert user_response.status_code == 201, user_response.text
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/api/v1/admin/devices",
        headers=admin_headers,
        json={"code": "LAB-DOOR-01", "name": "实验室门口", "location": "主实验室"},
    )
    assert device_response.status_code == 201, device_response.text
    device = device_response.json()
    device_headers = {"X-Device-Code": device["code"], "X-Device-Key": device["secret"]}

    enrollment = client.post(
        "/api/v1/face/enrollment-sessions",
        headers=admin_headers,
        json={"target_user_id": user_id, "mode": "ADMIN"},
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]
    frames = [jpeg("alice", "left"), jpeg("alice", "front"), jpeg("alice", "right")]
    captured = client.post(
        f"/api/v1/face/enrollment-sessions/{enrollment_id}/frames",
        headers=admin_headers,
        files=frames,
    )
    assert captured.status_code == 200, captured.text
    activated = client.post(
        f"/api/v1/face/enrollment-sessions/{enrollment_id}/submit",
        headers=admin_headers,
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "ACTIVE"

    recognition = client.post("/api/v1/kiosk/recognition-sessions", headers=device_headers)
    assert recognition.status_code == 201, recognition.text
    verified = client.post(
        f"/api/v1/kiosk/recognition-sessions/{recognition.json()['id']}/verify",
        headers=device_headers,
        files=frames,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["allowed_action"] == "CHECK_IN"
    assert verified.json()["face_box"] is not None
    assert verified.json()["processing_ms"] is not None
    assert verified.json()["quality_hint"]
    checked_in = client.post(
        "/api/v1/kiosk/attendance-actions",
        headers=device_headers,
        json={"ticket": verified.json()["ticket"], "action": "CHECK_IN", "idempotency_key": "check-in-0001"},
    )
    assert checked_in.status_code == 200, checked_in.text
    assert checked_in.json()["status"] == "OPEN"

    dashboard = client.get("/api/v1/kiosk/dashboard", headers=device_headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["current_count"] == 1
    assert dashboard.json()["today_checkins"] == 1
    assert dashboard.json()["today_checkouts"] == 0
    assert dashboard.json()["recent_records"][0]["real_name"] == "测试用户"

    presence = client.get("/api/v1/kiosk/presence", headers=device_headers)
    assert presence.status_code == 200, presence.text
    assert presence.json()["total"] == 1
    assert presence.json()["items"][0]["real_name"] == "测试用户"

    records = client.get("/api/v1/kiosk/records", headers=device_headers)
    assert records.status_code == 200, records.text
    assert records.json()["total"] == 1
    assert records.json()["items"][0]["action"] == "CHECK_IN"

    duplicate = client.post(
        "/api/v1/kiosk/attendance-actions",
        headers=device_headers,
        json={"ticket": verified.json()["ticket"], "action": "CHECK_IN", "idempotency_key": "different-key"},
    )
    assert duplicate.status_code == 409

    second = client.post("/api/v1/kiosk/recognition-sessions", headers=device_headers)
    verified_out = client.post(
        f"/api/v1/kiosk/recognition-sessions/{second.json()['id']}/verify",
        headers=device_headers,
        files=frames,
    )
    assert verified_out.json()["allowed_action"] == "CHECK_OUT"
    checked_out = client.post(
        "/api/v1/kiosk/attendance-actions",
        headers=device_headers,
        json={"ticket": verified_out.json()["ticket"], "action": "CHECK_OUT", "idempotency_key": "check-out-0001"},
    )
    assert checked_out.status_code == 200, checked_out.text
    assert checked_out.json()["status"] == "CLOSED"
    assert checked_out.json()["duration_seconds"] >= 0

    after_checkout = client.get("/api/v1/kiosk/dashboard", headers=device_headers)
    assert after_checkout.status_code == 200, after_checkout.text
    assert after_checkout.json()["current_count"] == 0
    assert after_checkout.json()["today_checkouts"] == 1

    third = client.post("/api/v1/kiosk/recognition-sessions", headers=device_headers)
    verified_next_cycle = client.post(
        f"/api/v1/kiosk/recognition-sessions/{third.json()['id']}/verify",
        headers=device_headers,
        files=frames,
    )
    assert verified_next_cycle.status_code == 200, verified_next_cycle.text
    assert verified_next_cycle.json()["allowed_action"] == "CHECK_IN"

    statistics = client.get("/api/v1/admin/statistics", headers=admin_headers)
    assert statistics.status_code == 200, statistics.text
    assert statistics.json()["today_checkins"] == 1
    assert statistics.json()["today_checkouts"] == 1
    assert statistics.json()["current_count"] == 0


def test_self_enrollment_can_be_live_verified(client: TestClient, admin_headers: dict):
    created = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "bob",
            "real_name": "待复验用户",
            "identifier": "LAB-002",
            "password": "BobSecure123!",
            "role": "USER",
        },
    )
    assert created.status_code == 201, created.text

    login = client.post("/api/v1/auth/login", json={"username": "bob", "password": "BobSecure123!"})
    assert login.status_code == 200, login.text
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    enrollment = client.post(
        "/api/v1/face/enrollment-sessions",
        headers=user_headers,
        json={"mode": "SELF"},
    )
    assert enrollment.status_code == 201, enrollment.text
    frames = [jpeg("bob", "left"), jpeg("bob", "front"), jpeg("bob", "right")]
    captured = client.post(
        f"/api/v1/face/enrollment-sessions/{enrollment.json()['id']}/frames",
        headers=user_headers,
        files=frames,
    )
    assert captured.status_code == 200, captured.text

    submitted = client.post(
        f"/api/v1/face/enrollment-sessions/{enrollment.json()['id']}/submit",
        headers=user_headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "PENDING"

    verified = client.post(
        f"/api/v1/admin/face-profiles/{submitted.json()['id']}/live-verify",
        headers=admin_headers,
        files=frames,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    assert verified.json()["score"] >= verified.json()["threshold"]
