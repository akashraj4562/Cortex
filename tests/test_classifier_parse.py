"""Tests for classifier.parse_input — input pattern detection. No Claude API calls."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import MagicMock, patch

with patch.dict('sys.modules', {'anthropic': MagicMock()}):
    from classifier import parse_input, is_substack


class TestParseInput(unittest.TestCase):

    # ── Basic URL patterns ──

    def test_url_only(self):
        url, hint, etype = parse_input("https://example.com/article")
        self.assertEqual(url, "https://example.com/article")
        self.assertIsNone(hint)

    def test_url_with_inline_keyword(self):
        url, hint, etype = parse_input("https://example.com/article Claude")
        self.assertEqual(url, "https://example.com/article")
        self.assertEqual(hint, "Claude")

    def test_url_with_multi_word_hint(self):
        url, hint, etype = parse_input("https://example.com payments learn")
        self.assertEqual(url, "https://example.com")
        self.assertEqual(hint, "payments learn")

    def test_plain_text(self):
        url, hint, etype = parse_input("Remind me to call Vikas Thursday 4pm")
        self.assertIsNone(url)
        self.assertIsNone(hint)
        self.assertIsNone(etype)

    def test_whitespace_stripped(self):
        url, hint, etype = parse_input("  https://example.com  Claude  ")
        self.assertEqual(url, "https://example.com")
        self.assertEqual(hint, "Claude")

    # ── Multi-line keyword (WhatsApp style: URL then keyword on next line) ──

    def test_url_keyword_on_next_line(self):
        """WhatsApp style: URL on line 1, blank line, keyword on line 3."""
        raw = "https://linkedin.com/posts/abc \n\nSwiggy"
        url, hint, etype = parse_input(raw)
        self.assertIsNotNone(url)
        self.assertEqual(hint, "Swiggy")

    def test_url_multiword_keyword_on_next_line(self):
        raw = "https://linkedin.com/posts/xyz \n\nImprove Google map"
        url, hint, etype = parse_input(raw)
        self.assertEqual(hint, "Improve Google map")

    def test_url_job_keyword_on_next_line(self):
        raw = "https://linkedin.com/posts/job123 \n\nJob"
        url, hint, etype = parse_input(raw)
        self.assertEqual(hint, "Job")
        self.assertEqual(etype, "job_post")

    # ── Explicit type keywords ──

    def test_explicit_keyword_job(self):
        _, hint, etype = parse_input("https://example.com Job")
        self.assertEqual(etype, "job_post")

    def test_explicit_keyword_jobs(self):
        _, hint, etype = parse_input("https://example.com jobs")
        self.assertEqual(etype, "job_post")

    def test_explicit_keyword_job_case_insensitive(self):
        _, hint, etype = parse_input("https://example.com JOB")
        self.assertEqual(etype, "job_post")

    def test_explicit_keyword_reminder(self):
        _, hint, etype = parse_input("https://example.com reminder")
        self.assertEqual(etype, "reminder")

    def test_explicit_keyword_idea(self):
        _, hint, etype = parse_input("https://example.com idea")
        self.assertEqual(etype, "product_idea")

    def test_topic_hint_not_explicit(self):
        """Topic hints like 'Swiggy', 'Claude' should NOT be explicit types."""
        _, hint, etype = parse_input("https://example.com Swiggy")
        self.assertEqual(hint, "Swiggy")
        self.assertIsNone(etype)  # not an explicit classification keyword

    def test_topic_hint_claude_not_explicit(self):
        _, hint, etype = parse_input("https://example.com Claude")
        self.assertEqual(hint, "Claude")
        self.assertIsNone(etype)

    # ── LinkedIn URL pattern detection ──

    def test_linkedin_posts_url_infers_blog_post(self):
        _, _, etype = parse_input("https://www.linkedin.com/posts/jeevanshu-narang_abc")
        self.assertEqual(etype, "blog_post")

    def test_linkedin_activity_url_infers_blog_post(self):
        _, _, etype = parse_input("https://www.linkedin.com/posts/activity-7464940271676444672-iZt3")
        self.assertEqual(etype, "blog_post")

    def test_linkedin_jobs_url_infers_job_post(self):
        _, _, etype = parse_input("https://www.linkedin.com/jobs/view/12345")
        self.assertEqual(etype, "job_post")

    def test_explicit_keyword_overrides_linkedin_inference(self):
        """User writes 'Job' explicitly — even for a linkedin/posts URL, honour user."""
        _, _, etype = parse_input("https://www.linkedin.com/posts/abc \n\nJob")
        self.assertEqual(etype, "job_post")

    def test_topic_hint_does_not_set_explicit_type_for_linkedin(self):
        """'Swiggy' hint on a linkedin/posts URL → blog_post from URL, not from hint."""
        _, hint, etype = parse_input("https://www.linkedin.com/posts/swiggy-post \n\nSwiggy")
        self.assertEqual(hint, "Swiggy")
        self.assertEqual(etype, "blog_post")  # from LinkedIn URL pattern


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
