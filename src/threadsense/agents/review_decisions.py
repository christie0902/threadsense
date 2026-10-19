
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from threadsense.agents.contracts import TopicAnalysis


class HumanReviewDecision(str, Enum):
    ACCEPTED = "ACCEPTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    REJECTED = "REJECTED"


class ReviewRecord(BaseModel):
    candidate_group_id: str
    analysis_hash: str
    decision: HumanReviewDecision
    reviewer: str
    notes: str
    reviewed_at: datetime


def record_review(
    analysis: TopicAnalysis,
    decision: HumanReviewDecision,
    reviewer: str,
    notes: str,
    output_dir: Path,
) -> Path:
    """Persist a human decision without modifying Agent 2 output."""

    if not reviewer.strip() or not notes.strip():
        raise ValueError("Reviewer and review notes are required")

    # Fingerprint the exact analysis being reviewed.
    content = json.dumps(
        analysis.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
    )
    fingerprint = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    record = ReviewRecord(
        candidate_group_id=analysis.candidate_group_id,
        analysis_hash=fingerprint,
        decision=HumanReviewDecision(decision),
        reviewer=reviewer.strip(),
        notes=notes.strip(),
        reviewed_at=datetime.now(timezone.utc),
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"review_{fingerprint[:16]}.json"

    # Exclusive creation prevents overwriting an earlier review.
    with path.open("x", encoding="utf-8") as file:
        file.write(record.model_dump_json(indent=2))

    return path
