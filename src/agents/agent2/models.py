"""
Agent 2 (Task Allocator) — Pydantic models for task–developer assignment.

Input: tasks (from Agent 1 user stories or tickets) and developers with skills.
Output: TaskAllocationResult (who does what).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Developer(BaseModel):
    """A developer with a skill set for allocation."""

    id: str = Field(..., description="Unique identifier (e.g. dev-1)")
    name: str = Field(..., description="Display name")
    skills: list[str] = Field(
        default_factory=list,
        description="List of skills (e.g. Python, API, Security)",
    )
    capacity: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max number of tasks that can be assigned",
    )


class Task(BaseModel):
    """A task or user story to assign to a developer."""

    id: str = Field(..., description="Unique identifier (e.g. US-01)")
    title: str = Field(..., description="Short title or action summary")
    complexity: Literal["Low", "Medium", "High"] = Field(
        default="Medium",
        description="Task complexity",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Skills needed for this task",
    )


class Assignment(BaseModel):
    """One task assigned to one developer."""

    task_id: str = Field(..., description="Task identifier")
    developer_id: str = Field(..., description="Developer identifier")
    reason: str | None = Field(
        default=None,
        description="Short justification for the assignment",
    )


class TaskAllocationResult(BaseModel):
    """Output of Agent 2: full assignment plan."""

    assignments: list[Assignment] = Field(
        default_factory=list,
        description="Task–developer assignments",
    )
    unassigned_task_ids: list[str] = Field(
        default_factory=list,
        description="Task IDs that could not be assigned",
    )
