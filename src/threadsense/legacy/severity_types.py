"""Historical serialization enum only; no rubric or assessment implementation."""
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    NOT_APPLICABLE = 'N/A'
