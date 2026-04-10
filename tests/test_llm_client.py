from bot.services.llm_client import llm_enabled


def test_llm_enabled_flag(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm_enabled() is False

    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    assert llm_enabled() is True
