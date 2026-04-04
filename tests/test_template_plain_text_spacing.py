"""Tests for template-driven plain-text vertical spacing (DOCX pipeline)."""

import unittest

from app.utils.template_plain_text_spacing import (
    enforce_plain_text_line_spacing_from_template,
    _blanks_between_nonempty_template_lines,
)


class TestTemplatePlainTextSpacing(unittest.TestCase):
    def test_blanks_between_nonempty_template_lines_counts_empty_rows(self):
        template = "<<a>>\n\n\n<<b>>\n<<c>>"
        self.assertEqual(_blanks_between_nonempty_template_lines(template), [2, 0])

    def test_enforce_spacing_inserts_blank_lines_from_template(self):
        # Four newlines after <<date>> gives three blank lines before hiring manager.
        template = (
            "<<date>>\n\n\n\n<<hiring manager>>\n<<company name>>\n\n"
            "Re: <<position title>>\n\n\n<<salutation>>,\n\n<<body paragraphs>>\n\n\n"
            "<<complimentary close>>,\n\n<<name>>\n<<email>> | <<phone>>"
        )
        content = """April 04, 2026
Hiring Manager
Deloitte
Re: Manager - Generative AI
Dear Hiring Manager,

First body.

Sincerely,
Jane Doe
jane@example.com | 555-1234"""

        out = enforce_plain_text_line_spacing_from_template(content, template)
        lines = out.split("\n")
        self.assertEqual(lines[0], "April 04, 2026")
        self.assertEqual(lines[1:4], ["", "", ""])
        self.assertEqual(lines[4], "Hiring Manager")


if __name__ == "__main__":
    unittest.main()
