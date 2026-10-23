# Deku Recipes

Deku Recipes will contain reviewed, versioned package recipe metadata, source pins, patch references, and package-specific review notes.

## Status

**Bootstrap stage.** There is no supported package catalog yet. The initial format is metadata-only and does not download source code, execute build instructions, create packages, or publish binaries.

## Recipe requirements

- Stable package identifier and version.
- Immutable source revision and expected SHA-256 digest.
- Explicit license identifier and source URL.
- Supported architecture declarations and dependency names.
- Review record for patches, build changes, security updates, and deprecation.
- No credentials, private source URLs, generated binaries, or unreviewed archives.

## Prototype

- `schema/recipe-v1.schema.json` — JSON Schema for recipe metadata.
- `examples/hello.json` — illustrative recipe descriptor.
- `deku_recipes/validate.py` — standard-library validator.
- `tests/` — malformed and valid fixture coverage.

A valid recipe describes inputs; it is not proof that its source is safe, its license has been legally approved, or its package builds successfully.
