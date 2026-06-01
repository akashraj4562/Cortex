"""Tests for splitter.py — multi-item paste detection and splitting."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from splitter import split_items

# Exact paste from user (iOS WhatsApp format with time-first timestamps)
REAL_WHATSAPP_PASTE = (
    "[1:11 PM, 5/31/2026] Akash Raj: https://www.linkedin.com/posts/jeevanshu-narang_few-months-ago "
    "\n\nSwiggy\n"
    "[1:39 PM, 5/31/2026] Akash Raj: https://www.linkedin.com/posts/activity-1234 "
    "\n\nImprove Google map\n"
    "[4:46 PM, 5/31/2026] Akash Raj: https://www.linkedin.com/posts/siddharthadhar_lead "
    "\n\nJob\n"
    "[8:06 AM, 6/1/2026] Akash Raj: https://www.linkedin.com/posts/ritu-mishra_product "
    "\n\nJob\n"
    "[8:06 AM, 6/1/2026] Akash Raj: https://www.linkedin.com/posts/eordax_ai "
    "\n\nClaude"
)


class TestSplitter(unittest.TestCase):

    # ── Core cases ──

    def test_single_text_unchanged(self):
        items = split_items("Remind me to call Vikas Thursday")
        self.assertEqual(len(items), 1)
        self.assertIn("Vikas", items[0])

    def test_single_url_unchanged(self):
        items = split_items("https://example.com/article")
        self.assertEqual(len(items), 1)

    def test_url_plus_inline_keyword_unchanged(self):
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

    # ── WhatsApp global format [DD/MM/YYYY, HH:MM AM/PM] ──

    def test_whatsapp_global_format_splits(self):
        blob = (
            "[01/06/2026, 10:30 AM] Akash: https://techcrunch.com/ai\n"
            "[01/06/2026, 10:31 AM] Akash: Payments article interesting\n"
            "[01/06/2026, 10:32 AM] Akash: Call mom tomorrow"
        )
        items = split_items(blob)
        self.assertGreaterEqual(len(items), 2)

    def test_whatsapp_global_short_year(self):
        blob = (
            "[1/6/26, 10:30 AM] Me: check this out https://url.com\n"
            "[1/6/26, 10:31 AM] Me: also this one https://url2.com"
        )
        items = split_items(blob)
        self.assertGreaterEqual(len(items), 2)

    # ── WhatsApp iOS format [H:MM AM/PM, M/DD/YYYY] ──

    def test_whatsapp_ios_format_splits(self):
        """iOS WhatsApp format: time first, then date."""
        blob = (
            "[1:11 PM, 5/31/2026] Akash Raj: https://linkedin.com/posts/abc \n\nSwiggy\n"
            "[1:39 PM, 5/31/2026] Akash Raj: https://linkedin.com/posts/def \n\nJob\n"
        )
        items = split_items(blob)
        self.assertEqual(len(items), 2)

    def test_whatsapp_ios_format_five_messages(self):
        """Real paste from user — 5 LinkedIn URLs with iOS timestamps."""
        items = split_items(REAL_WHATSAPP_PASTE)
        self.assertEqual(len(items), 5)

    def test_whatsapp_ios_url_keyword_preserved_in_item(self):
        """Each item should contain both the URL and the keyword."""
        items = split_items(REAL_WHATSAPP_PASTE)
        # Item 1 should contain the Swiggy URL and keyword
        self.assertTrue(any("jeevanshu" in i for i in items))
        self.assertTrue(any("Swiggy" in i for i in items))
        # They should be in the SAME item
        swiggy_item = next((i for i in items if "jeevanshu" in i), None)
        self.assertIsNotNone(swiggy_item)
        self.assertIn("Swiggy", swiggy_item)

    def test_whatsapp_ios_job_keyword_in_item(self):
        """Job keyword should be in same item as the job URL."""
        items = split_items(REAL_WHATSAPP_PASTE)
        job_items = [i for i in items if "siddharthadhar" in i or "ritu-mishra" in i]
        for item in job_items:
            self.assertIn("Job", item)

    def test_whatsapp_ios_claude_keyword_in_item(self):
        """Claude keyword should be in same item as the Claude URL."""
        items = split_items(REAL_WHATSAPP_PASTE)
        claude_item = next((i for i in items if "eordax" in i), None)
        self.assertIsNotNone(claude_item)
        self.assertIn("Claude", claude_item)

    # ── URL + keyword (double-newline, non-WhatsApp) ──
    # These are the mobile sharing patterns that caused the double-capture bug.
    # URL\n\nshort-keyword must stay as ONE item (URL + topic_hint), not split.

    def test_url_newline_keyword_stays_one_item(self):
        """Mobile share: URL then blank line then short keyword → 1 item."""
        blob = "https://www.linkedin.com/posts/sumitkrpal_focuslens\n\nInteresting read"
        items = split_items(blob)
        self.assertEqual(len(items), 1)
        self.assertIn("Interesting read", items[0])
        self.assertIn("sumitkrpal", items[0])

    def test_url_newline_single_word_keyword_stays_one_item(self):
        """Single-word keyword after URL → 1 item."""
        blob = "https://www.linkedin.com/posts/vivek-tiwari\n\nInterseting"
        items = split_items(blob)
        self.assertEqual(len(items), 1)

    def test_two_url_keyword_pairs_split_correctly(self):
        """Two URL+keyword pairs → 2 items, each with its keyword."""
        blob = (
            "https://www.linkedin.com/posts/eordax_ai\n\nClaude\n\n"
            "https://www.linkedin.com/posts/ritu-mishra_product\n\nJob"
        )
        items = split_items(blob)
        self.assertEqual(len(items), 2)
        claude_item = next((i for i in items if "eordax" in i), None)
        job_item = next((i for i in items if "ritu-mishra" in i), None)
        self.assertIsNotNone(claude_item)
        self.assertIn("Claude", claude_item)
        self.assertIsNotNone(job_item)
        self.assertIn("Job", job_item)

    def test_url_newline_long_text_splits(self):
        """Long text (> 60 chars) after a bare URL is treated as a separate item, not a topic hint."""
        blob = (
            "https://linkedin.com/posts/someone\n\n"
            "This is a long standalone note that is clearly not a topic hint but its own thought entirely"
        )
        items = split_items(blob)
        self.assertEqual(len(items), 2)

    def test_two_urls_no_keywords_split(self):
        """Two URLs separated by double newline → 2 items (no keyword merging)."""
        blob = "https://url1.com/article\n\nhttps://url2.com/article"
        items = split_items(blob)
        self.assertEqual(len(items), 2)

    def test_url_keyword_then_standalone_text(self):
        """URL+keyword pair followed by a standalone text → 2 items."""
        blob = (
            "https://linkedin.com/posts/abc\n\nSwiggy\n\n"
            "Remind me to follow up with Vikas on Thursday"
        )
        items = split_items(blob)
        self.assertEqual(len(items), 2)
        self.assertTrue(any("abc" in i and "Swiggy" in i for i in items))
        self.assertTrue(any("Vikas" in i for i in items))

    # ── Other formats ──

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
