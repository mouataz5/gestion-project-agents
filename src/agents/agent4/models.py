"""
Agent 4 (Meeting Summarizer) — Pydantic models for meeting summary and action items.

Structured output: title, participants, key points, action items (assignee, task, due).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """One action item extracted from the meeting."""

    assignee: str | None = Field(
        default=None,
        description="Person responsible (if mentioned)",
    )
    task: str = Field(..., description="What needs to be done")
    due_date: str | None = Field(
        default=None,
        description="Due date or deadline if mentioned (e.g. 'next Friday')",
    )


class ChunkSummary(BaseModel):
    """Summary of one transcript chunk (used in map step)."""

    key_points: list[str] = Field(
        default_factory=list,
        description="Main points from this chunk",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Action items mentioned in this chunk",
    )


class MeetingSummary(BaseModel):
    """Final meeting summary (map-reduce output)."""

    title: str = Field(default="", description="Meeting title or topic")
    date: str | None = Field(default=None, description="Meeting date if mentioned")
    participants: list[str] = Field(
        default_factory=list,
        description="People who participated or were mentioned",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Main discussion points and decisions",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Deduplicated action items with assignee and due date when known",
    )
