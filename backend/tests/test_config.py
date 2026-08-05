from app.core.config import Settings


def test_allowed_origins_accepts_comma_separated_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174")
    configured = Settings(_env_file=None)
    assert configured.allowed_origins == ["http://localhost:5174", "http://127.0.0.1:5174"]
