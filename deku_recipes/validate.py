"""Validate recipe metadata without downloading or executing package sources."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_RECIPE_BYTES = 1_048_576
MAX_DEPENDENCIES = 256
MAX_URL_LENGTH = 2_048

NAME = re.compile(r"^[a-z0-9][a-z0-9+._-]{0,127}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+:~_-]{0,127}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
LICENSE = re.compile(r"^[A-Za-z0-9.+() -]{1,128}$")
ARCHITECTURES = {"x86_64", "aarch64"}
REQUIRED = {
    "schema_version",
    "name",
    "version",
    "summary",
    "license",
    "source",
    "architectures",
    "dependencies",
}
OPTIONAL = {"homepage", "notes"}


class RecipeValidationError(ValueError):
    """Raised when recipe metadata is invalid."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RecipeValidationError(message)


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON object keys rather than accepting ambiguous metadata."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecipeValidationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _https_url(value: Any, label: str, *, source_url: bool = False) -> None:
    require(isinstance(value, str), f"{label} must be a string")
    require(0 < len(value) <= MAX_URL_LENGTH, f"{label} must be 1 to {MAX_URL_LENGTH} characters")
    require(
        not any(char.isspace() or ord(char) < 0x21 or ord(char) == 0x7F for char in value),
        f"{label} must not contain whitespace or control characters",
    )
    require("\\\\" not in value, f"{label} must not contain backslashes")

    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise RecipeValidationError(f"{label} must be a well-formed HTTPS URL") from exc

    require(
        parsed.scheme == "https" and bool(hostname),
        f"{label} must be an absolute HTTPS URL with a hostname",
    )
    require(
        not parsed.username and not parsed.password,
        f"{label} must not contain embedded credentials",
    )
    authority = parsed.netloc.rsplit("@", 1)[-1]
    require(not authority.endswith(":"), f"{label} must not contain an empty port")
    require(port is None or 1 <= port <= 65_535, f"{label} port must be between 1 and 65535")
    if source_url:
        require(
            "?" not in value and "#" not in value and not parsed.query and not parsed.fragment,
            f"{label} must not contain a query string or fragment",
        )


def validate_recipe(recipe: Any) -> dict[str, Any]:
    """Validate a metadata-only recipe descriptor; do not fetch or execute its inputs."""
    require(isinstance(recipe, dict), "recipe must be an object")
    keys = set(recipe)
    require(REQUIRED <= keys and keys <= REQUIRED | OPTIONAL, "recipe has missing or unsupported fields")
    require(
        type(recipe["schema_version"]) is int and recipe["schema_version"] == 1,
        "unsupported schema_version",
    )
    require(isinstance(recipe["name"], str) and NAME.fullmatch(recipe["name"]) is not None, "invalid package name")
    require(
        isinstance(recipe["version"], str) and VERSION.fullmatch(recipe["version"]) is not None,
        "invalid package version",
    )
    require(
        isinstance(recipe["summary"], str)
        and 1 <= len(recipe["summary"]) <= 300
        and recipe["summary"] == recipe["summary"].strip(),
        "summary must be a trimmed string of 1 to 300 characters",
    )
    require(
        isinstance(recipe["license"], str) and LICENSE.fullmatch(recipe["license"]) is not None,
        "invalid license expression syntax",
    )

    source = recipe["source"]
    require(
        isinstance(source, dict) and set(source) == {"url", "revision", "sha256"},
        "source must contain url, revision, and sha256 only",
    )
    _https_url(source["url"], "source.url", source_url=True)
    require(
        isinstance(source["revision"], str) and REVISION.fullmatch(source["revision"]) is not None,
        "source.revision must be a full lowercase 40-character commit hash",
    )
    require(
        isinstance(source["sha256"], str) and SHA256.fullmatch(source["sha256"]) is not None,
        "source.sha256 must be a 64-character lowercase SHA-256 digest",
    )

    architectures = recipe["architectures"]
    require(
        isinstance(architectures, list) and 0 < len(architectures) <= len(ARCHITECTURES),
        "architectures must be a non-empty array containing at most the supported architecture count",
    )
    require(
        all(isinstance(arch, str) and arch in ARCHITECTURES for arch in architectures),
        "unsupported architecture",
    )
    require(len(set(architectures)) == len(architectures), "architectures must not contain duplicates")

    dependencies = recipe["dependencies"]
    require(
        isinstance(dependencies, list) and len(dependencies) <= MAX_DEPENDENCIES,
        f"dependencies must be an array with at most {MAX_DEPENDENCIES} entries",
    )
    require(
        all(isinstance(dep, str) and NAME.fullmatch(dep) is not None for dep in dependencies),
        "dependency names must use the package identifier format",
    )
    require(len(set(dependencies)) == len(dependencies), "dependencies must not contain duplicates")
    require(recipe["name"] not in dependencies, "package must not depend on itself")

    if "homepage" in recipe:
        _https_url(recipe["homepage"], "homepage")
    if "notes" in recipe:
        require(
            isinstance(recipe["notes"], str) and len(recipe["notes"]) <= 4_000,
            "notes must be a string of at most 4000 characters",
        )
    return recipe


def load_and_validate(path: str | Path) -> dict[str, Any]:
    """Load a bounded UTF-8 JSON recipe and reject duplicate keys before validation."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_RECIPE_BYTES + 1)
    except OSError as exc:
        raise RecipeValidationError(f"cannot read recipe: {exc}") from exc

    if len(raw) > MAX_RECIPE_BYTES:
        raise RecipeValidationError(f"recipe exceeds the {MAX_RECIPE_BYTES}-byte input limit")

    try:
        text = raw.decode("utf-8")
        recipe = json.loads(text, object_pairs_hook=_unique_object_pairs)
    except RecipeValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise RecipeValidationError(f"cannot read valid UTF-8 JSON recipe: {exc}") from exc

    return validate_recipe(recipe)
