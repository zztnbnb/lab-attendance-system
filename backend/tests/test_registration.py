from fastapi.testclient import TestClient


def test_student_id_registration_logs_user_in_and_rejects_duplicate(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"student_id": "202499999999", "real_name": "测试同学", "password": "safe-password-123"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["username"] == "202499999999"
    assert response.json()["user"]["identifier"] == "202499999999"
    assert response.json()["user"]["role"] == "USER"
    assert response.cookies.get("lab_refresh_token")

    duplicate = client.post(
        "/api/v1/auth/register",
        json={"student_id": "202499999999", "real_name": "测试同学", "password": "safe-password-123"},
    )
    assert duplicate.status_code == 409


def test_student_id_must_be_numeric(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"student_id": "student-a", "real_name": "测试同学", "password": "safe-password-123"},
    )
    assert response.status_code == 422
