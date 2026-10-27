"""Agent 2 schema v2: factual consolidation, without Agent 3 decisions.

Legacy TopicAnalysis/TopicRollup remain in contracts.py for historical decoding.
That module is part of frozen Agent 1 fingerprints and is deliberately unchanged.
"""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class StrictModel(BaseModel):
    model_config = {'extra':'forbid'}

class EvidenceReference(StrictModel):
    member_id: Text
    message_id: Text
    quote: Text

class CitedText(StrictModel):
    text: Text
    evidence: list[EvidenceReference] = Field(min_length=1)

class FactualTopic(StrictModel):
    topic_name: Text
    member_ids: list[Text] = Field(min_length=1)
    conversation_kind: Literal['DISCUSSION', 'ANNOUNCEMENT', 'MIXED']
    shared_issue: CitedText
    representative_question: CitedText | None
    relevant_differences: list[CitedText]
    open_questions: list[CitedText]
    supported_answers: list[CitedText]
    uncertainties: list[CitedText]

    @model_validator(mode='after')
    def announcement_has_no_question(self):
        if self.conversation_kind == 'ANNOUNCEMENT' and (
            self.representative_question is not None or self.open_questions or self.supported_answers
        ):
            raise ValueError('Pure announcements have no invented question or question/answer resolution.')
        return self

class TopicConsolidation(StrictModel):
    schema_version: Literal[2]
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
