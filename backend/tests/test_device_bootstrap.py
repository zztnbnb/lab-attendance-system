from uuid import uuid4

from fastapi.testclient import TestClient


def test_local_device_bootstrap_is_admin_only_and_idempotent(client: TestClient, admin_headers: dict):
    payload = {
        "installation_id": str(uuid4()),
        "name": "本机打卡终端",
        "location": "测试电脑",
    }

    unauthorized = client.post("/api/v1/admin/devices/bootstrap-local", json=payload)
    assert unauthorized.status_code == 401

    first = client.post("/api/v1/admin/devices/bootstrap-local", headers=admin_headers, json=payload)
    assert first.status_code == 200, first.text
    first_device = first.json()
    assert first_device["code"].startswith("LOCAL-")
    assert first_device["secret"]

    second = client.post("/api/v1/admin/devices/bootstrap-local", headers=admin_headers, json=payload)
    assert second.status_code == 200, second.text
    second_device = second.json()
    assert second_device["id"] == first_device["id"]
    assert second_device["code"] == first_device["code"]
    assert second_device["secret"] != first_device["secret"]

    old_credentials = {
        "X-Device-Code": first_device["code"],
        "X-Device-Key": first_device["secret"],
    }
    assert client.post("/api/v1/kiosk/recognition-sessions", headers=old_credentials).status_code == 401

    current_credentials = {
        "X-Device-Code": second_device["code"],
        "X-Device-Key": second_device["secret"],
    }
    assert client.post("/api/v1/kiosk/recognition-sessions", headers=current_credentials).status_code == 201
