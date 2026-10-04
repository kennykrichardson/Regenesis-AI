"""
============================================================
REGENESIS
Prompt Builder
============================================================

Purpose
-------
Convert a retrieved Codebase into a deterministic,
high-fidelity reconstruction prompt for coding agents.

Supported consumers include:
    - Codex
    - Claude Code
    - Antigravity
    - Other autonomous coding agents

This module does NOT:
    - call an LLM
    - summarize source code
    - inspect commits
    - inspect issues
    - inspect pull requests
    - calculate repository health
    - invent application functionality

Its responsibility is:

    Codebase
        ↓
    deterministic file classification
        ↓
    dependency discovery
        ↓
    dependency-aware source selection
        ↓
    reconstruction prompt
"""

from __future__ import annotations

import posixpath
import re
from collections import deque
from dataclasses import dataclass
from typing import Final

from backend.codebase import Codebase
from backend.codebase import SourceBlob


# ============================================================
# Configuration
# ============================================================

MAX_PROMPT_TOKENS: Final = 14_000

MAX_SOURCE_TOKENS: Final = 12_000

CHARS_PER_TOKEN: Final = 4

MAX_CRITICAL_FILES: Final = 64

MAX_CRITICAL_SOURCE_FILE_TOKENS: Final = 4_000


# ============================================================
# File Categories
# ============================================================

CONFIGURATION_FILES: Final = {
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",

    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "Pipfile.lock",

    "Cargo.toml",
    "Cargo.lock",

    "go.mod",
    "go.sum",

    "pom.xml",
    "build.gradle",
    "build.gradle.kts",

    "pubspec.yaml",
    "pubspec.lock",

    "composer.json",

    "Gemfile",
    "Gemfile.lock",

    "tsconfig.json",
    "jsconfig.json",

    "vite.config.js",
    "vite.config.ts",

    "next.config.js",
    "next.config.ts",

    "nuxt.config.js",
    "nuxt.config.ts",

    "astro.config.js",
    "astro.config.ts",

    "svelte.config.js",
    "svelte.config.ts",

    "webpack.config.js",
    "webpack.config.ts",

    "babel.config.js",
    "babel.config.json",

    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",

    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",

    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",

    "docker-compose.yml",
    "docker-compose.yaml",

    "Dockerfile",
    "Dockerfile.dev",
    "Dockerfile.prod",

    "Makefile",
}


ENTRY_POINT_FILES: Final = {
    "main.py",
    "app.py",
    "server.py",

    "main.ts",
    "main.tsx",
    "main.js",
    "main.jsx",

    "Program.cs",
    "Main.java",
}


WEB_ENTRY_POINT_FILES: Final = {
    "index.html",

    "main.js",
    "main.jsx",
    "main.ts",
    "main.tsx",
}


APPLICATION_DIRECTORIES: Final = {
    "src",
    "app",
    "apps",
    "components",
    "pages",
    "routes",
    "views",
    "screens",
    "services",
    "api",
    "lib",
    "core",
    "hooks",
    "stores",
    "state",
    "models",
    "controllers",
    "utils",
}


STYLING_LANGUAGES: Final = {
    "CSS",
    "SCSS",
    "Sass",
    "Less",
}


TEST_DIRECTORY_NAMES: Final = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
}


DOCUMENTATION_FILES: Final = {
    "README",
    "README.md",
    "README.txt",
}


NON_FUNCTIONAL_FILES: Final = {
    "LICENSE",
    "LICENSE.md",
    "LICENCE",
    "LICENCE.md",

    ".gitignore",
    ".gitattributes",
    ".editorconfig",
}


# ============================================================
# Dependency Patterns
# ============================================================

