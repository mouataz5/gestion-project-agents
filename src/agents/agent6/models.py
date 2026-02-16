"""
Agent 6 (Documentation Writer) — Pydantic models for generated docs.

Aligns with Cahier des Charges: OF6.1 API docs, OF6.2 JSDoc/TSDoc, OF6.6 language, OF6.7 obsolete, OF6.8 coverage.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class APIFunctionDoc(BaseModel):
    """Documentation for one function or method (OF6.1). JSDoc/TSDoc content in description (OF6.2)."""

    name: str = Field(..., description="Function or method name")
    signature: str | None = Field(default=None, description="Signature if available")
    description: str = Field(default="", description="Brief description or extracted docstring/JSDoc/TSDoc")


class APIModuleDoc(BaseModel):
    """Documentation for one module or file (OF6.1)."""

    module_path: str = Field(..., description="Relative path (e.g. src/agents/agent1/models.py)")
    description: str = Field(default="", description="Module purpose")
    functions: list[APIFunctionDoc] = Field(
        default_factory=list,
        description="Public functions/classes to document",
    )


class DocumentationResult(BaseModel):
    """Full documentation output: README, API docs, coverage, obsolete warnings, language (OF6.1–OF6.8)."""

    readme_content: str = Field(
        default="",
        description="Generated README content (overview, setup, usage)",
    )
    api_docs: list[APIModuleDoc] = Field(
        default_factory=list,
        description="API documentation per module",
    )
    documentation_coverage_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="OF6.8: Documentation coverage 0–100% (documented modules / total discoverable modules)",
    )
    obsolete_doc_warnings: list[str] = Field(
        default_factory=list,
        description="OF6.7: Suspected obsolete documentation (e.g. README older than code, missing recent files)",
    )
    language: Literal["en", "fr", "es"] = Field(
        default="en",
        description="OF6.6: Language of the generated documentation (en/fr/es)",
    )
