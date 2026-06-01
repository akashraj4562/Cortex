"""Tests for classifier.parse_input — input pattern detection. No Claude API calls."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Patch out anthropic before import so no API key needed
import unittest
from unittest.mock import MagicMock, patch

with patch.dict('sys.modules', {'anthropic': MagicMock()}):
    from classifier import parse_input, is_substack


class TestParseInput(unittest.TestCase):

    def test_url_only(self):
        url, hint, _ = parse_input("https://example.com/article")
        self.assertEqual(url, "https://example.com/article")
        self.assertIsNone(hint)

    def test_url_with_keyword(self):
        url, hint, _ = parse_input("https://example.com/article Claude")
        self.assertEqual(url, "https://example.com/article")
        self.assertEqual(hint, "Claude")

    def test_url_with_multi_word_hint(self):
        url, hint, _ = parse_input("https://example.com payments learn")
        self.assertEqual(url, "https://example.com")
        self.assertEqual(hint, "payments learn")

    def test_plain_text(self):
        url, hint, text = parse_input("Remind me to call Vikas Thursday 4pm")
        self.assertIsNone(url)
        self.assertIsNone(hint)
        self.assertIn("Vikas", text)

    def test_www_url(self):
        url, hint, _ = parse_input("www.stripe.com/docs Payments")
        self.assertIsNotNone(url)
        self.assertEqual(hint, "Payments")

    def test_whitespace_stripped(self):
        url, hint, _ = parse_input("  https://example.com  Claude  ")
        self.assertEqual(url, "https://example.com")
        self.assertEqual(hint, "Claude")


class TestIsSubstack(unittest.TestCase):

    def test_substack_url(self):
        self.assertTrue(is_substack("https://newsletter.substack.com/p/article"))

    def test_non_substack(self):
        self.assertFalse(is_substack("https://techcrunch.com/article"))

    def test_none(self):
        self.assertFalse(is_substack(None))

    def test_empty(self):
        self.assertFalse(is_substack(""))


if __name__ == "__main__":
    unittest.main()
