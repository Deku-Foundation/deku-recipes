"""Strict, non-executing validation for declarative recipe schema v2."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_RECIPE_BYTES = 1_048_576
MAX_PATCHES = 128
MAX_DEPENDENCIES_PER_CLASS = 256
MAX_BUILD_STEPS = 128
MAX_ARGS_PER_STEP = 64
MAX_STEP_BYTES = 16_384

NAME = re.compile(r"^[a-z0-9][a-z0-9+._-]{0,127}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+:~_-]{0,127}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
PATCH_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
OUTPUT_PATH = PATCH_PATH
OCI_DIGEST_IMAGE = re.compile(r"^[a-z0-9][A-Za-z0-9._/:@-]{0,254}@sha256:[0-9a-f]{64}$")
CONSTRAINT = re.compile(r"^(?:\*|(?:>=|<=|=|>|<|\^|~)?[A-Za-z0-9][A-Za-z0-9.+:~_-]{0,127})$")
ARCHITECTURES = {"x86_64", "aarch64"}
DEPENDENCY_CLASSES = {"build", "runtime", "optional"}
STEP_KEYS = {"name", "argv", "cwd", "timeout_seconds"}


class RecipeV2Error(ValueError):
    """Raised when a v2 recipe violates its declarative contract."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RecipeV2Error(message)


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecipeV2Error(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _https_source_url(value: Any) -> None:
    require(isinstance(value, str) and 0 < len(value) <= 2048, "source.url must be a string of at most 2048 characters")
    require(not any(char.isspace() or ord(char) < 0x21 or ord(char) == 0x7F for char in value), "source.url contains whitespace/control characters")
    require("\\" not in value and "?" not in value and "#" not in value, "source.url must not contain backslashes, query or fragment")
    try:
        parsed = urlparse(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise RecipeV2Error("source.url must be a well-formed HTTPS URL") from exc
    require(parsed.scheme == "https" and bool(host), "source.url must be an absolute HTTPS URL")
    require(not parsed.username and not parsed.password, "source.url must not contain embedded credentials")
    require(not parsed.netloc.endswith(":"), "source.url must not contain an empty port")
    require(port is None or 1 <= port <= 65535, "source.url port is out of range")
    require(not parsed.query and not parsed.fragment, "source.url must not contain query or fragment")


def _license_tokens(expression: Any) -> list[str]:
    require(isinstance(expression, str) and 1 <= len(expression) <= 256, "license must be a non-empty SPDX expression candidate")
    tokens: list[str] = []
    position = 0
    pattern = re.compile(r"\s*(\(|\)|AND\b|OR\b|WITH\b|[A-Za-z0-9][A-Za-z0-9.+:-]*)")
    while position < len(expression):
        match = pattern.match(expression, position)
        require(match is not None, "license expression contains invalid syntax")
        tokens.append(match.group(1))
        position = match.end()
    require(tokens, "license expression is empty")
    return tokens


def validate_spdx_expression(expression: Any) -> None:
    """Validate SPDX expression grammar; this does not verify IDs against the SPDX registry."""
    tokens = _license_tokens(expression)
    index = 0

    def peek() -> str | None:
        return tokens[index] if index < len(tokens) else None

    def take() -> str:
        nonlocal index
        token = peek()
        require(token is not None, "license expression ends unexpectedly")
        index += 1
        return token  # type: ignore[return-value]

    def identifier(token: str | None) -> bool:
        return token is not None and token not in {"(", ")", "AND", "OR", "WITH"}

    def parse_primary() -> bool:
        token = take()
        if token == "(":
            parse_or()
            require(take() == ")", "license expression has an unmatched parenthesis")
            return False
        require(identifier(token), f"expected a license identifier, got {token!r}")
        return True

    def parse_with() -> bool:
        is_simple = parse_primary()
        if peek() == "WITH":
            take()
            require(is_simple, "WITH must follow a single license identifier")
            exception = take()
            require(identifier(exception), "WITH must be followed by an exception identifier")
            return False
        return is_simple

    def parse_and() -> bool:
        simple = parse_with()
        while peek() == "AND":
            take()
            parse_with()
            simple = False
        return simple

    def parse_or() -> bool:
        simple = parse_and()
        while peek() == "OR":
            take()
            parse_and()
            simple = False
        return simple

    parse_or()
    require(index == len(tokens), "license expression has trailing or misplaced operators")


def _safe_relative_path(value: Any, label: str, *, max_len: int = 200) -> str:
    pattern = re.compile(rf"^[A-Za-z0-9][A-Za-z0-9._/-]{{0,{max_len - 1}}}$")
    require(isinstance(value, str) and pattern.fullmatch(value) is not None, f"{label} has invalid path syntax")
    segments = value.split("/")
    require(all(segment not in {"", ".", ".."} and segment.lower() != ".git" for segment in segments), f"{label} contains an unsafe path segment")
    return value


def _validate_step(step: Any, label: str, names: set[str]) -> None:
    require(isinstance(step, dict) and set(step) == STEP_KEYS, f"{label} must contain name, argv, cwd and timeout_seconds only")
    name = step["name"]
    require(isinstance(name, str) and TOKEN.fullmatch(name) is not None, f"{label}.name is invalid")
    require(name not in names, f"duplicate step name: {name}")
    names.add(name)

    argv = step["argv"]
    require(isinstance(argv, list) and 0 < len(argv) <= MAX_ARGS_PER_STEP, f"{label}.argv must contain 1 to {MAX_ARGS_PER_STEP} arguments")
    total = 0
    for index, argument in enumerate(argv):
        require(isinstance(argument, str) and argument and "\x00" not in argument, f"{label}.argv[{index}] must be a non-empty string without NUL")
        require(not any(ord(char) < 32 or ord(char) == 127 for char in argument), f"{label}.argv[{index}] contains control characters")
        total += len(argument.encode("utf-8"))
    require(total <= MAX_STEP_BYTES, f"{label}.argv exceeds the combined argument-size limit")

    cwd = step["cwd"]
    require(isinstance(cwd, str), f"{label}.cwd must be a relative path")
    if cwd != ".":
        _safe_relative_path(cwd, f"{label}.cwd")
    timeout = step["timeout_seconds"]
    require(type(timeout) is int and 1 <= timeout <= 3600, f"{label}.timeout_seconds must be an integer from 1 to 3600")


def _validate_pinned_oci_image(value: Any) -> None:
    require(isinstance(value, str) and OCI_DIGEST_IMAGE.fullmatch(value) is not None, "build.environment_image must be pinned by an immutable OCI sha256 digest")
    name = value.split("@sha256:", 1)[0]
    parts = name.split("/")
    require(all(parts), "build.environment_image has an empty path component")
    segment_pattern = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]{1,5})?$")
    require(all(part not in {".", ".."} and segment_pattern.fullmatch(part) is not None for part in parts), "build.environment_image contains an invalid registry/repository component")


