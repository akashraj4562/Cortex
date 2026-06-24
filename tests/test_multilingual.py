"""PRD-CORTEX-006 — Hindi / multilingual image & text understanding.

Offline contract tests (Claude mocked). They lock:
  - routing parity (a Hindi shopping list clears HIGH_CONFIDENCE just like English),
  - the field contract (original_text keeps Devanagari verbatim; action fields are English),
  - the multilingual instruction is present in every classifier system prompt,
  - Devanagari survives a DB round-trip (UTF-8).
Model behaviour (does Opus actually normalize) is validated in the live spot-check (TECH-006 §5).
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import classifier
import db


def _mock_response(body: dict) -> MagicMock:
    msg = MagicMock()
    # ensure_ascii=False so the mock carries real Devanagari, like the live API does
    msg.content = [MagicMock(text=json.dumps(body, ensure_ascii=False))]
    return msg


HINDI_SHOPPING = {
    "type": "shopping_list",
    "confidence": 0.92,
    "rationale": "Handwritten grocery list",
    "metadata": {
        "description": "handwritten grocery list",
        "extracted_text": "दूध, अंडे, ब्रेड, प्याज़",
        "original_text": "दूध, अंडे, ब्रेड, प्याज़",
        "language": "hi",
        "title": "Grocery list",
        "items": ["milk", "eggs", "bread", "onions"],
        "store_hint": "zepto",
        "notes": "",
        "structured_data": {},
    },
    "tags": ["grocery", "shopping"],
    "suggested_new_type": None,
}

HINDI_REMINDER = {
    "type": "reminder",
    "confidence": 0.88,
    "rationale": "A dated task written in Hindi",
    "metadata": {
        "description": "note with a date",
        "extracted_text": "कल डॉक्टर को बुलाना है",
        "original_text": "कल डॉक्टर को बुलाना है",
        "language": "hi",
        "task": "Call the doctor",
        "due_date": None,
        "priority": "medium",
        "structured_data": {},
    },
    "tags": ["reminder", "health"],
    "suggested_new_type": None,
}


class TestMultilingualImageRouting(unittest.TestCase):
    def test_hindi_shopping_list_routes_assign(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(HINDI_SHOPPING)):
            r = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(r["type"], "shopping_list")
        self.assertEqual(r["routing"], "assign")  # parity: Hindi clears HIGH_CONFIDENCE 0.80

    def test_hindi_reminder_routes_assign(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(HINDI_REMINDER)):
            r = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(r["type"], "reminder")
        self.assertEqual(r["routing"], "assign")


class TestMultilingualFieldContract(unittest.TestCase):
    def test_original_text_keeps_devanagari(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(HINDI_SHOPPING)):
            r = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(r["metadata"]["language"], "hi")
        self.assertIn("दूध", r["metadata"]["original_text"])

    def test_shopping_items_normalized_to_english(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(HINDI_SHOPPING)):
            r = classifier.classify_image("b64==", "image/jpeg")
        for item in r["metadata"]["items"]:
            self.assertTrue(item.isascii(), f"shopping item not English/romanized: {item!r}")


class TestMultilingualPromptPresence(unittest.TestCase):
    """A future prompt edit must not silently drop the multilingual instruction."""

    def test_image_prompt_has_multilingual_block(self):
        for needle in ("Multilingual", "original_text", "language", "Devanagari"):
            self.assertIn(needle, classifier._IMAGE_SYSTEM)

    def test_text_prompts_have_multilingual_block(self):
        self.assertIn("original_text", classifier._SYSTEM)
        self.assertIn("Multilingual", classifier._SYSTEM)
        self.assertIn("original_text", classifier._SIMILARITY_SYSTEM)

    def test_item_extractor_requires_english_names(self):
        self.assertIn("English/romanized", classifier._EXTRACT_ITEMS_SYSTEM)

    def test_prompts_still_format_cleanly(self):
        """The added text must not break the .format() placeholders."""
        for tmpl in (classifier._IMAGE_SYSTEM, classifier._SYSTEM, classifier._SIMILARITY_SYSTEM):
            # Should not raise KeyError/ValueError from stray single braces
            tmpl.format(type_list="-", known_projects="[]", today="2026-06-24")


class TestDevanagariRoundTrip(unittest.TestCase):
    """Devanagari survives insert → read (UTF-8 end-to-end)."""

    def test_metadata_roundtrip(self):
        meta = {
            "original_text": "दूध, अंडे, ब्रेड",
            "language": "hi",
            "items": ["milk", "eggs", "bread"],
        }
        cid = db.insert_capture("दूध अंडे ब्रेड", "shopping_list", 0.92,
                                "Hindi grocery list", meta, ["grocery"],
                                input_type="image")
        card = db.get_capture(cid)
        got = card["metadata"] if isinstance(card["metadata"], dict) else json.loads(card["metadata"])
        self.assertEqual(got["original_text"], "दूध, अंडे, ब्रेड")
        self.assertEqual(got["language"], "hi")
        self.assertEqual(got["items"], ["milk", "eggs", "bread"])


if __name__ == "__main__":
    unittest.main()
