"""
Agent 3 (Code Reviewer) — Pydantic models for review output.

Structured findings: bugs, security issues, style violations.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """One review finding (bug, security, or style)."""

    category: Literal["bug", "security", "style"] = Field(
        ...,
        description="Type of issue",
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Severity of the finding",
    )
    file_path: str | None = Field(
        default=None,
        description="File path (if applicable)",
    )
    line_start: int | None = Field(
        default=None,
        description="Start line number (1-based)",
    )
    message: str = Field(..., description="Short description of the issue")
    suggestion: str | None = Field(
        default=None,
        description="Suggested fix or improvement",
    )


class CodeReviewResult(BaseModel):
    """Output of Agent 3: full code review."""

    findings: list[Finding] = Field(
        default_factory=list,
        description="List of review findings",
    )
    summary: str = Field(
        default="",
        description="Brief overall review summary",
    )


class CritiqueOutput(BaseModel):
    """Critic agent output: additional findings and comment on the draft review."""

    additional_findings: list[Finding] = Field(
        default_factory=list,
        description="Findings the critic thinks the reviewer missed",
    )
    comment: str = Field(
        default="",
        description="Critique of the draft review",
    )
