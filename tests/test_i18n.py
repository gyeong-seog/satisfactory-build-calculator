"""Translation catalog consistency checks."""

import string
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ui.i18n import STRINGS


class TranslationTests(unittest.TestCase):
    def test_languages_have_identical_keys(self) -> None:
        self.assertEqual(set(STRINGS["ko"]), set(STRINGS["en"]))

    def test_translations_use_identical_format_fields(self) -> None:
        formatter = string.Formatter()
        for key, korean in STRINGS["ko"].items():
            english = STRINGS["en"][key]
            korean_fields = {name for _, name, _, _ in formatter.parse(korean) if name}
            english_fields = {name for _, name, _, _ in formatter.parse(english) if name}
            self.assertEqual(korean_fields, english_fields, key)

    def test_english_interface_catalog_contains_no_korean(self) -> None:
        for key, value in STRINGS["en"].items():
            self.assertFalse(any("가" <= character <= "힣" for character in value), key)


if __name__ == "__main__":
    unittest.main()
