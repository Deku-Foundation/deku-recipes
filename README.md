# Deku Recipes

Deku Recipes is the reviewable source-package registry contract for Deku Linux. It describes inputs and intended outputs; it does not fetch code or execute a build.

## Status

**Metadata-validation prototypes.** Schema v1 remains supported for the original examples. Schema v2 is the recommended direction for new recipes because it requires explicit target ABI, dependency classes, patch digests, pinned build environment, network-disabled build intent, argument-vector steps, declared outputs and test commands. Neither schema proves that source is safe, that licensing is approved, or that a package actually builds.

## Schema v1 and v2

- [Recipe v1 schema](schema/recipe-v1.schema.json): source pin, digest, architecture list and flat dependency names.
- [Recipe v2 schema](schema/recipe-v2.schema.json): source revision and archive digest, explicit target ABI, SPDX-expression grammar check, build/runtime/optional dependencies with constraints, patch hashes, digest-pinned OCI build environment, no-network build intent, bounded argv steps, declared output paths and tests.
- [V1 example](examples/hello.json) and [v2 example](examples/hello-v2.json). All example URLs/digests and the environment image digest are fixtures only; they are not published or buildable inputs.
- [V1 validator](deku_recipes/validate.py) and [v2 validator](deku_recipes/v2.py).

## Security properties and limits

The validators bound JSON to 1 MiB before parsing, reject duplicate JSON object keys, invalid UTF-8, unknown fields, mutable Git revisions, malformed SHA-256 digests, embedded URL credentials, source query/fragment, unsafe paths, duplicate dependency/patch/step/output entries, invalid ABI tokens and build environments that are not digest-pinned. V2 uses argv arrays instead of a single shell command string, and accepts only a declared disabled network mode.

These are schema checks only. They do not validate redirect/DNS safety during fetching, prove SPDX identifiers exist in the official registry, approve a license legally, enforce the worker sandbox, validate package archive contents, publish artifacts or authenticate a publisher. The actual build executor must re-validate every input and enforce isolation independently.

## Run checks

With Python 3.12 or newer:

```sh
python -m unittest discover -s tests -v
PYTHONPATH=. python -m deku_recipes.validate_cli examples/hello.json
PYTHONPATH=. python -m deku_recipes.validate_v2_cli examples/hello-v2.json
```

A passing validator means that the descriptor matches the current metadata contract. It is not a package build, license approval or release authorization.

## Next engineering gates

1. Adopt v2 only after versioned schema compatibility and dependency constraint semantics are reviewed.
2. Connect recipe validation to a separate fetch stage with pinned source digests and strict redirect/IP/size controls.
3. Execute recipes only in disposable build workers; no secrets and no network during compilation by default.
4. Validate produced archives and bind package artifacts to input manifests and build provenance.
5. Add independent rebuild comparisons and signed repository metadata before a package is trusted by Deku clients.
