"""
Agent 1 (Project Analyzer) — Pydantic models for structured output.

Enriched schema to capture all details from the PDF: full description, objectives,
scope, deliverables, timeline, assumptions, key terms, and detailed requirements.
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
    responsibilities: list[str] = Field(
        default_factory=list,
        description="List of concrete responsibilities or tasks for this actor",
    )


class UserStory(BaseModel):
    """One functional requirement in 'who / what / why' form, with full detail."""

    id: str = Field(..., description="Unique identifier (e.g. US-01)")
    actor: str = Field(..., description="Name of the actor who performs the action")
    action: str = Field(..., description="What the actor does (detailed)")
    goal: str = Field(..., description="Why / business value")
    priority: Literal["High", "Medium", "Low"] = Field(
        default="Medium",
        description="Priority of this user story",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Acceptance criteria or conditions of satisfaction",
    )
    notes: str = Field(default="", description="Additional detail from the document")


class TechnicalConstraint(BaseModel):
    """A non-functional or technical requirement."""

    category: str = Field(
        ...,
        description="Category (e.g. Database, Security, Performance)",
    )
    requirement: str = Field(..., description="The technical requirement text (full detail)")
    rationale: str = Field(default="", description="Why this constraint exists, if stated")


class KeyTerm(BaseModel):
    """A key term or acronym from the document with its definition."""

    term: str = Field(..., description="Term or acronym")
    definition: str = Field(..., description="Definition or explanation from the document")


class ProjectAnalysis(BaseModel):
    """
    Root structured output of Agent 1 (Project Analyzer).

    Enriched to capture all details from the PDF in the same context:
    full description, objectives, scope, deliverables, timeline, assumptions,
    key terms, and detailed requirements with acceptance criteria.
    """

    project_name: str = Field(..., description="Name of the project")
    summary: str = Field(..., description="Short project summary (2–4 sentences)")
    full_description: str = Field(
        default="",
        description="Comprehensive narrative of the project as described in the document (preserve detail, do not shorten)",
    )
    objectives: list[str] = Field(
        default_factory=list,
        description="Explicit project objectives or goals from the document",
    )
    scope: str = Field(
        default="",
        description="Scope of the project: what is in and out of scope (full detail)",
    )
    deliverables: list[str] = Field(
        default_factory=list,
        description="Deliverables or outputs expected from the project",
    )
    timeline: str = Field(
        default="",
        description="Duration, phases, milestones, or schedule as stated in the document",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions or preconditions stated in the document",
    )
    actors: list[Actor] = Field(
        default_factory=list,
        description="List of identified actors/roles with descriptions and responsibilities",
    )
    functional_requirements: list[UserStory] = Field(
        default_factory=list,
        description="User stories / functional requirements with acceptance criteria and notes",
    )
    technical_constraints: list[TechnicalConstraint] = Field(
        default_factory=list,
        description="Technical and non-functional constraints with rationale when stated",
    )
    identified_risks: list[str] = Field(
        default_factory=list,
        description="List of identified project risks (preserve full wording from document)",
    )
    key_terms: list[KeyTerm] = Field(
        default_factory=list,
        description="Key terms, acronyms, or glossary entries from the document",
    )
    additional_notes: str = Field(
        default="",
        description="Any other important detail from the document that does not fit above (context, references, exclusions)",
    )
