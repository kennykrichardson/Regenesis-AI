"""
============================================================
REGENESIS
Inference Provider
============================================================

LLM inference layer for Regenesis.

Responsibilities:
    - Send reconstruction prompts to Hugging Face
      Inference Providers.
    - Keep provider/model configuration outside the
      prompt-building layer.
    - Enforce the maximum generation-token limit.

This module does NOT:
    - build prompts
    - retrieve GitHub repositories
    - analyze repositories
    - modify source code
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

load_dotenv(
    PROJECT_ROOT / ".env"
)


HF_TOKEN = os.getenv(
    "HF_TOKEN"
)

HF_MODEL = os.getenv(
    "HF_MODEL",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
)

HF_PROVIDER = os.getenv(
    "HF_PROVIDER",
    "auto",
)


# ============================================================
# Limits
# ============================================================

MAX_OUTPUT_TOKENS: Final = 6_000

DEFAULT_TEMPERATURE: Final = 0.2

DEFAULT_TOP_P: Final = 0.9

DEFAULT_TIMEOUT: Final = 180


# ============================================================
# API
# ============================================================

HF_INFERENCE_URL: Final = (
    "https://router.huggingface.co/v1/chat/completions"
)


# ============================================================
# Exceptions
# ============================================================

class InferenceError(Exception):
    """Base exception for inference failures."""


class InferenceAuthenticationError(
    InferenceError
):
    """Hugging Face authentication failed."""


class InferenceRateLimitError(
    InferenceError
):
    """Inference provider rate limit was exceeded."""


class InferenceResponseError(
    InferenceError
):
    """Inference provider returned an invalid response."""


# ============================================================
# Configuration
# ============================================================

@dataclass(
    slots=True,
    frozen=True,
)
class InferenceConfig:

    """
    Configuration for an inference request.
    """

    model: str = HF_MODEL

    provider: str = HF_PROVIDER

    temperature: float = DEFAULT_TEMPERATURE

    top_p: float = DEFAULT_TOP_P

    max_tokens: int = MAX_OUTPUT_TOKENS

    timeout: int = DEFAULT_TIMEOUT


def get_inference_config() -> InferenceConfig:
    """
    Build the current inference configuration from the
    environment.
    """

    return InferenceConfig(

        model=os.getenv(
            "HF_MODEL",
            HF_MODEL,
        ),

        provider=os.getenv(
            "HF_PROVIDER",
            HF_PROVIDER,
        ),

        temperature=float(
            os.getenv(
                "HF_TEMPERATURE",
                str(DEFAULT_TEMPERATURE),
            )
        ),

        top_p=float(
            os.getenv(
                "HF_TOP_P",
                str(DEFAULT_TOP_P),
            )
        ),

        max_tokens=min(

            int(
                os.getenv(
                    "HF_MAX_TOKENS",
                    str(MAX_OUTPUT_TOKENS),
                )
            ),

            MAX_OUTPUT_TOKENS,

        ),

        timeout=int(
            os.getenv(
                "HF_TIMEOUT",
                str(DEFAULT_TIMEOUT),
            )
        ),

    )


# ============================================================
# Validation
# ============================================================

def validate_inference_environment() -> None:
    """
    Validate the environment required for Hugging Face
    inference.
    """

    token = os.getenv(
        "HF_TOKEN"
    )

    if not token:

        raise InferenceAuthenticationError(
            "Missing HF_TOKEN."
        )


# ============================================================
# Request Construction
# ============================================================

def build_headers() -> dict[str, str]:
    """
    Build HTTP headers for the Hugging Face router.
    """

    validate_inference_environment()

    return {
        "Authorization": (
            f"Bearer {os.getenv('HF_TOKEN')}"
        ),
        "Content-Type": "application/json",
    }


def build_payload(
    prompt: str,
    config: InferenceConfig,
) -> dict:

    """
    Construct an OpenAI-compatible chat completion payload.

    The output-token limit is always capped at 6,000.
    """

    max_tokens = min(
        config.max_tokens,
        MAX_OUTPUT_TOKENS,
    )

    return {

        "model": config.model,

        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],

        "temperature": config.temperature,

        "top_p": config.top_p,

        "max_tokens": max_tokens,

    }


# ============================================================
# Response Parsing
# ============================================================

def extract_content(
    payload: dict,
) -> str:
    """
    Extract the generated text from an OpenAI-compatible
    Hugging Face response.
    """

    choices = payload.get(
        "choices"
    )

    if not choices:

        raise InferenceResponseError(
            "Inference provider returned no choices."
        )

    first_choice = choices[0]

    message = first_choice.get(
        "message"
    )

    if not isinstance(
        message,
        dict,
    ):

        raise InferenceResponseError(
            "Inference provider returned an invalid message."
        )

    content = message.get(
        "content"
    )

    if not isinstance(
        content,
        str,
    ):

        raise InferenceResponseError(
            "Inference provider returned no textual content."
        )

    return content


# ============================================================
# Inference
# ============================================================

def generate(
    prompt: str,
    config: InferenceConfig | None = None,
) -> str:

    """
    Send a reconstruction prompt to Hugging Face Inference
    Providers and return the generated response.
    """

    if not prompt.strip():

        raise ValueError(
            "Inference prompt cannot be empty."
        )

    if config is None:

        config = get_inference_config()

    payload = build_payload(
        prompt,
        config,
    )

    try:

        response = requests.post(

            HF_INFERENCE_URL,

            headers=build_headers(),

            json=payload,

            timeout=config.timeout,

        )

    except requests.RequestException as exc:

        raise InferenceError(
            "Failed to contact the Hugging Face "
            "Inference Router."
        ) from exc

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    if response.status_code in {
        401,
        403,
    }:

        raise InferenceAuthenticationError(
            "Hugging Face authentication failed."
        )

    # --------------------------------------------------------
    # Rate limiting
    # --------------------------------------------------------

    if response.status_code == 429:

        raise InferenceRateLimitError(
            "Hugging Face inference rate limit exceeded."
        )

    # --------------------------------------------------------
    # Other failures
    # --------------------------------------------------------

    if response.status_code >= 400:

        try:

            detail = response.json()

        except ValueError:

            detail = response.text

        raise InferenceError(
            "Hugging Face inference failed: "
            f"{detail}"
        )

    # --------------------------------------------------------
    # Parse response
    # --------------------------------------------------------

    try:

        payload = response.json()

    except ValueError as exc:

        raise InferenceResponseError(
            "Hugging Face returned invalid JSON."
        ) from exc

    return extract_content(
        payload
    )


# ============================================================
# Public API
# ============================================================

__all__ = [

    "MAX_OUTPUT_TOKENS",

    "InferenceConfig",

    "InferenceError",

    "InferenceAuthenticationError",

    "InferenceRateLimitError",

    "InferenceResponseError",

    "get_inference_config",

    "validate_inference_environment",

    "build_payload",

    "generate",

]