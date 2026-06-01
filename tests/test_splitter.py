"""Tests for splitter.py — multi-item paste detection and splitting."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from splitter import split_items


class TestSplitter(unittest.TestCase):

    def test_single_text_unchanged(self):
        items = split_items("Remind me to call Vikas Thursday")
        self.assertEqual(len(items), 1)
        self.assertIn("Vikas", items[0])

    def test_single_url_unchanged(self):
        items = split_items("https://example.com/article")
        self.assertEqual(len(items), 1)

    def test_url_plus_keyword_unchanged(self):
        # URL + keyword is a single item (not multi)
        items = split_items("https://example.com/article Claude")
        self.assertEqual(len(items), 1)

    def test_double_newline_splits(self):
        blob = "https://example.com/a\n\nhttps://example.com/b"
        items = split_items(blob)
        self.assertEqual(len(items), 2)

    def test_three_paragraphs(self):
        blob = "First thought\n\nSecond thought\n\nThird thought"
        items = split_items(blob)
        self.assertEqual(len(items), 3)

    def test_whatsapp_timestamp_splits(self):
        blob = (
            "[01/06/2026, 10:30 AM] Akash: https://techcrunch.com/ai\n"
            "[01/06/2026, 10:31 AM] Akash: Payments article interesting\n"
            "[01/06/2026, 10:32 AM] Akash: Call mom tomorrow"
        )
        items = split_items(blob)
        self.assertGreaterEqual(len(items), 2)

    def test_whatsapp_short_format(self):
        blob = (
            "[1/6/26, 10:30 AM] Me: check this out https://url.com\n"
            "[1/6/26, 10:31 AM] Me: also this one https://url2.com"
        )
        items = split_items(blob)
        self.assertGreaterEqual(len(items), 2)

    def test_multiple_bare_urls_on_lines(self):
        blob = "https://url1.com\nhttps://url2.com\nhttps://url3.com"
        items = split_items(blob)
        self.assertEqual(len(items), 3)

    def test_dedup_identical_items(self):
        blob = "same thought\n\nsame thought"
        items = split_items(blob)
        self.assertEqual(len(items), 1)

    def test_empty_input(self):
        items = split_items("")
        self.assertEqual(items, [])

    def test_whitespace_only(self):
        items = split_items("   \n\n   ")
        self.assertEqual(items, [])

    def test_mixed_content(self):
        blob = (
            "https://stripe.com/blog/payments Payments\n\n"
            "Remind me to follow up with Vikas Thursday\n\n"
            "https://substack.com/ai-weekly AI"
        )
        items = split_items(blob)
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
