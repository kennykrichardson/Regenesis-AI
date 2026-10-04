"""
============================================================
REGENESIS
API Routes
============================================================

HTTP endpoints for the Regenesis source-to-prompt pipeline.

Pipeline:

    GitHub repository
        ↓
    Codebase
        ↓
    Reconstruction prompt
        ↓
    Optional inference
        ↓
    Generated response
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

from backend.codebase import build_codebase
from backend.inference import InferenceAuthenticationError
from backend.inference import InferenceError
from backend.inference import InferenceRateLimitError
from backend.inference import generate
from backend.inference import get_inference_config
from backend.prompt_builder import build_prompt_result
from backend.regenesis import AuthenticationError
from backend.regenesis import GitHubConnectionError
from backend.regenesis import RateLimitError
from backend.regenesis import RepositoryError
from backend.schemas import PromptRequest
from backend.schemas import PromptResponse


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/api",
    tags=["prompt"],
)


# ============================================================
# Generation Schemas
# ============================================================

class GenerateRequest(BaseModel):
    """
    Request to send a reconstruction prompt to the configured
    inference provider.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        description="Reconstruction prompt to send to the LLM.",
    )


class GenerateResponse(BaseModel):
    """
    Generated response returned by the inference provider.
    """

    response: str

    model: str

    provider: str


# ============================================================
# Prompt Generation
# ============================================================

@router.post(
    "/prompt",
    response_model=PromptResponse,
)
def generate_prompt(
    request: PromptRequest,
) -> PromptResponse:
    """
    Retrieve a repository and construct its deterministic
    reconstruction prompt.
    """

    try:

        codebase = build_codebase(
            repository=request.repository,
            branch=request.branch,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except AuthenticationError as exc:

        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    except RateLimitError as exc:

        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    except GitHubConnectionError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except RepositoryError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error while retrieving repository "
                f"source: {exc}"
            ),
        ) from exc

    try:

        result = build_prompt_result(
            codebase
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to construct the reconstruction prompt: "
                f"{exc}"
            ),
        ) from exc

    return PromptResponse(
        repository=codebase.repository,
        branch=codebase.branch,
        prompt=result.prompt,
        included_files=list(
            result.included_files
        ),
        excluded_files=list(
            result.excluded_files
        ),
        estimated_tokens=result.estimated_tokens,
    )


# ============================================================
# LLM Generation
# ============================================================

@router.post(
    "/generate",
    response_model=GenerateResponse,
)
def generate_response(
    request: GenerateRequest,
) -> GenerateResponse:
    """
    Send a reconstruction prompt to the configured Hugging Face
    Inference Provider.
    """

    try:

        config = get_inference_config()

        response = generate(

            prompt=request.prompt,

            config=config,

        )

    except InferenceAuthenticationError as exc:

        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    except InferenceRateLimitError as exc:

        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    except InferenceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return GenerateResponse(

        response=response,

        model=config.model,

        provider=config.provider,

    )


# ============================================================
# Health Check
# ============================================================

@router.get(
    "/health",
)
def health_check() -> dict[str, str]:
    """
    Basic backend health endpoint.

    This is an operational check and has nothing to do with
    repository health scoring.
    """

    return {
        "status": "ok",
    }


# ============================================================
# Public API
# ============================================================

__all__ = [
    "router",
    "generate_prompt",
    "generate_response",
    "health_check",
]