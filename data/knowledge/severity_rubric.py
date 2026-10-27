"""
ThreadSense Severity Rubric (TL-editable)

Place this file where project-specific standards live so Team Leads can
edit it per project without touching agent code.

Recommended location in the ThreadSense repo:
    standards/severity_rubric.py
    (or config/severity_rubric.py)

Agent 3 should load it at runtime. Keep a copy or import path stable.
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
    required_signals: list[str]  # At least one must be present for MEDIUM/HIGH


SEVERITY_RUBRIC: dict[SeverityLevel, SeverityDefinition] = {
    SeverityLevel.HIGH: {
        "definition": (
            "Issue creating a serious risk to data integrity, labeling quality, "
            "operational continuity, or required safety procedures. May affect "
            "many tasks, cause difficult-to-reverse errors, or require prompt escalation."
        ),
        "examples": (
            "Widespread incorrect labeling caused by conflicting instructions, "
            "required QN/safety controls being bypassed, major LT outage, "
            "systemic QA misalignment affecting an entire batch."
        ),
        "required_signals": [
            "Explicit statement that assigned work cannot be completed or evaluated",
            "Safety or required QN control described as bypassed, missing, or ignored",
            "Issue reported as affecting many tasks or an entire batch",
        ],
    },
    SeverityLevel.MEDIUM: {
        "definition": (
            "Issue that may affect labeling accuracy, QA consistency, or "
            "operational efficiency, requiring clarification or intervention. "
            "Impact is meaningful but appears contained or manageable. "
            "Clarification requests alone are not sufficient."
        ),
        "examples": (
            "Recurring rubric ambiguity, conflicting QA interpretations, "
            "intermittent LT failures affecting task completion, unclear "
            "QN handling for a specific edge case."
        ),
        "required_signals": [
            "Recurring confusion about the same rule, tool behavior, or scoring criterion",
            "Conflicting interpretations that affect how tasks are scored or handled",
            "Intermittent tool or process failure that blocks some but not all work",
        ],
    },
    SeverityLevel.LOW: {
        "definition": (
            "Localized issue with limited impact on labeling quality or workflow. "
            "Work continues normally, and any correction is straightforward."
        ),
        "examples": (
            "One-off clarification, minor LT inconvenience, isolated "
            "inconsistency with no meaningful downstream impact."
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
            "Insufficient evidence to assess operational impact. "
            "Do not invent a level when structured signals are absent."
        ),
        "examples": (
            "Topic contains only ambiguous or incomplete reports with no clear "
            "operational consequence stated."
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
    Later: load standards/{project_id}/severity_rubric.py if it exists.
    """
    return {
        "version": RUBRIC_VERSION,
        "project_id": project_id or PROJECT_ID,
        "rubric": SEVERITY_RUBRIC,
    }
