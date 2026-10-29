"""
ThreadSense Severity Rubric (TL-editable)

Place this file where project-specific standards live so Team Leads can
edit it per project without touching agent code.
"""

from enum import Enum
from typing import TypedDict


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NOT_APPLICABLE = "N/A"
    UNKNOWN = "UNKNOWN"


class SeverityDefinition(TypedDict):
    definition: str
    examples: str
    # At least one signal should be supported for MEDIUM/HIGH.
    # Support may come from wording, symptoms, context, or related reports.
    # Exact phrases and explicit impact declarations are not required.
    required_signals: list[str]  # At least one must be present for MEDIUM/HIGH


SEVERITY_RUBRIC: dict[SeverityLevel, SeverityDefinition] = {
    SeverityLevel.HIGH: {
        "definition": (
            "Issue creating or reasonably indicating a serious risk to data "
            "integrity, labeling quality, operational continuity, or required "
            "safety procedures. May affect many tasks, cause difficult-to-reverse "
            "errors, or require prompt escalation. Serious impact may be inferred "
            "from the described behavior even when it is not explicitly stated."
        ),
        "examples": (
            "Widespread incorrect labeling caused by conflicting instructions; "
            "required QN/safety controls being bypassed; major LT outage; "
            "systemic QA misalignment affecting a batch; "
            "Operational reports such as 'all required fields are filled but "
            "Submit stays grey' or 'the waveform loads but Play never starts' "
            "can indicate inability to complete or evaluate assigned work."
        ),
        "required_signals": [
            "Explicit statement that assigned work cannot be completed or evaluated",
            "Safety or required QN control described as bypassed, missing, or ignored",
            "Issue reported as affecting many tasks or an entire batch",
             "Multiple distinct people or affected tasks reporting a comparable problem within the relevant project, batch, and time window, suggesting "
            "broader disruption or systemic labeling risk. Consider the number affected relative to the known active group when that information is available; do not require an explicit statement of widespread impact"
        ],
    },
    SeverityLevel.MEDIUM: {
        "definition": (
           "Issue that may affect labeling accuracy, QA consistency, or "
            "operational efficiency, requiring clarification or intervention. "
            "Impact appears meaningful but contained or manageable based on "
            "the available context. A question alone does not establish "
            "MEDIUM, but its content may reveal consequential uncertainty."
        ),
        "examples": (
            "Recurring rubric ambiguity; conflicting QA interpretations; "
            "intermittent LT failures affecting task completion; unclear "
            "QN handling for a specific edge case. "
            "Examples include similar pairs receiving inconsistent tie "
            "judgments, reviewers disagreeing over clipping severity, or "
            "playback repeatedly failing and then recovering."
        ),
        "required_signals": [
            (
                "Recurring confusion about the same rule, tool behavior, "
                "or scoring criterion that suggests meaningful workflow "
                "or labeling impact"
            ),
            (
                "Conflicting interpretations that affect, or are reasonably "
                "likely to affect, how tasks are scored or handled"
            ),
            (
                "Intermittent or contained tool/process failure suggesting "
                "a meaningful interruption, with context indicating that "
                "work remains possible or access recovers"
            ),
        ],
    },
    SeverityLevel.LOW: {
        "definition": (
            "Localized issue that appears to have limited impact on labeling quality or workflow. The available context suggests a minor "
            "inconvenience or straightforward correction rather than a "
            "substantive operational problem."
        ),
        "examples": (
            "One-off clarification of otherwise clear guidance; minor LT "
            "inconvenience; isolated inconsistency with little downstream "
            "impact; a confusing FAQ heading when the underlying rule is "
            "understood and usable."
        ),
        "required_signals": [],  # No required signal; default when higher triggers are absent
    },
    SeverityLevel.NOT_APPLICABLE: {
        "definition": (
            "No identifiable operational problem or risk requiring severity assessment. "
            "Includes casual chat, pure social threads, and routine announcements."
        ),
        "examples": (
            "Routine announcements, informational updates, acknowledgments, "
            "administrative messages, general discussion without an actionable issue."
        ),
        "required_signals": [],
    },
    SeverityLevel.UNKNOWN: {
        "definition": (
            "The report and available context are too ambiguous or incomplete to meaningfully assess operational impact. Missing explicit impact wording, affected-task counts, or a confirmed technical cause does not by itself require UNKNOWN."
        ),
        "examples": (
            "'Something looks wrong' without describing the behavior; "
            "a report referring to missing context; contradictory accounts that leave it unclear whether there is a minor display issue "
            "or an inability to complete the task."
        ),
        "required_signals": [],
    },
}


# Metadata for traceability (Agent 3 should record which version it used)
RUBRIC_VERSION = "severity-rubric-v2-with-signals"
PROJECT_ID = None  # Set per project when TL edits a copy, e.g. "audio_multimodal"


def get_rubric_for_project(project_id: str | None = None) -> dict:
    """
    Placeholder for future per-project loading.
    Currently returns the default rubric.
    Future project-specific loading is not implemented. The editable source is
    data/knowledge/severity_rubric.py; project_id currently labels the response only.
    """
    return {
        "version": RUBRIC_VERSION,
        "project_id": project_id or PROJECT_ID,
        "rubric": SEVERITY_RUBRIC,
    }
