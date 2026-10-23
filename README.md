# Deku Recipes

Deku Recipes is the metadata source for reviewed package recipes, immutable source pins, patch references and package-specific review notes.

## Status

**Metadata-validation prototype.** There is no supported package catalog yet. The schema and validator describe recipe inputs only; they do not download source code, execute build instructions, create packages or publish binaries.

## Current recipe contract

A recipe records:

- A stable package identifier and constrained version token.
- An HTTPS source URL, immutable 40-character source revision and expected SHA-256 digest.
- A license expression field and concise package summary.
- Supported architecture declarations and dependency names.
- Optional homepage and bounded review notes.

The validator bounds JSON input to 1 MiB before parsing, rejects duplicate JSON object keys, invalid UTF-8 and excessive nesting, and fails closed on unknown fields. It rejects embedded URL credentials, malformed or empty ports, whitespace/control characters, backslashes, query strings and fragments in source URLs. Dependency and architecture lists are bounded and duplicate entries are rejected.

These checks are syntactic metadata validation. They do not prove that a source is safe, that a license has been legally approved, that a digest is trusted, or that a package builds successfully. HTTPS URL validation alone is not sufficient for a future source fetcher; redirect policy, DNS/IP protections, content verification and network isolation must be implemented separately.

## Prototype files

- schema/recipe-v1.schema.json — JSON Schema for recipe metadata.
- examples/hello.json — illustrative recipe descriptor.
- deku_recipes/validate.py — standard-library validator.
- tests/ — valid and adversarial fixture coverage.

## Run checks

With Python 3.12 or newer:

```sh
python -m unittest discover -s tests -v
PYTHONPATH=. python -m deku_recipes.validate_cli examples/hello.json
```

A successful validation means only that the descriptor conforms to the current metadata contract. It is not a build, license approval or release authorization.

## Next milestones

1. Define maintainership and review records for individual recipes.
2. Connect recipes to a source-fetcher that pins and verifies immutable inputs.
3. Execute builds only through a disposable, unprivileged worker.
4. Capture build inputs, logs, artifact manifests and provenance.
5. Add CI for package builds and upstream update monitoring after the build contract stabilizes.
