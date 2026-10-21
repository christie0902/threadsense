"""Exercise the actual CrewAI revision path with a mocked provider boundary."""

import json
from types import SimpleNamespace

import pytest

from threadsense.agents import interpretation_revision as revision
from threadsense.agents.contracts import ThreadInterpretation, VerificationFinding
from threadsense.models import Thread


@pytest.fixture
def revision_case(monkeypatch, tmp_path):
    monkeypatch.setenv("THREADSENSE_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-revision-key")
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("CREWAI_TELEMETRY_ENABLED", "false")
    monkeypatch.setattr(
        "crewai.memory.storage.kickoff_task_outputs_storage.db_storage_path",
        lambda: str(tmp_path),
    )
    thread = Thread.model_validate({
        "thread_id": "1.0", "project_id": "test", "channel_id": "C_TEST",
        "channel_name": "test", "channel_type": "QA",
        "created_at": "2026-10-01T00:00:00Z",
        "messages": [{
            "message_id": "1.0", "author_id": "U1", "author_name": "Trainer",
            "author_role": "TUTOR", "timestamp": "2026-10-01T00:00:00Z",
            "text": "Should this silent clip be QN or scored?",
        }],
    })
    original = ThreadInterpretation(
        thread_id="1.0", summary="The author asks about a quality note (QN).",
        central_question="Should the clip be quarantined or scored?",
        resolution_state="UNRESOLVED", resolution_rationale="No reply supplies guidance.",
        confidence=0.6,
    )
    findings = [VerificationFinding(
        category="TERMINOLOGY", explanation="QN means Quarantine, not quality note.",
        disputed_fields=["summary"],
    )]
    return thread, original, findings


@pytest.mark.parametrize("invalid", [False, True])
def test_revision_reuses_interpreter_model_once_and_preserves_raw_before_validation(
    monkeypatch, revision_case, invalid,
):
    import litellm

    thread, original, findings = revision_case
    corrected = original.model_copy(update={"summary": "The author asks whether to use Quarantine (QN)."})
    raw = "not valid JSON" if invalid else corrected.model_dump_json()
    calls, saved = [], []

    def complete(**kwargs):
        calls.append(kwargs)
        assert kwargs["model"] == "openai/gpt-4o-mini"
        assert kwargs["api_key"] == "offline-revision-key"
        prompt = json.dumps(kwargs["messages"])
        assert "Quarantine" in prompt and "Label Tool" in prompt
        assert "quality note" in prompt
        assert "SPECIFIC VERIFICATION FINDINGS" in prompt
        assert "authority_eligible_message_ids" not in prompt  # All placeholders resolved.
        return litellm.ModelResponse(
            model=kwargs["model"],
            choices=[{"message": {"role": "assistant", "content": f"Final Answer: {raw}"},
                      "finish_reason": "stop"}],
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    monkeypatch.setattr(litellm, "completion", complete)
    if invalid:
        with pytest.raises(RuntimeError, match="valid ThreadInterpretation JSON"):
            revision.revise_interpretation(thread, original, findings, None, on_raw_output=saved.append)
    else:
        result = revision.revise_interpretation(thread, original, findings, None, on_raw_output=saved.append)
        assert result == corrected
    assert saved == [raw]
    assert len(calls) == 1


def test_missing_revision_text_is_retained_and_rejected(monkeypatch, revision_case):
    thread, original, findings = revision_case
    monkeypatch.setattr(revision, "Crew", lambda **kwargs: SimpleNamespace(
        kickoff=lambda **kwargs: SimpleNamespace(raw=None),
    ))
    saved = []
    with pytest.raises(ValueError, match="no text output"):
        revision.revise_interpretation(thread, original, findings, None, on_raw_output=saved.append)
    assert saved == [""]
