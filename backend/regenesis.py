"""
============================================================
REGENESIS
Core Configuration
============================================================

Shared configuration and GitHub repository utilities.

Regenesis' current pipeline is:

    GitHub repository
        ↓
    codebase.py
        ↓
    prompt_builder.py

This module contains only the configuration required by that
pipeline.

It does NOT:
    - inspect commits
    - inspect issues
    - inspect pull requests
    - calculate repository health
    - run GraphQL queries
    - call inference providers
    - generate prompts
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


# ============================================================
# Project Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BACKEND_DIR = PROJECT_ROOT / "backend"

load_dotenv(
    PROJECT_ROOT / ".env"
)


# ============================================================
# Environment
# ============================================================

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN"
)


# ============================================================
# GitHub
# ============================================================

GITHUB_API = "https://api.github.com"


GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json",
}


# ============================================================
# Exceptions
# ============================================================


class GitHubError(Exception):

    """Base exception for GitHub-related failures."""


class AuthenticationError(GitHubError):

    """GitHub authentication failed."""


class RateLimitError(GitHubError):

    """GitHub API rate limit was exceeded."""


class RepositoryError(GitHubError):

    """GitHub repository or branch could not be accessed."""


class GitHubConnectionError(GitHubError):

    """The GitHub API could not be contacted."""


# ============================================================
# Repository Configuration
# ============================================================

@dataclass(
    slots=True,
    frozen=True,
)
class RepositoryConfig:

    """
    Parsed GitHub repository information.
    """

    owner: str

    repository: str

    url: str


# ============================================================
# Repository Parsing
# ============================================================

def parse_repository_url(
    repository: str,
) -> RepositoryConfig:
    """
    Parse a GitHub repository supplied as either:

        owner/repository

    or:

        https://github.com/owner/repository

    Query strings and fragments are ignored.
    """

    value = repository.strip()

    if not value:
        raise ValueError(
            "Repository cannot be empty."
        )

    # --------------------------------------------------------
    # Full GitHub URL
    # --------------------------------------------------------

    if (
        value.startswith("https://")
        or value.startswith("http://")
    ):

        parsed = urlparse(
            value
        )

        if parsed.netloc.lower() != "github.com":

            raise ValueError(
                "Repository URL must point to github.com."
            )

        path = parsed.path.strip(
            "/"
        )

    else:

        path = value.strip(
            "/"
        )

    # --------------------------------------------------------
    # Remove optional .git suffix
    # --------------------------------------------------------

    if path.endswith(
        ".git"
    ):

        path = path[:-4]

    # --------------------------------------------------------
    # Repository path
    # --------------------------------------------------------

    parts = [
        part
        for part in path.split("/")
        if part
    ]

    if len(parts) != 2:

        raise ValueError(
            "Expected owner/repository or a GitHub repository URL."
        )

    owner, repo = parts

    if not owner or not repo:

        raise ValueError(
            "Both GitHub owner and repository are required."
        )

    return RepositoryConfig(

        owner=owner,

        repository=repo,

        url=(
            f"https://github.com/"
            f"{owner}/{repo}"
        ),

    )


# ============================================================
# Default Repository
# ============================================================

DEFAULT_REPOSITORY = os.getenv(
    "REGENESIS_DEFAULT_REPOSITORY"
)


ACTIVE_REPOSITORY = (

    parse_repository_url(
        DEFAULT_REPOSITORY
    )

    if DEFAULT_REPOSITORY

    else None

)


def set_active_repository(
    repository: str,
) -> RepositoryConfig:
    """
    Set the repository used by the backend when an explicit
    repository is not passed to lower-level functions.
    """

    global ACTIVE_REPOSITORY

    ACTIVE_REPOSITORY = parse_repository_url(
        repository
    )

    return ACTIVE_REPOSITORY


def get_active_repository() -> RepositoryConfig:
    """
    Return the currently configured repository.
    """

    if ACTIVE_REPOSITORY is None:

        raise RepositoryError(
            "No active repository configured. "
            "Send a repository in the API request or set "
            "REGENESIS_DEFAULT_REPOSITORY."
        )

    return ACTIVE_REPOSITORY


# ============================================================
# Environment Validation
# ============================================================

def validate_environment() -> None:
    """
    Validate the environment required for GitHub access.
    """

    if not GITHUB_TOKEN:

        raise AuthenticationError(
            "Missing GITHUB_TOKEN."
        )


# ============================================================
# Public API
# ============================================================

__all__ = [
    "PROJECT_ROOT",
    "BACKEND_DIR",
    "GITHUB_TOKEN",
    "GITHUB_API",
    "GITHUB_HEADERS",
    "GitHubError",
    "AuthenticationError",
    "RateLimitError",
    "RepositoryError",
    "GitHubConnectionError",
    "RepositoryConfig",
    "parse_repository_url",
    "set_active_repository",
    "get_active_repository",
    "validate_environment",
]