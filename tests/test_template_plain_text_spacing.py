"""Tests for plain-text spacing normalization (DOCX pipeline)."""

import unittest

from app.utils.template_plain_text_spacing import (
    finalize_plain_text_for_docx,
    compact_blank_lines_between_consecutive_list_lines,
)


class TestTemplatePlainTextSpacing(unittest.TestCase):
    def test_compact_drops_blank_between_two_list_lines(self):
        lines = ["• First", "", "• Second"]
        self.assertEqual(
            compact_blank_lines_between_consecutive_list_lines(lines),
            ["• First", "• Second"],
        )

    def test_finalize_without_template_collapses_triple_newlines_and_lists(self):
        inp = "Para one.\n\n\n\nPara two.\n\n- Item A\n\n\n- Item B\n\nClosing."
        out = finalize_plain_text_for_docx(inp, None)
        self.assertNotIn("\n\n\n", out)
        self.assertIn("- Item A\n- Item B", out)

    def test_finalize_unescapes_literal_backslash_n(self):
        inp = "Line A\\n\\nLine B"
        out = finalize_plain_text_for_docx(inp, None)
        self.assertEqual(out, "Line A\n\nLine B")
        self.assertNotIn("\\n", out)

    def test_finalize_unescapes_literal_newlines_before_triple_collapse(self):
        inp = "Line A\\n\\n\\n\\nLine B"
        out = finalize_plain_text_for_docx(inp, None)
        self.assertEqual(out, "Line A\n\nLine B")

    def test_finalize_with_template_still_collapses_triple_newlines(self):
        """Collapse is unconditional; templates do not preserve extra blank lines."""
        content = "April 04, 2026\n\n\nHiring Manager\nDeloitte\n\nRe: Manager"
        template = "<<date>>\n\n\n<<hiring manager>>\n<<company name>>\n\nRe: <<position title>>"
        out = finalize_plain_text_for_docx(content, template)
        self.assertEqual(out, "April 04, 2026\n\nHiring Manager\nDeloitte\n\nRe: Manager")


if __name__ == "__main__":
    unittest.main()
