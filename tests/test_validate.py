from copy import deepcopy
import json
import unittest
from pathlib import Path

from deku_recipes.validate import RecipeValidationError, load_and_validate, validate_recipe

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

    def test_unknown_fields_are_rejected(self):
        recipe = deepcopy(self.recipe)
        recipe["run_shell"] = "make install"
        with self.assertRaisesRegex(RecipeValidationError, "unsupported fields"):
            validate_recipe(recipe)


if __name__ == "__main__":
    unittest.main()
