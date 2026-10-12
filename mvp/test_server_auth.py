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


def test_public_demo_requires_explicit_opt_in_and_disallows_live_credentials(monkeypatch):
    for key in (
        "JARVIS_ADMIN_TOKEN", "JARVIS_WORKER_TOKEN", "JARVIS_WORKER_ID",
        "JARVIS_WORKER_TOKENS", "JARVIS_WORKER_CAPABILITIES",
        "JARVIS_SEARCH_ENDPOINT", "JARVIS_SEARCH_API_KEY",
        "JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("JARVIS_PUBLIC_DEMO", raising=False)

    from mvp.server import authenticate_dashboard
    with pytest.raises(WorkforceAuthError) as error:
        authenticate_dashboard(Headers())
    assert error.value.status == 503

    monkeypatch.setenv("JARVIS_PUBLIC_DEMO", "true")
    assert authenticate_dashboard(Headers()) == {"role": "demo", "worker_id": None}

    monkeypatch.setenv("JARVIS_SEARCH_ENDPOINT", "https://search.example.test/api")
    with pytest.raises(WorkforceAuthError) as unsafe:
        authenticate_dashboard(Headers())
    assert unsafe.value.status == 503
