"""
Agent 5 (Risk Predictor) — Pydantic models for delay/risk analysis.

Aligns with Cahier des Charges: OF5.1–OF5.8 (metrics, delays, budget, team overload,
dependencies, probability/impact, mitigation plans, alerts).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    """One identified risk with evidence (OF5.6: probability and impact)."""

    factor: str = Field(..., description="Short name of the risk (e.g. 'Database tasks overrun')")
    description: str = Field(..., description="Brief explanation")
    severity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Severity of the risk",
    )
    probability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Estimated probability of occurrence (0–1)",
    )
    impact: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Impact if risk materializes",
    )
    evidence: str = Field(
        default="",
        description="Data supporting this (e.g. 'Database: avg actual 1.5x estimated')",
    )


class MitigationPlan(BaseModel):
    """OF5.7: One automatic mitigation action."""

    action: str = Field(..., description="Concrete action to reduce risk")
    owner_suggestion: str = Field(
        default="",
        description="Suggested owner (role or team)",
    )
    priority: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Priority of this mitigation",
    )


class Alert(BaseModel):
    """OF5.8: Alert with suggested corrective action."""

    level: Literal["info", "warning", "critical"] = Field(
        ...,
        description="Alert level",
    )
    message: str = Field(..., description="Alert message")
    suggested_action: str = Field(
        default="",
        description="Corrective action to take",
    )


class DelayPrediction(BaseModel):
    """Observed or predicted delay for a category or dimension."""

    category: str = Field(..., description="Category (e.g. Database, Backend) or 'Overall'")
    avg_estimated_hours: float = Field(..., description="Average estimated hours")
    avg_actual_hours: float = Field(..., description="Average actual hours")
    delay_ratio: float = Field(..., description="actual / estimated (e.g. 1.5 = 50% overrun)")
    ticket_count: int = Field(default=0, description="Number of tickets in this category")


class RiskReport(BaseModel):
    """Full risk report (OF5.1–OF5.8): metrics, delays, budget, team, dependencies, mitigations, alerts."""

    summary: str = Field(
        default="",
        description="Short overall summary of project delay risk",
    )
    risk_factors: list[RiskFactor] = Field(
        default_factory=list,
        description="Identified risks with probability/impact and evidence",
    )
    delay_predictions: list[DelayPrediction] = Field(
        default_factory=list,
        description="By-category (or overall) delay stats and ratios (OF5.2)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Suggested actions to reduce delay risk",
    )
    mitigation_plans: list[MitigationPlan] = Field(
        default_factory=list,
        description="OF5.7: Automatic mitigation plans",
    )
    alerts: list[Alert] = Field(
        default_factory=list,
        description="OF5.8: Alerts and corrective actions",
    )
    budget_risks: list[str] = Field(
        default_factory=list,
        description="OF5.3: Budget overrun risks (when derivable from data)",
    )
    team_overload_risks: list[str] = Field(
        default_factory=list,
        description="OF5.4: Team members overload/burnout risks",
    )
    dependency_risks: list[str] = Field(
        default_factory=list,
        description="OF5.5: Blocking technical dependency risks",
    )
