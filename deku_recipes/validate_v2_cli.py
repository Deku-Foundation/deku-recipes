"""CLI for the strict declarative recipe v2 validator."""
import argparse
import sys

from .v2 import RecipeV2Error, load_and_validate_v2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Deku recipe v2 metadata without downloading or building"
    )
    parser.add_argument("recipe", help="path to a recipe v2 JSON descriptor")
    args = parser.parse_args()
    try:
        recipe = load_and_validate_v2(args.recipe)
    except RecipeV2Error as exc:
        print(f"invalid recipe v2: {exc}", file=sys.stderr)
        return 2
    targets = ", ".join(
        f"{target['architecture']}:{target['abi']}" for target in recipe["targets"]
    )
    print("recipe v2 valid (metadata only; no source download or build performed)")
    print(f"package: {recipe['name']} {recipe['version']}")
    print(f"targets: {targets}")
    print(f"build steps: {len(recipe['build']['steps'])}; tests: {len(recipe['tests'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
