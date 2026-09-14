"""Tests for LLM cover-letter JSON parse and leaked wrapper stripping."""

import json
import unittest

from app.utils.llm_letter_json import (
    parse_llm_response_json,
    strip_leaked_json_wrapper,
)


SIGNATURE = (
    "Simon Kaltgrad\n"
    "simonkalt@gmail.com | (818) 419-5986"
)


class TestStripLeakedJsonWrapper(unittest.TestCase):
    def test_strips_quote_and_brace_after_signature(self):
        leaked = f'{SIGNATURE}"\n}}'
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)

    def test_strips_quote_brace_on_same_line(self):
        leaked = f'{SIGNATURE}" }}'
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)

    def test_strips_literal_backslash_n_between_quote_and_brace(self):
        leaked = SIGNATURE + '"\\n}'
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)

    def test_preserves_closing_quotation_without_brace(self):
        text = 'He said "yes."'
        self.assertEqual(strip_leaked_json_wrapper(text), text)

    def test_preserves_clean_signature(self):
        self.assertEqual(strip_leaked_json_wrapper(SIGNATURE), SIGNATURE)

    def test_strips_backslash_escaped_quote_and_brace(self):
        leaked = SIGNATURE + '\\"\n}'
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)

    def test_preserves_mid_letter_quotes_when_stripping_closer(self):
        body = 'I have 5 years of "hands-on" experience.\n\n' + SIGNATURE
        self.assertEqual(strip_leaked_json_wrapper(body + '"\n}'), body)

    def test_strips_lone_brace_on_following_page(self):
        leaked = SIGNATURE + "\n\n\n}"
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)

    def test_strips_lone_brace_on_next_line(self):
        leaked = SIGNATURE + "\n}"
        self.assertEqual(strip_leaked_json_wrapper(leaked), SIGNATURE)


class TestParseLlmResponseJson(unittest.TestCase):
    def test_valid_json_unchanged(self):
        letter = f"Dear Hiring Manager,\n\nI am applying.\n\nSincerely,\n{SIGNATURE}"
        raw = json.dumps({"content": letter})
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], letter)

    def test_strips_escaped_closer_inside_valid_json(self):
        """Opus-style: closing quote is escaped so it becomes letter text."""
        raw = json.dumps({"content": SIGNATURE + '"\n}'})
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], SIGNATURE)
        self.assertFalse(parsed["content"].rstrip().endswith("}"))
        self.assertFalse(parsed["content"].rstrip().endswith('"'))

    def test_strips_closer_from_unescaped_newline_json(self):
        raw = (
            '{\n  "content": "Dear Hiring Manager,\n\nHello.\n\n'
            + SIGNATURE
            + '"\n}'
        )
        parsed = parse_llm_response_json(raw)
        self.assertIn("Dear Hiring Manager", parsed["content"])
        self.assertTrue(parsed["content"].rstrip().endswith("419-5986"))
        self.assertNotIn("}", parsed["content"])

    def test_recovers_unterminated_content_without_keeping_closer(self):
        # Escaped closer + unescaped newlines: quote/brace would otherwise land in content.
        raw = '{"content": "' + SIGNATURE + '\\"\n}'
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], SIGNATURE)

    def test_strips_brace_inside_valid_json_after_blank_lines(self):
        raw = json.dumps({"content": SIGNATURE + "\n\n\n}"})
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], SIGNATURE)

    def test_recovers_unterminated_newline_then_object_brace(self):
        raw = '{"content": "' + SIGNATURE + "\n}"
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], SIGNATURE)

    def test_fenced_json_with_leaked_closer(self):
        inner = json.dumps({"content": SIGNATURE + '"\n}'})
        raw = f"```json\n{inner}\n```"
        parsed = parse_llm_response_json(raw)
        self.assertEqual(parsed["content"], SIGNATURE)


if __name__ == "__main__":
    unittest.main()
