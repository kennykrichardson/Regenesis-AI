"""
============================================================
REGENESIS
API Schemas
============================================================

Pydantic models used by the Regenesis API.

Regenesis' current responsibility is simple:

    GitHub repository
        ↓
    source blobs
        ↓
    reconstruction prompt

These schemas intentionally contain no repository grading,
health, commit, issue, or AI-review models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ============================================================
# Requests
# ============================================================

class PromptRequest(BaseModel):
    repository: str = Field(
        ...,
        min_length=1,
        description="GitHub repository URL or owner/repository.",
        examples=["react/react"],
    )

    branch: str | None = Field(
        default=None,
        description="Optional branch. If omitted, Regenesis uses the repository's default branch.",
        examples=["main"],
    )

# ============================================================
# Responses
# ============================================================

class PromptResponse(BaseModel):
    """
    Response containing the generated reconstruction prompt.
    """

    repository: str

    branch: str

    prompt: str

    included_files: list[str]

    excluded_files: list[str]

    estimated_tokens: int