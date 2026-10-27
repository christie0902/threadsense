
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NOT_APPLICABLE = "N/A"


SEVERITY_RUBRIC = {
    SeverityLevel.LOW: {
        "definition": (
            "Localized issue with limited impact on labeling quality or "
            "workflow. Work continues normally, and any correction is "
            "straightforward."
        ),
        "examples": (
            "One-off clarification, minor LT inconvenience, isolated "
            "inconsistency with no meaningful downstream impact."
        ),
    },
    SeverityLevel.MEDIUM: {
        "definition": (
            "Issue that may affect labeling accuracy, QA consistency, or "
            "operational efficiency, requiring clarification or intervention. "
            "Impact is meaningful but appears contained or manageable."
        ),
        "examples": (
            "Recurring rubric ambiguity, conflicting QA interpretations, "
            "intermittent LT failures affecting task completion, unclear "
            "QN handling for a specific edge case."
        ),
    },
    SeverityLevel.HIGH: {
        "definition": (
            "Issue creating a serious risk to data integrity, labeling "
            "quality, operational continuity, or required safety procedures. "
            "May affect many tasks, cause difficult-to-reverse errors, "
            "or require prompt escalation."
        ),
        "examples": (
            "Widespread incorrect labeling caused by conflicting instructions, "
            "lost labels, required QN/safety controls being bypassed, major "
            "LT outage, systemic QA misalignment affecting an entire batch."
        ),
    },
    SeverityLevel.NOT_APPLICABLE: {
        "definition": (
            "No identifiable operational problem or risk requiring "
            "severity assessment."
        ),
        "examples": (
            "Routine announcements, informational updates, acknowledgments, "
            "administrative messages, general discussion without an "
            "actionable issue."
        ),
    },
}
