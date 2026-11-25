import unittest

from limd.llm.markdown_text import strip_markdown


class StripMarkdownTests(unittest.TestCase):
    def test_keeps_inline_and_fenced_code(self) -> None:
        text = strip_markdown("Stack: `Kafka`, `Redis`\n\n```\nfoo\n```\n\n[Docs](http://x.io)")

        self.assertIn("Kafka", text)
        self.assertIn("Redis", text)
        self.assertIn("foo", text)
        self.assertIn("Docs", text)


if __name__ == "__main__":
    unittest.main()
