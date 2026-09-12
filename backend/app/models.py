"""Validated boundaries shared by the interpreter, policy engine, and API."""
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["book", "reschedule", "cancel", "availability", "hours", "handoff", "medical", "unclear"]
    doctor: str | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    original_date: str | None = None
    appointment_id: str | None = None
    hold: bool = False
    ambiguous: bool = False


class Slot(BaseModel):
    doctor: str
    date: str
    time: str


class Appointment(Slot):
    id: str
    status: Literal["confirmed", "cancelled"] = "confirmed"


class Proposal(Slot):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["book", "reschedule", "cancel"]
    appointment_id: str | None = None
    summary: str


class ToolResult(BaseModel):
    name: str
    result: str


class Decision(BaseModel):
    intent: str
    entities: dict
    action: str
    reason: str
    checks: list[str]
    tools: list[ToolResult] = Field(default_factory=list)
    source: str
    duration_ms: int = 0


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["user", "assistant"]
    content: str
    decision: Decision | None = None


class SessionView(BaseModel):
    id: str
    now: str
    mode: str
    model: str | None
    messages: list[Message]
    appointments: list[Appointment]
    pending: Proposal | None
    slots: list[Slot]
    handoffs: int


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=8, max_length=100)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(min_length=8, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)
