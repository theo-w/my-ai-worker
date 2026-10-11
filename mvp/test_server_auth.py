"""Security regression tests for the workforce API authentication boundary."""
import pytest

from mvp.server import WorkforceAuthError, authenticate_workforce, _worker_capabilities


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_workforce_api_fails_closed_without_tokens(monkeypatch):
    for key in ("JARVIS_ADMIN_TOKEN", "JARVIS_WORKER_TOKEN", "JARVIS_WORKER_ID",
                "JARVIS_WORKER_TOKENS", "JARVIS_WORKER_CAPABILITIES"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(WorkforceAuthError) as error:
        authenticate_workforce(Headers(), "admin")
    assert error.value.status == 503


def test_admin_and_worker_tokens_resolve_distinct_roles(monkeypatch):
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", "a" * 32)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", '{"researcher":"' + "w" * 32 + '"}')
    admin = authenticate_workforce(Headers(Authorization="Bearer " + "a" * 32), "admin")
    worker = authenticate_workforce(Headers(Authorization="Bearer " + "w" * 32), "worker")
    assert admin == {"role": "admin", "worker_id": None}
    assert worker == {"role": "worker", "worker_id": "researcher"}


def test_worker_token_cannot_authorize_admin_actions(monkeypatch):
    monkeypatch.delenv("JARVIS_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", '{"worker-a":"' + "w" * 32 + '"}')
    with pytest.raises(WorkforceAuthError) as error:
        authenticate_workforce(Headers(Authorization="Bearer " + "w" * 32), "admin")
    assert error.value.status == 403


def test_worker_tokens_must_be_long_and_json_must_be_valid(monkeypatch):
    monkeypatch.delenv("JARVIS_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", '{"worker-a":"short"}')
    with pytest.raises(WorkforceAuthError) as error:
        authenticate_workforce(Headers(Authorization="Bearer short"), "worker")
    assert error.value.status == 503


def test_worker_capabilities_are_server_configured(monkeypatch):
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", '{"researcher":["research","analysis"]}')
    assert _worker_capabilities("researcher") == ["analysis", "research"]
    assert _worker_capabilities("unknown-worker") == []
