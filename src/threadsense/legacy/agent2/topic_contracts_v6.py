"""Historical v6 inventory/impact contract; retained for strict replay only."""
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
    resolution_confidence: float | None = Field(ge=0, le=1, description='Uncalibrated model self-assessment of this resolution judgment, independent of severity and inherited reliability. Null if not assessed; never a measured probability.')
    uncertainty_note: CitedText | None = Field(description='Specific remaining ambiguity or research question, citing original evidence in this member conversation. Preserve unresolved scope even when the chosen likely resolution is ANSWERED. Null only if no specific uncertainty identified.')


class SourceItem(StrictModel):
    item_id: Text
    evidence_id: Text
    kind: Literal['QUESTION', 'DIAGNOSTIC_REQUEST', 'ANSWER', 'INSTRUCTION',
                  'FACT', 'ANNOUNCEMENT', 'CONTEXT']
    answer_status: Literal['TENTATIVE', 'DIRECT'] | None = Field(description='Only ANSWER items: TENTATIVE for unconfirmed advice, DIRECT for an explicit scoped answer. Context alone is not an answer. Python supplies the full original quotation.')
    question: QuestionState | None = Field(description='Required only for QUESTION. Link ANSWER items in the same member conversation, never diagnostics or another thread.')

    @model_validator(mode='after')
    def question_consistency(self):
        if (self.kind == 'QUESTION') != (self.question is not None):
            raise ValueError('Only QUESTION items have required question state.')
        if (self.kind == 'ANSWER') != (self.answer_status is not None):
            raise ValueError('Only ANSWER items have required answer_status.')
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
    impact: ImpactProposal | None = Field(description='Null when unassessed; never invent impact to fill the schema.')


class TopicConsolidation(StrictModel):
    topics: list[ResponseTopic] = Field(min_length=1)


class ResponseEnvelope(StrictModel):
    """Parse sections independently; invalid impact cannot delete valid facts."""
    topics: list[dict] = Field(min_length=1)


