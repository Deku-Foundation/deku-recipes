"""Command-line entry point for recipe metadata validation."""
import argparse
import sys

from .validate import RecipeValidationError, load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Deku recipe metadata without downloading or building")
    parser.add_argument("recipe", help="path to a JSON recipe descriptor")
    args = parser.parse_args()
    try:
        recipe = load_and_validate(args.recipe)
    except RecipeValidationError as exc:
        print(f"invalid recipe: {exc}", file=sys.stderr)
        return 2
    print("recipe valid (metadata only; no source download or build performed)")
    print(f"package: {recipe['name']} {recipe['version']}")
    print(f"architectures: {', '.join(recipe['architectures'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