def validate_recipe_v2(recipe: Any) -> dict[str, Any]:
    """Validate metadata only; never fetch sources, execute argv or build a package."""
    required = {"schema_version", "name", "version", "summary", "license", "source", "targets", "dependencies", "patches", "build", "outputs", "tests"}
    require(isinstance(recipe, dict) and set(recipe) == required, "recipe v2 must contain exactly the documented fields")
    require(type(recipe["schema_version"]) is int and recipe["schema_version"] == 2, "unsupported schema_version")
    require(isinstance(recipe["name"], str) and NAME.fullmatch(recipe["name"]) is not None, "invalid package name")
    require(isinstance(recipe["version"], str) and VERSION.fullmatch(recipe["version"]) is not None, "invalid package version")
    require(isinstance(recipe["summary"], str) and 1 <= len(recipe["summary"]) <= 300 and recipe["summary"] == recipe["summary"].strip(), "summary must be a trimmed string of 1 to 300 characters")
    validate_spdx_expression(recipe["license"])

    source = recipe["source"]
    require(isinstance(source, dict) and set(source) == {"type", "url", "revision", "sha256"}, "source must contain type, url, revision and sha256 only")
    require(source["type"] == "git", "schema v2 currently supports immutable git sources only")
    _https_source_url(source["url"])
    require(isinstance(source["revision"], str) and REVISION.fullmatch(source["revision"]) is not None, "source.revision must be a full lowercase 40-character commit hash")
    require(isinstance(source["sha256"], str) and SHA256.fullmatch(source["sha256"]) is not None, "source.sha256 must be a lowercase SHA-256 digest")

    targets = recipe["targets"]
    require(isinstance(targets, list) and 0 < len(targets) <= len(ARCHITECTURES), "targets must be a non-empty bounded array")
    seen_targets: set[tuple[str, str]] = set()
    for target in targets:
        require(isinstance(target, dict) and set(target) == {"architecture", "abi"}, "each target must contain architecture and abi only")
        require(isinstance(target["architecture"], str) and target["architecture"] in ARCHITECTURES, "unsupported target architecture")
        require(isinstance(target["abi"], str) and TOKEN.fullmatch(target["abi"]) is not None, "target.abi must be an explicit token")
        key = (target["architecture"], target["abi"])
        require(key not in seen_targets, "duplicate target architecture/ABI")
        seen_targets.add(key)

    dependencies = recipe["dependencies"]
    require(isinstance(dependencies, dict) and set(dependencies) == DEPENDENCY_CLASSES, "dependencies must define build, runtime and optional arrays")
    for category in DEPENDENCY_CLASSES:
        items = dependencies[category]
        require(isinstance(items, list) and len(items) <= MAX_DEPENDENCIES_PER_CLASS, f"dependencies.{category} must be a bounded array")
        names: set[str] = set()
        for item in items:
            require(isinstance(item, dict) and set(item) == {"name", "constraint"}, f"dependencies.{category} entries must contain name and constraint only")
            name = item["name"]
            constraint = item["constraint"]
            require(isinstance(name, str) and NAME.fullmatch(name) is not None, "invalid dependency name")
            require(name != recipe["name"], "package must not depend on itself")
            require(name not in names, f"duplicate {category} dependency: {name}")
            names.add(name)
            require(isinstance(constraint, str) and CONSTRAINT.fullmatch(constraint) is not None, "dependency constraint has invalid syntax")

    patches = recipe["patches"]
    require(isinstance(patches, list) and len(patches) <= MAX_PATCHES, f"patches must contain at most {MAX_PATCHES} entries")
    patch_paths: set[str] = set()
    for patch in patches:
        require(isinstance(patch, dict) and set(patch) == {"path", "sha256"}, "patch entries must contain path and sha256 only")
        path = _safe_relative_path(patch["path"], "patch.path")
        require(path not in patch_paths, "duplicate patch path")
        patch_paths.add(path)
        require(isinstance(patch["sha256"], str) and SHA256.fullmatch(patch["sha256"]) is not None, "patch.sha256 must be a lowercase SHA-256 digest")

    build = recipe["build"]
    require(isinstance(build, dict) and set(build) == {"environment_image", "network", "steps"}, "build must contain environment_image, network and steps only")
    _validate_pinned_oci_image(build["environment_image"])
    require(build["network"] == "disabled", "build network must be disabled")
    steps = build["steps"]
    require(isinstance(steps, list) and 0 < len(steps) <= MAX_BUILD_STEPS, f"build.steps must contain 1 to {MAX_BUILD_STEPS} entries")
    step_names: set[str] = set()
    for index, step in enumerate(steps):
        _validate_step(step, f"build.steps[{index}]", step_names)

    outputs = recipe["outputs"]
    require(isinstance(outputs, list) and 0 < len(outputs) <= 256, "outputs must be a non-empty bounded array")
    output_paths: set[str] = set()
    output_kinds: dict[str, str] = {}
    for output in outputs:
        require(isinstance(output, dict) and set(output) == {"path", "kind"}, "output entries must contain path and kind only")
        path = _safe_relative_path(output["path"], "output.path")
        require(isinstance(output["kind"], str) and output["kind"] in {"package", "file", "directory"}, "unsupported output kind")
        require(path not in output_paths, "duplicate output path")
        output_paths.add(path)
        output_kinds[path] = output["kind"]
    for path in output_paths:
        segments = path.split("/")
        for end in range(1, len(segments)):
            parent = "/".join(segments[:end])
            require(parent not in output_kinds or output_kinds[parent] == "directory", "output file/directory path collision")

    tests = recipe["tests"]
    require(isinstance(tests, list) and 0 < len(tests) <= 64, "tests must contain 1 to 64 test steps")
    test_names: set[str] = set()
    for index, step in enumerate(tests):
        _validate_step(step, f"tests[{index}]", test_names)

    return recipe


def load_and_validate_v2(path: str | Path) -> dict[str, Any]:
    """Load bounded UTF-8 JSON, reject duplicate keys, then validate v2 metadata."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_RECIPE_BYTES + 1)
    except OSError as exc:
        raise RecipeV2Error(f"cannot read recipe: {exc}") from exc
    if len(raw) > MAX_RECIPE_BYTES:
        raise RecipeV2Error(f"recipe exceeds the {MAX_RECIPE_BYTES}-byte input limit")
    try:
        recipe = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object_pairs)
    except RecipeV2Error:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise RecipeV2Error(f"cannot parse valid UTF-8 JSON recipe: {exc}") from exc
    return validate_recipe_v2(recipe)
