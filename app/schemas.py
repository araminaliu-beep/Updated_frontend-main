"""Typed meeting output contracts used by reporting and tests."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _fallback(value: str | None, replacement: str) -> str:
    if value is None or not str(value).strip():
        return replacement
    return str(value).strip()


class ActionItem(BaseModel):
    owner: str = Field(default="Unassigned")
    task: str
    deadline: str = Field(default="Unknown")
    status: str = Field(default="Open")

    @field_validator("owner", mode="before")
    @classmethod
    def default_owner(cls, value: str | None) -> str:
        return _fallback(value, "Unassigned")

    @field_validator("deadline", mode="before")
    @classmethod
    def default_deadline(cls, value: str | None) -> str:
        return _fallback(value, "Unknown")

    @field_validator("status", mode="before")
    @classmethod
    def default_status(cls, value: str | None) -> str:
        return _fallback(value, "Open")


class MeetingActionOutput(BaseModel):
    meeting_type: str = Field(default="Unknown")
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    follow_up_email: str = Field(default="")

    @field_validator("meeting_type", mode="before")
    @classmethod
    def default_meeting_type(cls, value: str | None) -> str:
        return _fallback(value, "Unknown")