PYTHON_IMPORT_PATTERN: Final = re.compile(
    r"""
    (?:
        ^\s*from\s+([A-Za-z_][\w.]*)\s+import
        |
        ^\s*import\s+([A-Za-z_][\w.]*)
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


JAVASCRIPT_IMPORT_PATTERN: Final = re.compile(
    r"""
    (?:
        import\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']
        |
        export\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']
        |
        require\(\s*["']([^"']+)["']\s*\)
        |
        import\(\s*["']([^"']+)["']\s*\)
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


HTML_REFERENCE_PATTERN: Final = re.compile(
    r"""
    (?:
        (?:src|href)\s*=\s*["']([^"']+)["']
        |
        url\(\s*["']?([^"')]+)["']?\s*\)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ============================================================
# Data Structures
# ============================================================

@dataclass(
    slots=True,
    frozen=True,
)
class PromptFile:

    """
    A repository source blob considered for prompt inclusion.
    """

    blob: SourceBlob

    priority: int

    estimated_tokens: int


@dataclass(
    slots=True,
    frozen=True,
)
class PromptBuildResult:

    """
    Result of deterministic prompt construction.
    """

    prompt: str

    included_files: tuple[str, ...]

    excluded_files: tuple[str, ...]

    estimated_tokens: int


# ============================================================
# Token Estimation
# ============================================================

def estimate_tokens(
    text: str,
) -> int:

    """
    Estimate token count deterministically.

    The exact tokenizer depends on the downstream model, so
    Regenesis intentionally uses a character-based estimate.
    """

    if not text:

        return 0

    return max(
        1,
        (
            len(text)
            + CHARS_PER_TOKEN
            - 1
        )
        // CHARS_PER_TOKEN,
    )


# ============================================================
# Path Helpers
# ============================================================

def basename(
    path: str,
) -> str:

    """
    Return the final repository path component.
    """

    return path.replace(
        "\\",
        "/",
    ).rsplit(
        "/",
        1,
    )[-1]


def normalized_path(
    path: str,
) -> str:

    """
    Normalize a repository path for deterministic comparisons.
    """

    return path.replace(
        "\\",
        "/",
    ).lower()


def path_parts(
    path: str,
) -> tuple[str, ...]:

    """
    Return normalized repository path components.
    """

    return tuple(
        part
        for part in normalized_path(
            path
        ).split("/")
        if part
    )


def path_without_extension(
    path: str,
) -> str:

    """
    Return a normalized path without its final extension.
    """

    normalized = normalized_path(
        path
    )

    if "." not in basename(
        normalized
    ):

        return normalized

    return normalized.rsplit(
        ".",
        1,
    )[0]


# ============================================================
# File Classification
# ============================================================

def is_configuration_file(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file describes project configuration,
    dependencies, or build/runtime behavior.
    """

    return basename(
        blob.path
    ) in CONFIGURATION_FILES


def is_entry_point(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file is an application entry point.
    """

    name = basename(
        blob.path
    )

    return (
        name in ENTRY_POINT_FILES
        or name in WEB_ENTRY_POINT_FILES
    )


def is_documentation(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file is repository documentation.
    """

    return basename(
        blob.path
    ) in DOCUMENTATION_FILES


def is_non_functional_file(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file is metadata that should not consume
    reconstruction source budget.
    """

    return basename(
        blob.path
    ) in NON_FUNCTIONAL_FILES


def is_test_file(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file appears to contain tests.
    """

    parts = path_parts(
        blob.path
    )

    if any(
        part in TEST_DIRECTORY_NAMES
        for part in parts
    ):

        return True

    name = basename(
        blob.path
    ).lower()

    return (
        ".test." in name
        or ".spec." in name
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def is_application_directory(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a file lives inside a likely application
    source directory.
    """

    parts = path_parts(
        blob.path
    )

    return any(
        part in APPLICATION_DIRECTORIES
        for part in parts
    )


def is_source_file(
    blob: SourceBlob,
) -> bool:

    """
    Determine whether a blob appears to be application source.
    """

    if is_configuration_file(
        blob
    ):

        return False

    if is_documentation(
        blob
    ):

        return False

    if is_non_functional_file(
        blob
    ):

        return False

    if is_test_file(
        blob
    ):

        return False

    return blob.language not in {
        "Unknown",
        "Text",
        "Markdown",
    }


# ============================================================
# File Priority
# ============================================================

def file_priority(
    blob: SourceBlob,
) -> int:

    """
    Assign deterministic reconstruction priority.

    Lower numbers are more important.
    """

    path = normalized_path(
        blob.path
    )

    name = basename(
        blob.path
    )

    if is_non_functional_file(
        blob
    ):

        return 100

    if name in WEB_ENTRY_POINT_FILES:

        return 10

    if is_configuration_file(
        blob
    ):

        return 20

    if name in ENTRY_POINT_FILES:

        return 25

    if path.startswith(
        "src/"
    ) or "/src/" in path:

        return 30

    if is_application_directory(
        blob
    ):

        return 35

    if blob.language in STYLING_LANGUAGES:

        return 45

    if (
        ".github/" in path
        or path.startswith(".github/")
    ):

        return 55

    if is_test_file(
        blob
    ):

        return 70

    if is_documentation(
        blob
    ):

        return 90

    return 60


# ============================================================
# Prompt File Preparation
# ============================================================

def prepare_files(
    codebase: Codebase,
) -> list[PromptFile]:

    """
    Convert every Codebase blob into a deterministically ranked
    prompt candidate.
    """

    files = [
        PromptFile(
            blob=blob,
            priority=file_priority(
                blob
            ),
            estimated_tokens=estimate_tokens(
                blob.content
            ),
        )
        for blob in codebase.blobs
    ]

    files.sort(
        key=lambda item: (
            item.priority,
            item.estimated_tokens,
            normalized_path(
                item.blob.path
            ),
        )
    )

    return files


# ============================================================
# Candidate Index
# ============================================================

def build_candidate_index(
    candidates: list[PromptFile],
) -> dict[str, PromptFile]:

    """
    Build a normalized repository-path index.
    """

    return {
        normalized_path(
            candidate.blob.path
        ): candidate
        for candidate in candidates
    }


# ============================================================
# Reference Resolution
# ============================================================

def candidate_for_path(
    path: str,
    index: dict[str, PromptFile],
) -> PromptFile | None:

    """
    Resolve a repository-relative path against the candidate index.
    """

    normalized = normalized_path(
        path
    ).lstrip(
        "/"
    )

    direct = index.get(
        normalized
    )

    if direct is not None:

        return direct

    if normalized.startswith(
        "public/"
    ):

        return index.get(
            normalized
        )

    public_candidate = index.get(
        f"public/{normalized}"
        )

    if public_candidate is not None:

        return public_candidate

    return None


def resolve_relative_path(
    source_path: str,
    reference: str,
    index: dict[str, PromptFile],
) -> PromptFile | None:
    """
    Resolve a local source reference to a repository candidate.

    Supports:
        ./foo
        ../foo
        /foo
        ./foo.tsx
        ./foo/index.tsx
        /assets/foo.css

    External URLs, package names, anchors, data URLs, and query
    strings are ignored.
    """

    value = reference.strip()

    if not value:
        return None

    if value.startswith(
        (
            "#",
            "data:",
            "http://",
            "https://",
            "//",
            "mailto:",
            "tel:",
        )
    ):
        return None

    value = value.split("#", 1)[0]
    value = value.split("?", 1)[0]

    if not value:
        return None

    source_directory = posixpath.dirname(
        normalized_path(source_path)
    )

    # ------------------------------------------------------------
    # Build repository-relative base path
    # ------------------------------------------------------------

    if value.startswith("/"):
        base_path = value.lstrip("/")
    else:
        base_path = posixpath.normpath(
            posixpath.join(
                source_directory,
                value,
            )
        )

    # ------------------------------------------------------------
    # Exact path first
    # ------------------------------------------------------------

    candidate = candidate_for_path(
        base_path,
        index,
    )

    if candidate is not None:
        return candidate

    # ------------------------------------------------------------
    # Extension fallbacks
    # ------------------------------------------------------------

    possible_extensions = (
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".py",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".html",
        ".json",
    )

    for extension in possible_extensions:
        candidate = candidate_for_path(
            f"{base_path}{extension}",
            index,
        )

        if candidate is not None:
            return candidate

    # ------------------------------------------------------------
    # Directory index fallbacks
    # ------------------------------------------------------------

    index_names = (
        "index.js",
        "index.jsx",
        "index.ts",
        "index.tsx",
        "index.mjs",
        "index.cjs",
        "index.py",
    )

    for index_name in index_names:
        candidate = candidate_for_path(
            f"{base_path}/{index_name}",
            index,
        )

        if candidate is not None:
            return candidate

    # ------------------------------------------------------------
    # Public-root fallback
    # ------------------------------------------------------------

    public_base = posixpath.normpath(
        posixpath.join(
            "public",
            value.lstrip("/"),
        )
    )

    candidate = candidate_for_path(
        public_base,
        index,
    )

    if candidate is not None:
        return candidate

    for extension in (
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".html",
        ".json",
    ):
        candidate = candidate_for_path(
            f"{public_base}{extension}",
            index,
        )

        if candidate is not None:
            return candidate

    return None

# ============================================================
# Python Dependencies
# ============================================================

def python_references(
    blob: SourceBlob,
) -> set[str]:

    """
    Extract local-looking Python module references.
    """

    references: set[str] = set()

    for match in PYTHON_IMPORT_PATTERN.finditer(
        blob.content
    ):

        module = (
            match.group(1)
            or match.group(2)
            or ""
        ).strip()

        if not module:

            continue

        references.add(
            module
        )

    return references


def resolve_python_reference(
    source_path: str,
    module: str,
    index: dict[str, PromptFile],
) -> PromptFile | None:
    """
    Resolve a Python module reference to a repository file.

    Supports both absolute project imports and relative imports.
    """

    module = module.strip()

    if not module:
        return None

    source_directory = posixpath.dirname(
        normalized_path(source_path)
    )

    # ------------------------------------------------------------
    # Relative Python import
    # ------------------------------------------------------------

    if module.startswith("."):
        leading_dots = len(module) - len(module.lstrip("."))

        remainder = module.lstrip(".")

        relative_directory = source_directory

        for _ in range(
            max(0, leading_dots - 1)
        ):
            relative_directory = posixpath.dirname(
                relative_directory
            )

        module_path = remainder.replace(
            ".",
            "/",
        )

        if module_path:
            resolved = posixpath.normpath(
                posixpath.join(
                    relative_directory,
                    module_path,
                )
            )
        else:
            resolved = relative_directory

    else:
        module_path = module.replace(
            ".",
            "/",
        )

        resolved = module_path

    # ------------------------------------------------------------
    # Candidate paths
    # ------------------------------------------------------------

    possible_paths = (
        f"{resolved}.py",
        f"{resolved}/__init__.py",
    )

    for candidate_path in possible_paths:
        candidate = candidate_for_path(
            candidate_path,
            index,
        )

        if candidate is not None:
            return candidate

    # ------------------------------------------------------------
    # Backend-root fallback
    # ------------------------------------------------------------

    if not resolved.startswith("backend/"):
        backend_resolved = posixpath.join(
            "backend",
            resolved,
        )

        for candidate_path in (
            f"{backend_resolved}.py",
            f"{backend_resolved}/__init__.py",
        ):
            candidate = candidate_for_path(
                candidate_path,
                index,
            )

            if candidate is not None:
                return candidate

    # ------------------------------------------------------------
    # Source-relative fallback
    # ------------------------------------------------------------

    if not module.startswith("."):
        relative_resolved = posixpath.normpath(
            posixpath.join(
                source_directory,
                resolved,
            )
        )

        for candidate_path in (
            f"{relative_resolved}.py",
            f"{relative_resolved}/__init__.py",
        ):
            candidate = candidate_for_path(
                candidate_path,
                index,
            )

            if candidate is not None:
                return candidate

    return None


# ============================================================
# JavaScript / TypeScript Dependencies
# ============================================================

def javascript_references(
    blob: SourceBlob,
) -> set[str]:

    """
    Extract local JavaScript/TypeScript import references.
    """

    references: set[str] = set()

    for match in JAVASCRIPT_IMPORT_PATTERN.finditer(
        blob.content
    ):

        reference = (
            match.group(1)
            or match.group(2)
            or match.group(3)
            or match.group(4)
            or ""
        ).strip()

        if reference.startswith(
            "."
        ) or reference.startswith(
            "/"
        ):

            references.add(
                reference
            )

    return references


# ============================================================
# HTML Dependencies
# ============================================================

def html_references(
    blob: SourceBlob,
) -> set[str]:

    """
    Extract local script, stylesheet, manifest, worker, and
    asset references from HTML/CSS source.
    """

    references: set[str] = set()

    for match in HTML_REFERENCE_PATTERN.finditer(
        blob.content
    ):

        reference = (
            match.group(1)
            or match.group(2)
            or ""
        ).strip()

        if reference:

            references.add(
                reference
            )

    return references


# ============================================================
# Dependency Discovery
# ============================================================

def referenced_candidates(
    candidate: PromptFile,
    index: dict[str, PromptFile],
) -> set[PromptFile]:

    """
    Resolve deterministic local dependencies for one candidate.
    """

    blob = candidate.blob

    references: set[PromptFile] = set()

    if blob.language == "Python":

        for module in python_references(
            blob
        ):

            dependency = resolve_python_reference(
                blob.path,
                module,
                index,
            )

            if dependency is not None:

                references.add(
                    dependency
                )

    elif blob.language in {
        "JavaScript",
        "TypeScript",
    }:

        for reference in javascript_references(
            blob
        ):

            dependency = resolve_relative_path(
                blob.path,
                reference,
                index,
            )

            if dependency is not None:

                references.add(
                    dependency
                )

    elif blob.language == "HTML":

        for reference in html_references(
            blob
        ):

            dependency = resolve_relative_path(
                blob.path,
                reference,
                index,
            )

            if dependency is not None:

                references.add(
                    dependency
                )

    elif blob.language in STYLING_LANGUAGES:

        for reference in html_references(
            blob
        ):

            dependency = resolve_relative_path(
                blob.path,
                reference,
                index,
            )

            if dependency is not None:

                references.add(
                    dependency
                )

    return references


def build_dependency_graph(
    candidates: list[PromptFile],
) -> dict[PromptFile, set[PromptFile]]:

    """
    Build a deterministic local dependency graph.

    Only references that resolve to files actually present in the
    Codebase are retained.
    """

    index = build_candidate_index(
        candidates
    )

    graph: dict[
        PromptFile,
        set[PromptFile],
    ] = {}

    for candidate in candidates:

        graph[candidate] = referenced_candidates(
            candidate,
            index,
        )

    return graph


# ============================================================
# Root Detection
# ============================================================

def root_priority(
    candidate: PromptFile,
) -> int | None:

    """
    Determine whether a file should act as a reconstruction root.

    Only genuine application entry points and configuration files
    are roots. Ordinary source files become important because they
    are dependencies of those roots.
    """

    blob = candidate.blob

    name = basename(
        blob.path
    )

    path = normalized_path(
        blob.path
    )

    # --------------------------------------------------------
    # Dependency manifests and build configuration
    # --------------------------------------------------------

    if is_configuration_file(
        blob
    ):
        return 0

    # --------------------------------------------------------
    # HTML application entry point
    # --------------------------------------------------------

    if (
        name == "index.html"
    ):
        return 1

    # --------------------------------------------------------
    # Backend runtime entry points
    # --------------------------------------------------------

    if (
        name in {
            "main.py",
            "app.py",
            "server.py",
        }
        and (
            path.startswith(
                "backend/"
            )
            or path.startswith(
                "server/"
            )
            or path.startswith(
                "api/"
            )
        )
    ):
        return 2

    # --------------------------------------------------------
    # Frontend runtime entry points
    # --------------------------------------------------------

    if (
        name in {
            "main.ts",
            "main.tsx",
            "main.js",
            "main.jsx",
        }
        and (
            path.startswith(
                "src/"
            )
            or "/src/" in path
            or path.startswith(
                "frontend/"
            )
        )
    ):
        return 2

    # --------------------------------------------------------
    # No automatic root status for generic source files.
    # --------------------------------------------------------

    return None


# ============================================================
# Dependency Depth
# ============================================================

def dependency_depths(
    candidates: list[PromptFile],
    graph: dict[PromptFile, set[PromptFile]],
) -> dict[PromptFile, tuple[int, int]]:

    """
    Calculate the shortest dependency depth from each
    reconstruction root.

    Returns:

        candidate -> (root_priority, dependency_depth)
    """

    depths: dict[
        PromptFile,
        tuple[int, int],
    ] = {}

    roots = sorted(
        (
            (
                root_priority(candidate),
                candidate,
            )
            for candidate in candidates
            if root_priority(candidate) is not None
        ),
        key=lambda item: (
            item[0],
            normalized_path(
                item[1].blob.path
            ),
        ),
    )

    for priority, root in roots:

        queue: deque[
            tuple[PromptFile, int]
        ] = deque(
            [
                (
                    root,
                    0,
                )
            ]
        )

        visited: set[PromptFile] = set()

        while queue:

            current, depth = queue.popleft()

            if current in visited:

                continue

            visited.add(
                current
            )

            existing = depths.get(
                current
            )

            if (
                existing is None
                or (
                    priority,
                    depth,
                ) < existing
            ):

                depths[current] = (
                    priority,
                    depth,
                )

            dependencies = sorted(
                graph.get(
                    current,
                    set(),
                ),
                key=lambda item: normalized_path(
                    item.blob.path
                ),
            )

            for dependency in dependencies:

                if dependency not in visited:

                    queue.append(
                        (
                            dependency,
                            depth + 1,
                        )
                    )

    return depths


# ============================================================
# Dependency-Aware Priority
# ============================================================

def dependency_priority(
    candidate: PromptFile,
    depths: dict[PromptFile, tuple[int, int]],
) -> tuple[int, int, int, int, str]:

    """
    Rank files according to their relationship with genuine
    reconstruction roots.

    Dependency depth dominates ordinary file classification.

    This means:

        root
          ↓
        direct dependency
          ↓
        transitive dependency

    will always be considered before unrelated source files.
    """

    dependency = depths.get(
        candidate
    )

    if dependency is not None:

        root, depth = dependency

        return (
            0,
            root,
            depth,
            candidate.estimated_tokens,
            normalized_path(
                candidate.blob.path
            ),
        )

    return (
        1,
        candidate.priority,
        999,
        candidate.estimated_tokens,
        normalized_path(
            candidate.blob.path
        ),
    )

def dependency_closure(
    candidates: list[PromptFile],
    graph: dict[PromptFile, set[PromptFile]],
) -> list[PromptFile]:

    """
    Return candidates reachable from genuine reconstruction roots.

    Files are ordered by:

        1. root priority
        2. dependency depth
        3. file size
        4. path

    Smaller dependencies are preferred when multiple files occupy
    the same dependency depth, allowing more of the application's
    actual dependency graph to fit inside the source budget.
    """

    depths = dependency_depths(
        candidates,
        graph,
    )

    reachable = [
        candidate
        for candidate in candidates
        if candidate in depths
    ]

    reachable.sort(
        key=lambda candidate: (
            depths[candidate][0],
            depths[candidate][1],
            candidate.estimated_tokens,
            normalized_path(
                candidate.blob.path
            ),
        )
    )

    return reachable

# ============================================================
# Source Selection
# ============================================================

def select_files(
    candidates: list[PromptFile],
) -> tuple[
    list[PromptFile],
    list[PromptFile],
]:

    """
    Select source files using dependency-aware reconstruction.

    Selection strategy:

        1. Remove non-functional metadata.
        2. Build the dependency graph.
        3. Establish the dependency closure of true roots.
        4. Include reachable files before unrelated files.
        5. Prefer smaller files at the same dependency depth.
        6. Use remaining budget for useful unrelated source.
        7. Never partially include a source file.
    """

    graph = build_dependency_graph(
        candidates
    )

    reachable = dependency_closure(
        candidates,
        graph,
    )

    reachable_paths = {
        candidate.blob.path
        for candidate in reachable
    }

    unrelated = [
        candidate
        for candidate in candidates
        if (
            candidate.blob.path
            not in reachable_paths
        )
        and not is_non_functional_file(
            candidate.blob
        )
    ]

    unrelated.sort(
        key=lambda candidate: (
            candidate.priority,
            candidate.estimated_tokens,
            normalized_path(
                candidate.blob.path
            ),
        )
    )

    selected: list[PromptFile] = []

    selected_paths: set[str] = set()

    used_tokens = 0

    # --------------------------------------------------------
    # Phase 1
    # Application dependency closure
    # --------------------------------------------------------

    for candidate in reachable:

        if len(selected) >= MAX_CRITICAL_FILES:

            break

        if (
            used_tokens
            + candidate.estimated_tokens
            <= MAX_SOURCE_TOKENS
        ):

            selected.append(
                candidate
            )

            selected_paths.add(
                candidate.blob.path
            )

            used_tokens += candidate.estimated_tokens

    # --------------------------------------------------------
    # Phase 2
    # Useful unrelated source
    # --------------------------------------------------------

    for candidate in unrelated:

        if len(selected) >= MAX_CRITICAL_FILES:

            break

        if candidate.blob.path in selected_paths:

            continue

        if (
            used_tokens
            + candidate.estimated_tokens
            <= MAX_SOURCE_TOKENS
        ):

            selected.append(
                candidate
            )

            selected_paths.add(
                candidate.blob.path
            )

            used_tokens += candidate.estimated_tokens

    # --------------------------------------------------------
    # Excluded files
    # --------------------------------------------------------

    excluded = [
        candidate
        for candidate in candidates
        if candidate.blob.path
        not in selected_paths
    ]

    selected.sort(
        key=lambda candidate: (
            0
            if candidate.blob.path
            in reachable_paths
            else 1,
            normalized_path(
                candidate.blob.path
            ),
        )
    )

    excluded.sort(
        key=lambda candidate: (
            candidate.priority,
            candidate.estimated_tokens,
            normalized_path(
                candidate.blob.path
            ),
        )
    )

    return (
        selected,
        excluded,
    )


# ============================================================
# Source Formatting
# ============================================================

def language_fence(
    language: str,
) -> str:

    """
    Map an internal language name to a Markdown code fence.
    """

    mapping = {
        "Python": "python",
        "JavaScript": "javascript",
        "TypeScript": "typescript",
        "Java": "java",
        "Kotlin": "kotlin",
        "C": "c",
        "C++": "cpp",
        "C#": "csharp",
        "Go": "go",
        "Rust": "rust",
        "PHP": "php",
        "Ruby": "ruby",
        "Swift": "swift",
        "Dart": "dart",
        "HTML": "html",
        "CSS": "css",
        "SCSS": "scss",
        "Sass": "sass",
        "Less": "less",
        "JSON": "json",
        "YAML": "yaml",
        "TOML": "toml",
        "XML": "xml",
        "SQL": "sql",
        "GraphQL": "graphql",
        "Shell": "shell",
        "Dockerfile": "dockerfile",
        "Markdown": "markdown",
    }

    return mapping.get(
        language,
        "",
    )


def format_source_file(
    blob: SourceBlob,
) -> str:

    """
    Format one complete source file verbatim.
    """

    return (
        f"FILE: {blob.path}\n"
        f"LANGUAGE: {blob.language}\n"
        f"SIZE: {blob.size} bytes\n"
        f"SHA: {blob.sha}\n"
        "\n"
        f"```{language_fence(blob.language)}\n"
        f"{blob.content}\n"
        "```\n"
    )


# ============================================================
# Prompt Header
# ============================================================

def build_header(
    codebase: Codebase,
    selected: list[PromptFile],
    excluded: list[PromptFile],
) -> str:

    """
    Build the reconstruction instruction section.
    """

    return f"""
You are an expert software engineer and autonomous application
reconstruction agent.

Your task is to recreate the application represented by the
source files supplied below.

Repository:
{codebase.repository}

Branch:
{codebase.branch}

RECONSTRUCTION OBJECTIVE
========================

Recreate the original application as faithfully as the supplied
source permits.

The supplied files are authoritative source material for this
reconstruction.

Some eligible repository files may be omitted because of the
prompt budget. An omitted file is not evidence that the original
application did not contain it.

RECONSTRUCTION RULES
====================

1. Preserve existing functionality, behavior, architecture,
   styling, dependencies, routing, state management, API
   contracts, and runtime configuration whenever the supplied
   source establishes them.

2. Treat dependency manifests and runtime configuration as
   authoritative when determining the original environment.

3. Trace relationships between files through imports, exports,
   HTML script and stylesheet references, routes, configuration,
   component usage, API calls, and data flow.

4. Preserve the existing visual structure and interaction model
   when frontend source is provided.

5. Preserve backend behavior and API contracts when backend source
   is provided.

6. Do not replace an existing framework, dependency, or runtime
   architecture unless the supplied source requires it.

7. Do not redesign the application merely because another design
   would be preferable.

8. Do not invent unrelated functionality.

9. Do not fabricate omitted source and present it as original
   source.

10. If a referenced file is omitted, infer only the minimum
    behavior necessary to make the reconstructed application
    coherent.

11. Preserve the repository structure implied by the supplied
    file paths.

12. The objective is reconstruction, not modernization.

SOURCE COVERAGE
===============

Regenesis selected {len(selected)} source files using a
deterministic dependency-aware reconstruction system.

{len(excluded)} eligible repository files were not included because
they were lower priority, non-functional metadata, or could not
fit inside the source budget.

Included source files are provided verbatim below.

Use the exact repository-relative file paths when recreating the
project structure.

""".strip()


# ============================================================
# Prompt Footer
# ============================================================

def build_footer() -> str:

    """
    Build the final reconstruction instructions.
    """

    return """
END OF SOURCE FILES
===================

RECONSTRUCTION CHECKLIST
========================

Before finishing:

1. Recreate the repository structure implied by the supplied
   paths.

2. Install and preserve the dependencies established by the
   supplied configuration.

3. Reconnect imports, routes, services, assets, scripts, workers,
   and data flow wherever the supplied source establishes those
   relationships.

4. Preserve the original UI structure, styling, interactions,
   and runtime behavior when supported by the source.

5. Preserve backend endpoints and request/response behavior when
   supported by the source.

6. Do not silently substitute a different framework or
   architecture.

7. Do not add unrelated features.

8. If a referenced source file is omitted, implement only the
   minimum compatible behavior that can be inferred from the
   supplied source.

9. Validate that the reconstructed application builds and runs.

The goal is a working reconstruction of the supplied application,
not a redesign or modernization.
""".strip()


# ============================================================
# Prompt Construction
# ============================================================

def build_prompt_result(
    codebase: Codebase,
) -> PromptBuildResult:

    """
    Build the complete deterministic reconstruction prompt.
    """

    candidates = prepare_files(
        codebase
    )

    selected, excluded = select_files(
        candidates
    )

    header = build_header(
        codebase,
        selected,
        excluded,
    )

    footer = build_footer()

    source_sections = [
        format_source_file(
            candidate.blob
        )
        for candidate in selected
    ]

    prompt = (
        header
        + "\n\n"
        + "\n\n".join(
            source_sections
        )
        + "\n\n"
        + footer
    )

    estimated_tokens = estimate_tokens(
        prompt
    )

    if estimated_tokens > MAX_PROMPT_TOKENS:

        raise RuntimeError(
            "Generated reconstruction prompt exceeds the "
            f"{MAX_PROMPT_TOKENS:,}-token budget. "
            f"Estimated: {estimated_tokens:,} tokens."
        )

    return PromptBuildResult(
        prompt=prompt,
        included_files=tuple(
            candidate.blob.path
            for candidate in selected
        ),
        excluded_files=tuple(
            candidate.blob.path
            for candidate in excluded
        ),
        estimated_tokens=estimated_tokens,
    )


# ============================================================
# Public API
# ============================================================

def build_prompt(
    codebase: Codebase,
) -> str:

    """
    Build and return the reconstruction prompt.
    """

    return build_prompt_result(
        codebase
    ).prompt


__all__ = [
    "MAX_PROMPT_TOKENS",
    "MAX_SOURCE_TOKENS",
    "PromptFile",
    "PromptBuildResult",
    "estimate_tokens",
    "file_priority",
    "prepare_files",
    "format_source_file",
    "build_prompt_result",
    "build_prompt",
]