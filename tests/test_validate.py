from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from deku_recipes.validate import MAX_DEPENDENCIES, MAX_RECIPE_BYTES, RecipeValidationError, load_and_validate, validate_recipe

EXAMPLE = Path(__file__).parents[1] / "examples" / "hello.json"


class RecipeValidationTests(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_is_valid(self):
        self.assertEqual(validate_recipe(self.recipe), self.recipe)

    def test_load_example(self):
        self.assertEqual(load_and_validate(EXAMPLE)["name"], "hello-example")

    def test_unknown_schema_fails_closed(self):
        recipe = deepcopy(self.recipe)
        recipe["schema_version"] = 2
        with self.assertRaisesRegex(RecipeValidationError, "schema_version"):
            validate_recipe(recipe)

    def test_embedded_credentials_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://name:secret@example.com/repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "embedded credentials"):
            validate_recipe(recipe)

    def test_unpinned_source_revision_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["revision"] = "main"
        with self.assertRaisesRegex(RecipeValidationError, "40-character"):
            validate_recipe(recipe)

    def test_self_dependency_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["dependencies"] = [recipe["name"]]
        with self.assertRaisesRegex(RecipeValidationError, "itself"):
            validate_recipe(recipe)

    def test_duplicate_architecture_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["architectures"] = ["x86_64", "x86_64"]
        with self.assertRaisesRegex(RecipeValidationError, "duplicates"):
            validate_recipe(recipe)

    def test_boolean_schema_version_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["schema_version"] = True
        with self.assertRaisesRegex(RecipeValidationError, "schema_version"):
            validate_recipe(recipe)

    def test_version_cannot_contain_path_or_control_characters(self):
        for version in ["../1.0", "1.0\\n0", " 1.0", "1.0 "]:
            recipe = deepcopy(self.recipe)
            recipe["version"] = version
            with self.subTest(version=version):
                with self.assertRaisesRegex(RecipeValidationError, "invalid package version"):
                    validate_recipe(recipe)

    def test_source_url_query_and_fragment_are_rejected(self):
        for suffix in ["?token=private", "#moving-target"]:
            recipe = deepcopy(self.recipe)
            recipe["source"]["url"] += suffix
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(RecipeValidationError, "query string or fragment"):
                    validate_recipe(recipe)

    def test_source_url_invalid_port_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://example.com:invalid/repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "well-formed HTTPS URL"):
            validate_recipe(recipe)

    def test_source_url_empty_port_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://example.com:/repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "empty port"):
            validate_recipe(recipe)

    def test_source_url_backslashes_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://example.com\\repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "backslashes"):
            validate_recipe(recipe)

    def test_non_https_source_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "http://example.com/repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "absolute HTTPS URL"):
            validate_recipe(recipe)

    def test_malformed_ipv6_source_url_is_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://[::1/repo.git"
        with self.assertRaisesRegex(RecipeValidationError, "well-formed HTTPS URL"):
            validate_recipe(recipe)

    def test_homepage_credentials_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["homepage"] = "https://user:password@example.com/"
        with self.assertRaisesRegex(RecipeValidationError, "embedded credentials"):
            validate_recipe(recipe)

    def test_source_url_control_characters_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["source"]["url"] = "https://example.com/repo.git\\n"
        with self.assertRaisesRegex(RecipeValidationError, "whitespace or control"):
            validate_recipe(recipe)

    def test_summary_must_not_have_outer_whitespace(self):
        recipe = deepcopy(self.recipe)
        recipe["summary"] = " summary "
        with self.assertRaisesRegex(RecipeValidationError, "trimmed string"):
            validate_recipe(recipe)

    def test_dependency_count_is_bounded(self):
        recipe = deepcopy(self.recipe)
        recipe["dependencies"] = [f"dependency-{index}" for index in range(MAX_DEPENDENCIES + 1)]
        with self.assertRaisesRegex(RecipeValidationError, "at most"):
            validate_recipe(recipe)

    def test_oversized_recipe_is_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized.json"
            path.write_bytes(b" " * (MAX_RECIPE_BYTES + 1))
            with self.assertRaisesRegex(RecipeValidationError, "input limit"):
                load_and_validate(path)

    def test_duplicate_json_object_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(RecipeValidationError, "duplicate JSON object key"):
                load_and_validate(path)

    def test_invalid_utf8_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_bytes(b'{"invalid":"' + bytes([0xFF]) + b'"}')
            with self.assertRaisesRegex(RecipeValidationError, "valid UTF-8 JSON"):
                load_and_validate(path)

    def test_excessive_json_nesting_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "deep.json"
            path.write_bytes(b"[" * 10_000 + b"0" + b"]" * 10_000)
            with self.assertRaisesRegex(RecipeValidationError, "valid UTF-8 JSON"):
                load_and_validate(path)

    def test_unknown_fields_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["run_shell"] = "make install"
        with self.assertRaisesRegex(RecipeValidationError, "unsupported fields"):
            validate_recipe(recipe)


if __name__ == "__main__":
    unittest.main()
