"""Agent 2 schema v3: evidence IDs, scoped guidance and provisional severity.

Legacy TopicAnalysis/TopicRollup remain in contracts.py for historical decoding.
That module is part of frozen Agent 1 fingerprints and is deliberately unchanged.
"""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints, model_validator
from threadsense.agents.operational_severity import CRITERIA

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class StrictModel(BaseModel):
    model_config = {'extra':'forbid'}

class CitedText(StrictModel):
    text: Text
    evidence_ids: list[Text] = Field(min_length=1)

class ScopedGuidance(CitedText):
    kind: Literal['SCOPED_ANSWER', 'HANDLING_INSTRUCTION', 'DIAGNOSTIC_REQUEST']
    authority: Literal['TEAM_LEAD', 'TL_ENDORSED', 'SOURCE_REPLY']
    scope: CitedText
    limitations: list[CitedText]

class SourceAssessment(StrictModel):
    evidence_id: Text
    question_status: Literal['NONE', 'OPEN', 'PARTIAL', 'ANSWERED'] = Field(
        description='Status of a question asked IN this message. Use NONE for statements/instructions without a question; ANSWERED does not mean this message is itself an answer.')
    guidance_status: Literal['NONE', 'AVAILABLE'] = Field(
        description='Independent of question_status. AVAILABLE instructions/answers must be retained in guidance or supported_answers with their scope and limitations.')

class ProvisionalSeverity(StrictModel):
    level: Literal['HIGH', 'MEDIUM', 'LOW', 'N/A', 'UNKNOWN']
    rubric_version: Literal['provisional-operational-severity-v1']
    matched_criteria: list[Text] = Field(min_length=1, description=(
        'Nonempty exact criterion IDs matching level. UNKNOWN requires insufficient_impact_evidence; '
        'N/A requires non_operational. Neither uses an empty list.'))
    rationale: CitedText = Field(description=(
        'Cite the source messages supporting the assessment, including for UNKNOWN/N/A. '
        'For UNKNOWN explain what impact evidence the cited conversation lacks; do not invent impact.'))
    work_blockage: CitedText | None
    affected_scope: CitedText | None
    quality_or_safety_consequences: CitedText | None
    evidence_basis: Literal['REPORTED_RISK', 'OBSERVED_OUTCOME', 'INSUFFICIENT_EVIDENCE', 'NON_OPERATIONAL'] = Field(
        description='UNKNOWN uses INSUFFICIENT_EVIDENCE. N/A uses NON_OPERATIONAL for clearly non-operational content. REPORTED_RISK/OBSERVED_OUTCOME distinguish reported operational risks from established outcomes. Never pair MEDIUM/HIGH/LOW/N/A with INSUFFICIENT_EVIDENCE.')
    severity_is_provisional: Literal[True]

    @model_validator(mode='after')
    def rubric_consistency(self):
        if len(set(self.matched_criteria)) != len(self.matched_criteria) or any(
            CRITERIA.get(c, {}).get('level') != self.level for c in self.matched_criteria
        ):
            raise ValueError('Severity criteria must be unique and match the selected rubric level.')
        if self.level == 'UNKNOWN' and self.evidence_basis != 'INSUFFICIENT_EVIDENCE':
            raise ValueError('UNKNOWN severity requires insufficient impact evidence.')
        if self.evidence_basis == 'NON_OPERATIONAL' and self.level != 'N/A':
            raise ValueError('NON_OPERATIONAL evidence basis is only valid for N/A.')
        if self.level == 'HIGH' and not (self.work_blockage or self.quality_or_safety_consequences):
            raise ValueError('HIGH requires cited substantial blockage or material quality/safety risk.')
        if self.level != 'UNKNOWN' and self.evidence_basis == 'INSUFFICIENT_EVIDENCE':
            raise ValueError('Insufficient impact evidence must remain UNKNOWN.')
        return self

class FactualTopic(StrictModel):
    topic_name: Text
    member_ids: list[Text] = Field(min_length=1)
    conversation_kind: Literal['DISCUSSION', 'ANNOUNCEMENT', 'MIXED']
    shared_issue: CitedText
    representative_question: CitedText | None
    relevant_differences: list[CitedText]
    open_questions: list[CitedText]
    supported_answers: list[ScopedGuidance]
    guidance: list[ScopedGuidance]
    uncertainties: list[CitedText]
    source_assessments: list[SourceAssessment] = Field(min_length=1, description=(
        'Exactly one entry for EVERY catalog message belonging to this topic, including uncited replies. '
        'These entries do not replace factual-prose evidence coverage for every assigned member.'))
    preliminary_severity: ProvisionalSeverity

    @model_validator(mode='after')
    def announcement_has_no_question(self):
        if self.conversation_kind == 'ANNOUNCEMENT' and (
            self.representative_question is not None or self.open_questions or self.supported_answers
        ):
            raise ValueError('Pure announcements have no invented question or question/answer resolution.')
        return self

class TopicConsolidation(StrictModel):
    schema_version: Literal[3]
    candidate_group_id: Text
    project_id: Text
    batch_id: str | None
    is_coherent: bool
    coherence_rationale: Text
    topics: list[FactualTopic] = Field(min_length=1)
    needs_review: bool
    review_reasons: list[Text]

    @model_validator(mode='after')
    def consistency(self):
        if self.is_coherent and len(self.topics) != 1:
            raise ValueError('A coherent candidate has exactly one topic.')
        if not self.is_coherent and len(self.topics) == 1 and not self.needs_review:
            raise ValueError('Uncertain membership needs a retained review reason.')
        if self.needs_review and not self.review_reasons:
            raise ValueError('Review requires an explanation.')
        return self
