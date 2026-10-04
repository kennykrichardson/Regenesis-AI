"""
============================================================
REGENESIS
Source Codebase Engine
============================================================

Purpose
-------
Retrieve the source representation of a GitHub repository.

This module is intentionally deterministic.

It does NOT:
    - analyze repository health
    - inspect commits
    - inspect issues
    - inspect pull requests
    - calculate scores
    - invoke an LLM
    - generate prompts

Its only responsibility is:

    GitHub Repository
        ↓
    Git Tree API
        ↓
    Git Blob API
        ↓
    SourceBlob objects
        ↓
    Codebase

The resulting Codebase is consumed by prompt_builder.py.

Author
------
Kenny Richardson
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import quote

import requests

from backend.regenesis import AuthenticationError
from backend.regenesis import GitHubConnectionError
from backend.regenesis import GITHUB_HEADERS
from backend.regenesis import RateLimitError
from backend.regenesis import RepositoryError
from backend.regenesis import get_active_repository
from backend.regenesis import validate_environment


# ============================================================
# GitHub API
# ============================================================

GITHUB_API: Final = "https://api.github.com"

REPOSITORY_ENDPOINT: Final = (
    GITHUB_API +
    "/repos/{owner}/{repo}"
)

TREE_ENDPOINT: Final = (
    GITHUB_API +
    "/repos/{owner}/{repo}/git/trees/{tree}?recursive=1"
)

BLOB_ENDPOINT: Final = (
    GITHUB_API +
    "/repos/{owner}/{repo}/git/blobs/{sha}"
)


# ============================================================
# HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update(
    GITHUB_HEADERS
)


# ============================================================
# Limits
# ============================================================

# Maximum individual blob size we are willing to retrieve.
#
# This is NOT the prompt-token limit.
#
# The complete Codebase may contain more information than can
# fit into one reconstruction request. prompt_builder.py will
# later enforce the reconstruction prompt budget.
#
# 1 MB is large enough for most source/configuration files
# while preventing absurdly large blobs from entering memory.
MAX_BLOB_SIZE: Final = 1_000_000


# Maximum number of cached blobs.
MAX_BLOB_CACHE: Final = 512


# ============================================================
# File Types
# ============================================================

LANGUAGE_MAP: Final = {

    # Python
    ".py": "Python",

    # JavaScript / TypeScript
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",

    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",

    # Web
    ".html": "HTML",
    ".htm": "HTML",

    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",

    # Java / JVM
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",

    # C family
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",

    # C#
    ".cs": "C#",

    # Go
    ".go": "Go",

    # Rust
    ".rs": "Rust",

    # PHP
    ".php": "PHP",

    # Ruby
    ".rb": "Ruby",

    # Swift
    ".swift": "Swift",

    # Dart / Flutter
    ".dart": "Dart",

    # Mobile
    ".m": "Objective-C",
    ".mm": "Objective-C++",

    # Data / configuration
    ".json": "JSON",
    ".jsonc": "JSON",

    ".yaml": "YAML",
    ".yml": "YAML",

    ".toml": "TOML",
    ".xml": "XML",

    ".ini": "INI",
    ".cfg": "Config",
    ".conf": "Config",

    # Database / APIs
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",

    # Documentation
    ".md": "Markdown",
    ".mdx": "MDX",
    ".txt": "Text",

    # Shell
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",

    # Docker
    ".dockerfile": "Dockerfile",

    # Infrastructure
    ".tf": "Terraform",
    ".tfvars": "Terraform",

}


# ============================================================
# Extensionless Text Files
# ============================================================

# These files are important to application reconstruction even
# though they do not have conventional source-code extensions.

SPECIAL_TEXT_FILES: Final = {

    "Dockerfile",
    "Dockerfile.dev",
    "Dockerfile.prod",

    "Makefile",
    "GNUmakefile",

    "Procfile",

    ".dockerignore",

    ".npmrc",
    ".nvmrc",
    ".node-version",

    ".python-version",

    ".editorconfig",

    ".prettierrc",
    ".prettierignore",

    ".eslintrc",
    ".eslintignore",

    ".flake8",

    ".env.example",
    ".env.sample",
    ".env.template",

}


# ============================================================
# Ignored Directories
# ============================================================

# These directories contain dependencies, generated output,
# caches, or source-control internals rather than application
# source that should be reconstructed.

IGNORED_DIRECTORIES: Final = {

    ".git",

    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",

    ".venv",
    "venv",
    "env",

    "node_modules",

    "dist",
    "build",

    ".next",
    ".nuxt",
    ".output",

    ".cache",

    "coverage",
    ".coverage",

    ".tox",

    ".gradle",

    "target",

    "vendor",

    ".dart_tool",

    ".pub-cache",

    ".idea",
    ".vscode",

}


# ============================================================
# Generated / Binary Extensions
# ============================================================

# These should never become part of a reconstruction prompt.

IGNORED_EXTENSIONS: Final = {

    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tiff",
    ".ico",
    ".svg",

    # Video
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",

    # Audio
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",

    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",

    # Compiled binaries
    ".exe",
    ".dll",
    ".so",
    ".dylib",

    # Object files
    ".o",
    ".obj",

    # Bytecode
    ".pyc",
    ".pyo",

    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",

    # Documents that are not source text
    ".pdf",

    # Database binaries
    ".db",
    ".sqlite",
    ".sqlite3",

}


# ============================================================
# Dataclasses
# ============================================================

@dataclass(
    slots=True,
    frozen=True,
)
class TreeEntry:

    """
    A file discovered through the Git Tree API.
    """

    path: str

    sha: str

    size: int


@dataclass(
    slots=True,
    frozen=True,
)
class SourceBlob:

    """
    Exact textual contents of one repository blob.

    The content is deliberately preserved without AI
    summarization or interpretation.
    """

    path: str

    sha: str

    size: int

    language: str

    content: str


@dataclass(
    slots=True,
)
class Codebase:

    """
    Complete source representation of a repository.

    `blobs` contains every eligible textual repository file
    discovered through the Git Tree API.
    """

    repository: str

    branch: str

    blobs: list[SourceBlob]


# ============================================================
# Blob Cache
# ============================================================

_BLOB_CACHE: dict[str, str] = {}


def cache_blob(
    sha: str,
    content: str,
) -> None:

    """
    Store a blob in the in-memory cache.

    A bounded cache prevents a very large repository from
    growing memory indefinitely.
    """

    if len(_BLOB_CACHE) >= MAX_BLOB_CACHE:

        oldest_key = next(
            iter(_BLOB_CACHE)
        )

        del _BLOB_CACHE[
            oldest_key
        ]

    _BLOB_CACHE[sha] = content


# ============================================================
# HTTP
# ============================================================

def github_get(
    url: str,
) -> dict:
    """
    Perform an authenticated GitHub REST request.

    GitHub failures are converted into typed Regenesis
    exceptions so the API layer can return the correct
    HTTP status.
    """

    validate_environment()

    try:
        response = SESSION.get(
            url,
            timeout=30,
            allow_redirects=True,
        )

    except requests.RequestException as exc:

        raise GitHubConnectionError(
            f"Failed to contact the GitHub API: {exc}"
        ) from exc

    if response.status_code == 401:
        raise AuthenticationError(
            "GitHub authentication failed. "
            "Check GITHUB_TOKEN."
        )

    if response.status_code == 403:
        raise RateLimitError(
            "GitHub API rate limit exceeded."
        )

    if response.status_code == 404:
        raise RepositoryError(
            "GitHub repository, branch, or resource was not found."
        )

    if response.status_code >= 400:
        raise RepositoryError(
            f"GitHub API request failed with HTTP "
            f"{response.status_code}."
        )

    try:
        return response.json()

    except ValueError as exc:
        raise RepositoryError(
            "GitHub returned an invalid JSON response."
        ) from exc


# ============================================================
# Path Helpers
# ============================================================

def extension(
    path: str,
) -> str:

    """
    Return a lowercase file extension.
    """

    return PurePosixPath(
        path
    ).suffix.lower()


def filename(
    path: str,
) -> str:

    """
    Return the final component of a repository path.
    """

    return PurePosixPath(
        path
    ).name


def language_of(
    path: str,
) -> str:

    """
    Determine the human-readable language of a file.
    """

    name = filename(path)

    if name == "Dockerfile":
        return "Dockerfile"

    if name.startswith("Dockerfile."):
        return "Dockerfile"

    return LANGUAGE_MAP.get(
        extension(path),
        "Unknown",
    )


def inside_ignored_directory(
    path: str,
) -> bool:

    """
    Determine whether a path belongs to an ignored directory.
    """

    return any(
        part in IGNORED_DIRECTORIES
        for part in PurePosixPath(path).parts
    )


# ============================================================
# File Filtering
# ============================================================

def is_special_text_file(
    path: str,
) -> bool:

    """
    Determine whether an extensionless configuration or
    documentation file should be retained.
    """

    return filename(path) in SPECIAL_TEXT_FILES


def supported_file(
    path: str,
    size: int,
) -> bool:

    """
    Determine whether a repository tree entry represents
    usable textual source/configuration content.
    """

    if size <= 0:
        return False

    if size > MAX_BLOB_SIZE:
        return False

    if inside_ignored_directory(path):
        return False

    name = filename(path)

    if name in SPECIAL_TEXT_FILES:
        return True

    suffix = extension(path)

    if suffix in IGNORED_EXTENSIONS:
        return False

    return suffix in LANGUAGE_MAP


# ============================================================
# Repository Metadata
# ============================================================

def fetch_default_branch(
    owner: str,
    repository: str,
) -> str:

    """
    Retrieve the repository's default branch.
    """

    payload = github_get(

        REPOSITORY_ENDPOINT.format(
            owner=owner,
            repo=repository,
        )

    )

    branch = payload.get(
        "default_branch"
    )

    if not branch:

        raise RuntimeError(
            "GitHub repository does not expose a default branch."
        )

    return branch


# ============================================================
# Repository Tree
# ============================================================

def fetch_repository_tree(
    owner: str,
    repository: str,
    branch: str,
) -> list[TreeEntry]:
    """
    Retrieve the complete recursive Git tree for a branch.
    """

    if not branch.strip():
        raise ValueError(
            "Branch cannot be empty."
        )

    encoded_branch = quote(
        branch.strip(),
        safe="",
    )

    payload = github_get(
        TREE_ENDPOINT.format(
            owner=owner,
            repo=repository,
            tree=encoded_branch,
        )
    )

    if payload.get("truncated"):
        raise RepositoryError(
            "GitHub returned a truncated repository tree. "
            "The repository is too large to reconstruct safely "
            "with a single recursive tree request."
        )

    entries = payload.get("tree", [])

    result: list[TreeEntry] = []

    for entry in entries:

        if entry.get("type") != "blob":
            continue

        path = entry.get("path")
        sha = entry.get("sha")
        size = entry.get("size", 0)

        if not path or not sha:
            continue

        result.append(
            TreeEntry(
                path=path,
                sha=sha,
                size=size,
            )
        )

    return result


# ============================================================
# Blob API
# ============================================================

def fetch_blob(
    owner: str,
    repository: str,
    sha: str,
) -> str:

    """
    Retrieve and decode an individual Git blob.

    GitHub normally returns blob content as Base64.
    """

    cached = _BLOB_CACHE.get(
        sha
    )

    if cached is not None:
        return cached

    payload = github_get(

        BLOB_ENDPOINT.format(
            owner=owner,
            repo=repository,
            sha=sha,
        )

    )

    encoding = payload.get(
        "encoding"
    )

    content = payload.get(
        "content"
    )

    if encoding != "base64":

        raise RuntimeError(
            f"Unsupported GitHub blob encoding: {encoding!r}"
        )

    if not isinstance(content, str):

        raise RuntimeError(
            f"GitHub returned invalid blob content for {sha}."
        )

    try:

        raw = base64.b64decode(
            content,
            validate=False,
        )

    except Exception as exc:

        raise RuntimeError(
            f"Failed to decode GitHub blob {sha}."
        ) from exc

    try:

        text = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:

        raise RuntimeError(
            f"Blob {sha} is not valid UTF-8 text."
        ) from exc

    cache_blob(
        sha,
        text,
    )

    return text


# ============================================================
# Blob Construction
# ============================================================

def build_source_blob(
    owner: str,
    repository: str,
    entry: TreeEntry,
) -> SourceBlob:

    """
    Convert one Git tree entry into an exact SourceBlob.
    """

    content = fetch_blob(

        owner=owner,

        repository=repository,

        sha=entry.sha,

    )

    return SourceBlob(

        path=entry.path,

        sha=entry.sha,

        size=entry.size,

        language=language_of(
            entry.path
        ),

        content=content,

    )


# ============================================================
# Deterministic Ordering
# ============================================================

def blob_sort_key(
    blob: SourceBlob,
) -> tuple[int, str]:

    """
    Produce a deterministic ordering for source blobs.

    Configuration and entry-point files appear first so that
    downstream prompt construction encounters the architecture
    before implementation details.

    This does NOT exclude any file.
    """

    name = filename(
        blob.path
    )

    path = blob.path.lower()

    # Repository configuration
    if name in {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "pubspec.yaml",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "tsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "next.config.ts",
    }:
        priority = 0

    # Application entry points
    elif name in {
        "main.py",
        "app.py",
        "main.ts",
        "main.tsx",
        "main.js",
        "main.jsx",
        "index.ts",
        "index.tsx",
        "index.js",
        "index.jsx",
        "App.tsx",
        "App.jsx",
    }:
        priority = 1

    # Source
    elif "/src/" in f"/{path}/" or path.startswith("src/"):
        priority = 2

    # Configuration / infrastructure
    elif (
        "config" in path
        or ".github/" in path
        or path.startswith(".github/")
    ):
        priority = 3

    # Tests
    elif (
        "test" in path
        or "spec" in path
    ):
        priority = 4

    # Documentation
    elif blob.language in {
        "Markdown",
        "Text",
    }:
        priority = 5

    else:
        priority = 3

    return (
        priority,
        blob.path.lower(),
    )


# ============================================================
# Codebase Construction
# ============================================================

def build_codebase(
    repository: str | None = None,
    branch: str | None = None,
) -> Codebase:

    """
    Build the complete deterministic source representation
    of a GitHub repository.

    Parameters
    ----------
    repository:
        GitHub repository in either:

            owner/repository

        or:

            https://github.com/owner/repository

        If omitted, the active Regenesis repository is used.

    branch:
        Branch to reconstruct.

        If omitted, the repository's default branch is used.

    Returns
    -------
    Codebase
        A collection of every eligible textual source/configuration
        blob in deterministic order.
    """

    if repository is not None:

        from backend.regenesis import set_active_repository

        config = set_active_repository(
            repository
        )

    else:

        config = get_active_repository()

    owner = config.owner

    repo = config.repository

    if branch is None:

        branch = fetch_default_branch(
            owner=owner,
            repository=repo,
        )

    tree = fetch_repository_tree(

        owner=owner,

        repository=repo,

        branch=branch,

    )

    blobs: list[SourceBlob] = []

    for entry in tree:

        if not supported_file(
            entry.path,
            entry.size,
        ):
            continue

        try:
            blob = build_source_blob(
                owner=owner,
                repository=repo,
                entry=entry,
            )


        except RepositoryError:
            raise

        except AuthenticationError:
            raise

        except RateLimitError:
            raise

        except RuntimeError:
            continue

        blobs.append(
            blob
        )

    blobs.sort(
        key=blob_sort_key
    )

    return Codebase(

        repository=f"{owner}/{repo}",

        branch=branch,

        blobs=blobs,

    )


# ============================================================
# Public API
# ============================================================

def fetch_codebase() -> Codebase:

    """
    Convenience wrapper for the active repository.
    """

    return build_codebase()


__all__ = [

    "TreeEntry",

    "SourceBlob",

    "Codebase",

    "LANGUAGE_MAP",

    "SPECIAL_TEXT_FILES",

    "IGNORED_DIRECTORIES",

    "IGNORED_EXTENSIONS",

    "fetch_default_branch",

    "fetch_repository_tree",

    "fetch_blob",

    "supported_file",

    "language_of",

    "build_source_blob",

    "build_codebase",

    "fetch_codebase",

]