import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.agents import thread_interpreter


@pytest.fixture
def configured_thread(monkeypatch, tmp_path):
    monkeypatch.setenv("THREADSENSE_MODEL", "openrouter/openrouter/free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-private-key")
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("CREWAI_TELEMETRY_ENABLED", "false")
    monkeypatch.setattr(
        "crewai.memory.storage.kickoff_task_outputs_storage.db_storage_path",
        lambda: str(tmp_path),
    )
    root = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "slack"
    return MockSlackAdapter(
        fixture_dir=str(root / "channels"), users_file=str(root / "users.json")
    ).get_threads("C_AUDIO_GENERAL")[0]


@pytest.fixture
def valid_output(configured_thread):
    return {
        "thread_id": configured_thread.thread_id,
        "summary": "Test response for the fixture thread.",
        "central_question": None,
        "resolution_state": "UNRESOLVED",
        "authoritative_response_present": False,
        "authority_evidence_message_ids": [],
        "resolution_rationale": "Test rationale.",
        "confidence": 0.5,
    }


@pytest.mark.parametrize("fenced", [False, True])
def test_full_crew_uses_text_completion_and_validates_json_locally(
    monkeypatch, configured_thread, valid_output, fenced
):
    import litellm

    requests = []
    raw = json.dumps(valid_output)
    if fenced:
        raw = f"```json\n{raw}\n```"

    def complete(**kwargs):
        requests.append(kwargs)
        assert kwargs["model"] == "openrouter/openrouter/free"
        assert kwargs["api_key"] == "test-private-key"
        assert not kwargs.get("response_format")
        assert not kwargs.get("response_model")
        assert not kwargs.get("tools")
        assert "authority_evidence_message_ids" in json.dumps(kwargs["messages"])
        return litellm.ModelResponse(
            model="openrouter/free",
            choices=[{
                "message": {
                    "role": "assistant",
                    "content": f"Thought: I can return the result.\nFinal Answer: {raw}",
                },
                "finish_reason": "stop",
            }],
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    monkeypatch.setattr(litellm, "completion", complete)
    result = thread_interpreter.interpret_thread(configured_thread)

    assert result.model_dump(mode="json") == valid_output
    assert len(requests) == 1


def test_http_400_is_not_retried_and_error_redacts_key(monkeypatch, configured_thread):
    import litellm

    calls = []

    def reject(**kwargs):
        calls.append(kwargs)
        raise litellm.BadRequestError(
            message="Rejected request containing test-private-key",
            model=kwargs["model"],
            llm_provider="openrouter",
        )

    monkeypatch.setattr(litellm, "completion", reject)
    with pytest.raises(RuntimeError, match="OpenRouter request failed.*HTTP 400") as exc:
        thread_interpreter.interpret_thread(configured_thread)

    assert "test-private-key" not in str(exc.value)
    assert "[redacted]" in str(exc.value)
    assert len(calls) == 1


@pytest.mark.parametrize(("changes", "message"), [
    ({"thread_id": "wrong-thread"}, "thread_id does not match"),
    ({"authority_evidence_message_ids": ["unknown"], "authoritative_response_present": True},
     "unknown message IDs"),
    ({"authoritative_response_present": True}, "inconsistent"),
    ({"confidence": 2}, "valid ThreadInterpretation JSON"),
])
def test_local_validation_rejects_invalid_output(
    monkeypatch, configured_thread, valid_output, changes, message
):
    raw = json.dumps({**valid_output, **changes})
    monkeypatch.setattr(thread_interpreter, "Crew", lambda **kwargs: SimpleNamespace(
        kickoff=lambda **inputs: SimpleNamespace(raw=raw)
    ))

    with pytest.raises((ValueError, RuntimeError), match=message):
        thread_interpreter.interpret_thread(configured_thread)


def test_invalid_json_has_actionable_error(monkeypatch, configured_thread):
    monkeypatch.setattr(thread_interpreter, "Crew", lambda **kwargs: SimpleNamespace(
        kickoff=lambda **inputs: SimpleNamespace(raw="I could not interpret the thread.")
    ))

    with pytest.raises(RuntimeError, match="select another :free model"):
        thread_interpreter.interpret_thread(configured_thread)
