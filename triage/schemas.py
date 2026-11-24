"""Pydantic models: validated structured outputs for every LLM step."""
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Classification(BaseModel):
    category: Category
    confidence: float = Field(ge=0, le=1, description="Model confidence 0-1")
    reasoning: str = Field(description="One sentence justification")


class PriorityAssessment(BaseModel):
    priority: Priority
    reasoning: str
    customer_sentiment: str = Field(description="e.g. angry, neutral, happy")


class DraftResponse(BaseModel):
    subject: str
    body: str = Field(min_length=10)


class Ticket(BaseModel):
    ticket_id: str
    customer: str
    message: str = Field(min_length=3)


class TriageState(TypedDict, total=False):
    ticket: dict
    classification: dict
    priority: dict
    draft: dict
    route: str  # "auto_reply" | "escalate"
    escalation_reason: str
    status: str
