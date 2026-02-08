"""
Agent 1 (Project Analyzer) — Pydantic models for structured output.

All LLM calls that produce the final analysis must use
.with_structured_output(ProjectAnalysis). These models define the schema
the agent fills from PDF specs / unstructured text.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Priority level for a user story."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Actor(BaseModel):
    """A user role or stakeholder in the project."""

    name: str = Field(..., description="Role or actor name (e.g. 'Project Manager')")
    description: str = Field(..., description="Brief description of the role and responsibilities")


class UserStory(BaseModel):
    """One functional requirement in 'who / what / why' form."""

    id: str = Field(..., description="Unique identifier (e.g. US-01)")
    actor: str = Field(..., description="Name of the actor who performs the action")
    action: str = Field(..., description="What the actor does")
    goal: str = Field(..., description="Why / business value")
    priority: Literal["High", "Medium", "Low"] = Field(
        default="Medium",
        description="Priority of this user story",
    )


class TechnicalConstraint(BaseModel):
    """A non-functional or technical requirement."""

    category: str = Field(
        ...,
        description="Category (e.g. Database, Security, Performance)",
    )
    requirement: str = Field(..., description="The technical requirement text")


class ProjectAnalysis(BaseModel):
    """
    Root structured output of Agent 1 (Project Analyzer).

    Produced via .with_structured_output(ProjectAnalysis) from the LLM.
    """

    project_name: str = Field(..., description="Name of the project")
    summary: str = Field(..., description="Short project summary (2–4 sentences)")
    actors: list[Actor] = Field(
        default_factory=list,
        description="List of identified actors/roles",
    )
    functional_requirements: list[UserStory] = Field(
        default_factory=list,
        description="User stories / functional requirements",
    )
    technical_constraints: list[TechnicalConstraint] = Field(
        default_factory=list,
        description="Technical and non-functional constraints",
    )
    identified_risks: list[str] = Field(
        default_factory=list,
        description="List of identified project risks",
    )
