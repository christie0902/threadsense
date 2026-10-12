from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest

from threadsense.agents import thread_interpreter


@pytest.mark.parametrize(
    "model",
    [
        "openrouter/openrouter/free",
        "openrouter/test-provider/test-model:free",
    ],
)
def test_free_model_uses_openrouter_credentials(monkeypatch, model):
    monkeypatch.setenv("THREADSENSE_MODEL", model)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-provider-key")
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-provider-key")
    monkeypatch.setattr(thread_interpreter, "LLM", lambda **kwargs: kwargs)

    settings = thread_interpreter.create_llm()

    assert settings["model"] == model
    assert settings["api_key"] == "test-provider-key"
    assert settings["base_url"] == "https://openrouter.ai/api/v1"
    assert settings["is_litellm"] is True


def test_openai_key_cannot_substitute_for_missing_openrouter_key(monkeypatch):
    monkeypatch.setenv("THREADSENSE_MODEL", "openrouter/openrouter/free")
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-provider-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not configured"):
        thread_interpreter.create_llm()


def test_default_model_is_the_free_router(monkeypatch):
    monkeypatch.delenv("THREADSENSE_MODEL", raising=False)

    assert thread_interpreter.get_model_settings() == (
        "openrouter/openrouter/free", "OPENROUTER_API_KEY"
    )


@pytest.mark.parametrize("model", [
    "", "openrouter/", "unsupported/model",
    "openai/gpt-4o-mini", "openrouter/openai/gpt-4o-mini",
])
def test_invalid_model_reports_expected_format(monkeypatch, model):
    monkeypatch.setenv("THREADSENSE_MODEL", model)

    with pytest.raises(ValueError, match="THREADSENSE_MODEL"):
        thread_interpreter.get_model_settings()


def test_paid_model_is_rejected_before_the_demo_asks_for_a_key(monkeypatch, capsys):
    monkeypatch.setenv("THREADSENSE_MODEL", "openrouter/openai/gpt-4o-mini")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["run_agent1_demo.py"])
    prompt = Mock(side_effect=AssertionError("A key should not be requested"))
    monkeypatch.setattr("getpass.getpass", prompt)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_agent1_demo.py"

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")

    assert exc.value.code == 2
    prompt.assert_not_called()
    assert "openrouter/openrouter/free" in capsys.readouterr().err
