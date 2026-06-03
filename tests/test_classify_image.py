"""Unit tests for classifier.classify_image() — Phase B."""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import classifier


def _mock_response(body: dict) -> MagicMock:
    """Build a mock Anthropic response object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(body))]
    return msg


_FULL_RESPONSE = {
    "type": "reminder",
    "confidence": 0.91,
    "rationale": "Dentist appointment card with a clear due date",
    "metadata": {
        "description": "Dentist appointment card",
        "extracted_text": "Dr. Mehta — July 15, 2026 at 3pm",
        "structured_data": {"due_date": "2026-07-15", "due_time": "15:00",
                            "price": None, "names": ["Dr. Mehta"], "location": None},
        "task": "Dentist appointment",
        "due_date": "2026-07-15",
        "priority": "high",
    },
    "tags": ["dentist", "appointment", "health"],
    "suggested_new_type": None,
}


class TestClassifyImage(unittest.TestCase):

    # ── 4.1 Image content block format ──────────────────────────────────────

    def test_image_content_block_format(self):
        """Verify the Anthropic call uses an image content block with correct structure."""
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)) as mock_create:
            classifier.classify_image("base64data==", "image/jpeg", hint="")
            call_kwargs = mock_create.call_args.kwargs
            messages = call_kwargs["messages"]
            content = messages[0]["content"]

            # First element must be the image block
            image_block = content[0]
            self.assertEqual(image_block["type"], "image")
            self.assertEqual(image_block["source"]["type"], "base64")
            self.assertEqual(image_block["source"]["media_type"], "image/jpeg")
            self.assertEqual(image_block["source"]["data"], "base64data==")

            # Second element must be the text prompt
            text_block = content[1]
            self.assertEqual(text_block["type"], "text")

    # ── 4.2 Full field parse ─────────────────────────────────────────────────

    def test_full_field_parse(self):
        """All fields from the LLM response are correctly parsed and returned."""
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)):
            result = classifier.classify_image("b64==", "image/jpeg")

        self.assertEqual(result["type"], "reminder")
        self.assertAlmostEqual(result["confidence"], 0.91)
        self.assertEqual(result["routing"], "assign")
        self.assertEqual(result["metadata"]["description"], "Dentist appointment card")
        self.assertEqual(result["metadata"]["extracted_text"], "Dr. Mehta — July 15, 2026 at 3pm")
        self.assertEqual(result["metadata"]["structured_data"]["due_date"], "2026-07-15")

    # ── 4.3 Routing — assign at high confidence ──────────────────────────────

    def test_routing_assign_high_confidence(self):
        body = {**_FULL_RESPONSE, "confidence": 0.85, "type": "general_note"}
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(body)):
            result = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(result["routing"], "assign")

    # ── 4.4 Routing — unknown at mid confidence ──────────────────────────────

    def test_routing_unknown_mid_confidence(self):
        body = {**_FULL_RESPONSE, "confidence": 0.55, "type": "general_note"}
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(body)):
            result = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(result["routing"], "unknown")
        self.assertEqual(result["type"], "unknown")

    # ── 4.5 Routing — new_type at low confidence with suggestion ─────────────

    def test_routing_new_type_low_confidence(self):
        body = {
            "type": "receipt",
            "confidence": 0.12,
            "rationale": "Looks like a grocery receipt",
            "metadata": {"description": "grocery receipt", "extracted_text": "Total: ₹450",
                         "structured_data": {}},
            "tags": ["shopping"],
            "suggested_new_type": {"key": "receipt", "label": "Receipt", "icon": "🧾"},
        }
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(body)):
            result = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(result["routing"], "new_type")
        self.assertEqual(result["suggested_new_type"]["key"], "receipt")

    # ── 4.6 max_tokens ≥ 1200 ────────────────────────────────────────────────

    def test_max_tokens_at_least_1200(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)) as mock_create:
            classifier.classify_image("b64==", "image/jpeg")
            call_kwargs = mock_create.call_args.kwargs
            self.assertGreaterEqual(call_kwargs["max_tokens"], 1200)

    # ── 4.7 Hint injected into text prompt ───────────────────────────────────

    def test_hint_injected_into_prompt(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)) as mock_create:
            classifier.classify_image("b64==", "image/jpeg", hint="shopping list")
            call_kwargs = mock_create.call_args.kwargs
            messages = call_kwargs["messages"]
            text_block = messages[0]["content"][1]
            self.assertIn("shopping list", text_block["text"])

    # ── 4.8 No-hint path — prompt still valid ────────────────────────────────

    def test_no_hint_prompt_valid(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)) as mock_create:
            result = classifier.classify_image("b64==", "image/jpeg", hint="")
            # Should not raise; type should be parsed
            self.assertIn("type", result)
            call_kwargs = mock_create.call_args.kwargs
            text_block = call_kwargs["messages"][0]["content"][1]
            # No empty "hint:" line should appear
            self.assertNotIn("hint:", text_block["text"].lower().split("classify")[0])

    # ── Explicit type override ────────────────────────────────────────────────

    def test_explicit_type_overrides_llm(self):
        body = {**_FULL_RESPONSE, "type": "general_note", "confidence": 0.60}
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(body)):
            result = classifier.classify_image("b64==", "image/jpeg", explicit_type="reminder")
        self.assertEqual(result["type"], "reminder")
        self.assertEqual(result["routing"], "assign")
        self.assertGreaterEqual(result["confidence"], 0.80)

    # ── JSON parse error fallback ─────────────────────────────────────────────

    def test_json_parse_error_returns_unknown(self):
        bad_msg = MagicMock()
        bad_msg.content = [MagicMock(text="not valid json at all")]
        with patch.object(classifier.client.messages, "create", return_value=bad_msg):
            result = classifier.classify_image("b64==", "image/jpeg")
        self.assertEqual(result["type"], "unknown")
        self.assertEqual(result["confidence"], 0.0)

    # ── Model used ────────────────────────────────────────────────────────────

    def test_uses_correct_model(self):
        with patch.object(classifier.client.messages, "create",
                          return_value=_mock_response(_FULL_RESPONSE)) as mock_create:
            classifier.classify_image("b64==", "image/jpeg")
            self.assertEqual(mock_create.call_args.kwargs["model"], classifier.MODEL)
