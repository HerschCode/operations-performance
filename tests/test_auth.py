"""
src/api/main.py builds the FastAPI app (and reads API_KEY) at import time, so these
tests reload the app module after setting/clearing the env var, rather than relying
on FastAPI re-evaluating the dependency's environment lookup per-request (it does --
require_api_key reads os.environ live -- but reloading main.py per test here keeps
these tests independent of that implementation detail and robust either way).
"""
import importlib
from fastapi.testclient import TestClient


def _client_with_api_key(monkeypatch, key: str | None):
    if key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", key)
    import src.api.main as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_health_never_requires_a_key(monkeypatch):
    client = _client_with_api_key(monkeypatch, "secret-123")
    response = client.get("/health")
    assert response.status_code == 200


def test_protected_endpoint_fails_open_when_no_key_configured(monkeypatch):
    from unittest.mock import patch
    client = _client_with_api_key(monkeypatch, None)
    with patch("src.api.routes.load_cases") as mock_load_cases:
        import pandas as pd
        mock_load_cases.return_value = pd.DataFrame({"case_id": ["C1"], "cycle_time_hours": [10.0]})
        response = client.get("/metrics/cycle-time")
    assert response.status_code == 200  # no API_KEY set -> auth fails open


def test_protected_endpoint_rejects_missing_header_when_key_configured(monkeypatch):
    client = _client_with_api_key(monkeypatch, "secret-123")
    response = client.get("/metrics/cycle-time")
    assert response.status_code == 401


def test_protected_endpoint_rejects_wrong_key(monkeypatch):
    client = _client_with_api_key(monkeypatch, "secret-123")
    response = client.get("/metrics/cycle-time", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_protected_endpoint_accepts_correct_key(monkeypatch):
    from unittest.mock import patch
    client = _client_with_api_key(monkeypatch, "secret-123")
    with patch("src.api.routes.load_cases") as mock_load_cases:
        import pandas as pd
        mock_load_cases.return_value = pd.DataFrame({"case_id": ["C1"], "cycle_time_hours": [10.0]})
        response = client.get("/metrics/cycle-time", headers={"X-API-Key": "secret-123"})
    assert response.status_code == 200
