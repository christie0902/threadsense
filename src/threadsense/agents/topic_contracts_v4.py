"""Agent 2 response v4: one item inventory and independent impact evidence.

Historical contracts remain in topic_contracts_v2/v3. Display fields are derived.
"""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = {'extra': 'forbid'}


class CitedText(StrictModel):
    text: Text
    evidence_ids: list[Text] = Field(min_length=1)


class QuestionState(StrictModel):
    status: Literal['OPEN', 'PARTIAL', 'ANSWERED']
    answer_item_ids: list[Text]


class SourceItem(StrictModel):
    item_id: Text
    evidence_id: Text
    kind: Literal['QUESTION', 'DIAGNOSTIC_REQUEST', 'ANSWER', 'INSTRUCTION',
                  'FACT', 'ANNOUNCEMENT', 'CONTEXT']
    text: Text = Field(description='Exact contiguous source excerpt including applicable qualifiers. No invented questions or paraphrases. Python retains the full original message.')
    question: QuestionState | None = Field(description='Required only for QUESTION. Link ANSWER items in the same member conversation, never diagnostics or another thread.')

    @model_validator(mode='after')
    def question_consistency(self):
        if (self.kind == 'QUESTION') != (self.question is not None):
            raise ValueError('Only QUESTION items have required question state.')
        if self.question:
            links = self.question.answer_item_ids
            if len(links) != len(set(links)):
                raise ValueError('Duplicate answer links.')
            if (self.question.status == 'OPEN') != (not links):
                raise ValueError('OPEN has no answers; PARTIAL/ANSWERED require scoped answer links.')
        return self


class SourceDisposition(StrictModel):
    evidence_id: Text
    disposition: Literal['NON_SUBSTANTIVE', 'UNCERTAIN']
    reason: Text


class InventoryTopic(StrictModel):
    topic_name: Text
    member_ids: list[Text] = Field(min_length=1)
    shared_issue: CitedText
    relevant_differences: list[CitedText]
    inventory: list[SourceItem] = Field(min_length=1)
    dispositions: list[SourceDisposition] = Field(description='Only messages without inventory items. Account for every message explicitly; missing treatment never defaults to NONE.')


class ImpactCriterion(StrictModel):
    criterion: Literal['substantial_blockage', 'material_quality_risk', 'material_safety_risk',
                       'bounded_operational_issue', 'limited_demonstrated_consequence',
                       'non_operational', 'insufficient_impact_evidence']
    basis: Literal['REPORTED_RISK', 'OBSERVED_OUTCOME', 'INSUFFICIENT_EVIDENCE', 'NON_OPERATIONAL']
    observation: CitedText


class ImpactProposal(StrictModel):
    criteria: list[ImpactCriterion] = Field(min_length=1)
    affected_scope: CitedText | None


class ResponseTopic(InventoryTopic):
    impact: ImpactProposal


class TopicConsolidation(StrictModel):
    schema_version: Literal[4]
    topics: list[ResponseTopic] = Field(min_length=1)


class ResponseEnvelope(StrictModel):
    """Parse sections independently; invalid impact cannot delete valid facts."""
    schema_version: Literal[4]
    topics: list[dict] = Field(min_length=1)
