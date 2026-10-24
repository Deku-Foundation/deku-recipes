from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from deku_recipes.v2 import (
    MAX_RECIPE_BYTES,
    RecipeV2Error,
    load_and_validate_v2,
    validate_recipe_v2,
    validate_spdx_expression,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "hello-v2.json"


class RecipeV2Tests(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_is_valid(self):
        self.assertEqual(validate_recipe_v2(self.recipe), self.recipe)

    def test_spdx_expression_grammar(self):
        for expression in (
            "MIT",
            "MIT OR Apache-2.0",
            "GPL-2.0-only WITH Classpath-exception-2.0",
            "(MIT OR Apache-2.0) AND BSD-3-Clause",
        ):
            with self.subTest(expression=expression):
                validate_spdx_expression(expression)

    def test_invalid_spdx_operators_are_rejected(self):
        for expression in ("MIT AND OR Apache-2.0", "MIT WITH", "(MIT OR Apache-2.0", "AND MIT"):
            with self.subTest(expression=expression):
                with self.assertRaises(RecipeV2Error):
                    validate_spdx_expression(expression)

    def test_unknown_fields_fail_closed(self):
        recipe = deepcopy(self.recipe)
        recipe["execute"] = "arbitrary shell"
        with self.assertRaisesRegex(RecipeV2Error, "exactly"):
            validate_recipe_v2(recipe)

    def test_mutable_source_revision_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["revision"] = "main"
        with self.assertRaisesRegex(RecipeV2Error, "40-character"):
            validate_recipe_v2(recipe)

    def test_source_credentials_query_and_fragment_are_rejected(self):
        for url in (
            "https://user:pass@example.invalid/repo.git",
            "https://example.invalid/repo.git?token=secret",
            "https://example.invalid/repo.git#main",
        ):
            recipe = deepcopy(self.recipe)
            recipe["source"]["url"] = url
            with self.subTest(url=url):
                with self.assertRaises(RecipeV2Error):
                    validate_recipe_v2(recipe)

    def test_patches_require_unique_safe_paths_and_digests(self):
        recipe = deepcopy(self.recipe)
        recipe["patches"] = [
            {"path": "../escape.patch", "sha256": "a" * 64}
        ]
        with self.assertRaisesRegex(RecipeV2Error, "unsafe path|invalid path"):
            validate_recipe_v2(recipe)
        recipe = deepcopy(self.recipe)
        patch = {"path": "patches/fix.patch", "sha256": "a" * 64}
        recipe["patches"] = [patch, deepcopy(patch)]
        with self.assertRaisesRegex(RecipeV2Error, "duplicate patch"):
            validate_recipe_v2(recipe)

    def test_dependency_classes_are_explicit_and_duplicates_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["dependencies"]["runtime"] = [
            {"name": "zlib", "constraint": ">=1.2.0"},
            {"name": "zlib", "constraint": ">=1.2.0"},
        ]
        with self.assertRaisesRegex(RecipeV2Error, "duplicate runtime dependency"):
            validate_recipe_v2(recipe)

    def test_network_enabled_build_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["build"]["network"] = "enabled"
        with self.assertRaisesRegex(RecipeV2Error, "network must be disabled"):
            validate_recipe_v2(recipe)

    def test_builder_image_must_be_digest_pinned_and_well_formed(self):
        for image in (
            "ghcr.io/deku-foundation/build-env:latest",
            "ghcr.io/deku-foundation/../escape@sha256:" + "b" * 64,
            "ghcr.io/deku-foundation/build-env@sha256:" + "B" * 64,
        ):
            recipe = deepcopy(self.recipe)
            recipe["build"]["environment_image"] = image
            with self.subTest(image=image):
                with self.assertRaises(RecipeV2Error):
                    validate_recipe_v2(recipe)

    def test_output_traversal_and_file_directory_collisions_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["outputs"][0]["path"] = "dist/../escape.pkg"
        with self.assertRaises(RecipeV2Error):
            validate_recipe_v2(recipe)
        recipe = deepcopy(self.recipe)
        recipe["outputs"] = [
            {"path": "dist", "kind": "file"},
            {"path": "dist/hello.pkg", "kind": "package"},
        ]
        with self.assertRaisesRegex(RecipeV2Error, "collision"):
            validate_recipe_v2(recipe)

    def test_malformed_types_fail_with_validation_errors_not_type_errors(self):
        recipe = deepcopy(self.recipe)
        recipe["targets"][0]["architecture"] = []
        with self.assertRaises(RecipeV2Error):
            validate_recipe_v2(recipe)
        recipe = deepcopy(self.recipe)
        recipe["outputs"][0]["kind"] = []
        with self.assertRaises(RecipeV2Error):
            validate_recipe_v2(recipe)

    def test_duplicate_json_keys_and_oversized_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            duplicate = Path(temp_dir) / "duplicate.json"
            duplicate.write_text('{"schema_version":2,"schema_version":2}', encoding="utf-8")
            with self.assertRaisesRegex(RecipeV2Error, "duplicate JSON object key"):
                load_and_validate_v2(duplicate)
            huge = Path(temp_dir) / "huge.json"
            huge.write_bytes(b" " * (MAX_RECIPE_BYTES + 1))
            with self.assertRaisesRegex(RecipeV2Error, "input limit"):
                load_and_validate_v2(huge)


if __name__ == "__main__":
    unittest.main()
