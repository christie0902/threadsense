from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest

from threadsense.agents import thread_interpreter
from threadsense import config
from threadsense.agents import topic_analyst


@pytest.mark.parametrize(
    "model",
    [
        "openrouter/openrouter/free",
        "openrouter/test-provider/test-model:free",
        "openrouter/openai/gpt-4o-mini",
    ],
)
def test_openrouter_model_uses_openrouter_credentials(monkeypatch, model):
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


def test_default_model_is_openai(monkeypatch):
    monkeypatch.delenv("THREADSENSE_MODEL", raising=False)

    assert thread_interpreter.get_model_settings() == (
        "openai/gpt-4o-mini", "OPENAI_API_KEY"
    )


@pytest.mark.parametrize("model", [None, "openai/gpt-4o-mini", "gpt-4o-mini"])
def test_openai_configuration_uses_its_own_credentials(monkeypatch, model):
    if model is None:
        monkeypatch.delenv("THREADSENSE_MODEL", raising=False)
    else:
        monkeypatch.setenv("THREADSENSE_MODEL", model)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong-provider-key")
    monkeypatch.setattr(thread_interpreter, "LLM", lambda **kwargs: kwargs)

    settings = thread_interpreter.create_llm()

    assert settings["model"] == (model or "openai/gpt-4o-mini")
    assert settings["api_key"] == "test-openai-key"
    assert settings["base_url"] == "https://api.openai.com/v1"
    assert settings["temperature"] == 0
    assert settings["max_tokens"] == 4096
    assert settings["timeout"] == 120

    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        thread_interpreter.create_llm()


@pytest.mark.parametrize("model", ["", "   "])
def test_invalid_model_reports_expected_format(monkeypatch, model):
    monkeypatch.setenv("THREADSENSE_MODEL", model)

    with pytest.raises(ValueError, match="THREADSENSE_MODEL"):
        thread_interpreter.get_model_settings()


def test_empty_model_is_rejected_before_the_demo_asks_for_a_key(monkeypatch, capsys):
    monkeypatch.setenv("THREADSENSE_MODEL", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["run_agent1_demo.py"])
    prompt = Mock(side_effect=AssertionError("A key should not be requested"))
    monkeypatch.setattr("getpass.getpass", prompt)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_agent1_demo.py"

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")

    assert exc.value.code == 2
    prompt.assert_not_called()
    assert "THREADSENSE_MODEL must not be empty" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("model", "key_name"),
    [
        ("openai/gpt-4o-mini", "OPENAI_API_KEY"),
        ("openrouter/openrouter/free", "OPENROUTER_API_KEY"),
    ],
)
def test_both_agents_load_saved_credentials_from_another_directory(
    monkeypatch, tmp_path, model, key_name
):
    config.ENV_FILE.write_text(
        f"THREADSENSE_MODEL={model}\n{key_name}=saved-test-key\n",
        encoding="utf-8-sig",
    )
    working_dir = tmp_path / "elsewhere"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
    monkeypatch.setattr(thread_interpreter, "LLM", lambda **kwargs: kwargs)
    monkeypatch.setattr(topic_analyst, "Agent", lambda **kwargs: kwargs)

    interpreter_llm = thread_interpreter.create_llm()
    analyst_llm = topic_analyst.create_topic_analyst()["llm"]

    for settings in (interpreter_llm, analyst_llm):
        assert settings["model"] == model
        assert settings["api_key"] == "saved-test-key"


def test_terminal_settings_take_precedence_over_saved_settings(monkeypatch):
    config.ENV_FILE.write_text(
        "THREADSENSE_MODEL=openrouter/openrouter/free\n"
        "OPENAI_API_KEY=saved-test-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THREADSENSE_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "terminal-test-key")
    monkeypatch.setattr(thread_interpreter, "LLM", lambda **kwargs: kwargs)

    settings = thread_interpreter.create_llm()

    assert settings["model"] == "openai/gpt-4o-mini"
    assert settings["api_key"] == "terminal-test-key"


@pytest.mark.parametrize(
    ("script_name", "arguments", "exit_code"),
    [
        ("run_agent1_demo.py", [], 1),
        ("run_agent1_batch.py", ["--limit", "1"], 2),
        ("run_agent2_sample.py", ["--run"], 2),
    ],
)
def test_runners_report_missing_saved_key_without_prompting(
    monkeypatch, tmp_path, capsys, script_name, arguments, exit_code
):
    config.ENV_FILE.write_text(
        "THREADSENSE_MODEL=openai/gpt-4o-mini\nOPENAI_API_KEY=\n",
        encoding="utf-8",
    )
    prompt = Mock(side_effect=AssertionError("No terminal prompt is allowed"))
    monkeypatch.setattr("getpass.getpass", prompt)
    monkeypatch.setattr("builtins.input", prompt)
    llm = Mock(side_effect=AssertionError("Missing keys must prevent model startup"))
    monkeypatch.setattr(thread_interpreter, "LLM", llm)
    script = Path(__file__).resolve().parents[1] / "scripts" / script_name
    runner = runpy.run_path(str(script))
    output_dir = tmp_path / "outputs"
    if script_name == "run_agent1_batch.py":
        arguments = [*arguments, "--output-dir", str(output_dir)]
    if script_name == "run_agent2_sample.py":
        monkeypatch.setitem(runner["main"].__globals__, "OUTPUT", output_dir / "analysis.json")
    monkeypatch.setattr("sys.argv", [str(script), *arguments])

    with pytest.raises(SystemExit) as exc:
        runner["main"]()

    assert exc.value.code == exit_code
    error = capsys.readouterr().err
    assert "OPENAI_API_KEY is not configured" in error
    assert str(config.ENV_FILE) in error
    prompt.assert_not_called()
    llm.assert_not_called()
    assert not output_dir.exists()
