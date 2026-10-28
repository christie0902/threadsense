"""Current Agent 2 taxonomy response contract (v7); historical schemas live in legacy/agent2."""
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints


class StrictModel(BaseModel):
    model_config = {'extra': 'forbid'}


class TaxonomyTopic(StrictModel):
    topic_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    rationale: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    member_ids: list[Annotated[str, StringConstraints(min_length=1)]] = Field(min_length=1)


class TopicTaxonomy(StrictModel):
    """Assignments only. Empty topics is valid when every member is rejected."""
    topics: list[TaxonomyTopic]
    rejected_member_ids: list[Annotated[str, StringConstraints(min_length=1)]]
