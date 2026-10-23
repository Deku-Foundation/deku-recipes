"""Validate recipe metadata without downloading or executing package sources."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

NAME = re.compile(r"^[a-z0-9][a-z0-9+._-]{0,127}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
LICENSE = re.compile(r"^[A-Za-z0-9.+() -]{1,128}$")
ARCHITECTURES = {"x86_64", "aarch64"}
REQUIRED = {"schema_version", "name", "version", "summary", "license", "source", "architectures", "dependencies"}
OPTIONAL = {"homepage", "notes"}


class RecipeValidationError(ValueError):
    """Raised when recipe metadata is invalid."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RecipeValidationError(message)


def _https_url(value: Any, label: str) -> None:
    require(isinstance(value, str), f"{label} must be a string")
    parsed = urlparse(value)
    require(parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password,
            f"{label} must be HTTPS and must not contain embedded credentials")


def validate_recipe(recipe: Any) -> dict[str, Any]:
    """Validate a metadata-only recipe descriptor."""
    require(isinstance(recipe, dict), "recipe must be an object")
    keys = set(recipe)
    require(REQUIRED <= keys and keys <= REQUIRED | OPTIONAL, "recipe has missing or unsupported fields")
    require(type(recipe["schema_version"]) is int and recipe["schema_version"] == 1, "unsupported schema_version")
    require(isinstance(recipe["name"], str) and NAME.fullmatch(recipe["name"]) is not None, "invalid package name")
    require(isinstance(recipe["version"], str) and 1 <= len(recipe["version"]) <= 128, "invalid package version")
    require(isinstance(recipe["summary"], str) and 1 <= len(recipe["summary"].strip()) <= 300, "invalid package summary")
    require(isinstance(recipe["license"], str) and LICENSE.fullmatch(recipe["license"]) is not None, "invalid license expression syntax")

    source = recipe["source"]
    require(isinstance(source, dict) and set(source) == {"url", "revision", "sha256"},
            "source must contain url, revision, and sha256 only")
    _https_url(source["url"], "source.url")
    require(isinstance(source["revision"], str) and REVISION.fullmatch(source["revision"]) is not None,
            "source.revision must be a full lowercase 40-character commit hash")
    require(isinstance(source["sha256"], str) and SHA256.fullmatch(source["sha256"]) is not None,
            "source.sha256 must be a 64-character lowercase SHA-256 digest")

    architectures = recipe["architectures"]
    require(isinstance(architectures, list) and architectures, "architectures must be a non-empty array")
    require(all(isinstance(a, str) and a in ARCHITECTURES for a in architectures), "unsupported architecture")
    require(len(set(architectures)) == len(architectures), "architectures must not contain duplicates")

    dependencies = recipe["dependencies"]
    require(isinstance(dependencies, list), "dependencies must be an array")
    require(all(isinstance(d, str) and NAME.fullmatch(d) is not None for d in dependencies),
            "dependency names must use the package identifier format")
    require(len(set(dependencies)) == len(dependencies), "dependencies must not contain duplicates")
    require(recipe["name"] not in dependencies, "package must not depend on itself")

    if "homepage" in recipe:
        _https_url(recipe["homepage"], "homepage")
    if "notes" in recipe:
        require(isinstance(recipe["notes"], str) and len(recipe["notes"]) <= 4000, "notes must be a string of at most 4000 characters")
    return recipe


def load_and_validate(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            recipe = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise RecipeValidationError(f"cannot read valid JSON recipe: {exc}") from exc
    return validate_recipe(recipe)
