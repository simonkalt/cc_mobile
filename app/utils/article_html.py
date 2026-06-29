"""HTML helpers for marketing News articles."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Optional

import markdown

from app.utils.pdf_utils import read_pdf_markdown_from_bytes

_ARTICLE_BODY_MARKER = '<div class="news-article-body">'
_FOOTER_LINKS = """
          <a href="/">Home</a>
          <a href="/website/docs/terms-of-service.html">Terms of Service</a>
          <a href="/website/docs/privacy-policy.html">Privacy Policy</a>
          <a href="/delete-account.html">Delete account</a>
          <a href="/support.html">Support</a>
          <a href="/news">News</a>
"""


def slug_from_title(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "article"


def _format_published_date(published_at: Optional[datetime]) -> str:
    if not published_at:
        return ""
    return published_at.strftime("%B %d, %Y")


def _paragraphs_to_html(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    parts: list[str] = []
    for block in blocks:
        if block.startswith("[Screenshot Placeholder:"):
            label = block.strip("[]")
            parts.append(
                f'<div class="news-screenshot-placeholder">{html.escape(label)}</div>'
            )
            continue
        if block.startswith("### "):
            parts.append(f"<h3>{html.escape(block[4:].strip())}</h3>")
        elif block.startswith("## "):
            parts.append(f"<h2>{html.escape(block[3:].strip())}</h2>")
        elif block.startswith("# "):
            parts.append(f"<h2>{html.escape(block[2:].strip())}</h2>")
        elif block.startswith("- "):
            items = [
                f"<li>{html.escape(line[2:].strip())}</li>"
                for line in block.splitlines()
                if line.strip().startswith("- ")
            ]
            parts.append("<ul>" + "".join(items) + "</ul>")
        else:
            parts.append(f"<p>{html.escape(block)}</p>")
    return "\n        ".join(parts)


def extract_body_from_html(full_html: str) -> str:
    """Return inner article body from a full page or raw fragment."""
    marker = _ARTICLE_BODY_MARKER
    start = full_html.find(marker)
    if start == -1:
        return full_html.strip()
    start += len(marker)
    end = full_html.find("</div>", start)
    if end == -1:
        return full_html[start:].strip()
    return full_html[start:end].strip()


def wrap_article_html(
    *,
    title: str,
    author: str,
    body_html: str,
    published_at: Optional[datetime] = None,
    summary: Optional[str] = None,
) -> str:
    published_label = _format_published_date(published_at)
    meta_bits = [f'<span class="news-meta-author">By {html.escape(author)}</span>']
    if published_label:
        meta_bits.append(
            f'<span class="news-meta-date">{html.escape(published_label)}</span>'
        )
    meta_html = "\n          ".join(meta_bits)
    description = html.escape(summary or title)

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(title)} | sAImon Software News</title>
    <meta name="description" content="{description}" />
    <link rel="icon" href="/website/images/1.png" type="image/png" />
    <link rel="stylesheet" href="/website/styles.css" />
    <link rel="stylesheet" href="/website/news/news.css" />
  </head>
  <body>
    <div class="container">
      <header>
        <h1 class="ai-logo-container">
          s<img src="/website/images/ai-hero.gif" alt="AI" class="ai-logo" />mon
          Software
        </h1>
        <p class="tagline">AI-Powered Solutions for Your Career</p>
      </header>

      <div class="main-content news-article">
        <a class="news-back-link" href="/news">&larr; Back to News</a>
        <div class="news-meta">{meta_html}</div>
        <h2 class="news-article-title">{html.escape(title)}</h2>
        <div class="news-article-body">
        {body_html}
        </div>
      </div>

      <footer>
        <div class="footer-links">
          <a href="/">Home</a>
          <a href="/website/docs/terms-of-service.html">Terms of Service</a>
          <a href="/website/docs/privacy-policy.html">Privacy Policy</a>
          <a href="/delete-account.html">Delete account</a>
          <a href="/support.html">Support</a>
          <a href="/news">News</a>
        </div>
        <p class="copyright">
          &copy; 2024 sAImon Software. All rights reserved.
        </p>
      </footer>
    </div>
  </body>
</html>
"""


def markdown_to_html_body(markdown_text: str) -> str:
    return markdown.markdown(markdown_text, extensions=["extra", "nl2br"])


def pdf_bytes_to_html_body(pdf_bytes: bytes) -> str:
    md = read_pdf_markdown_from_bytes(pdf_bytes)
    return markdown_to_html_body(md)


def plain_text_to_html_body(text: str) -> str:
    """Convert plain/markdown-ish article draft text to HTML body fragments."""
    if "<p>" in text or "<h" in text:
        return extract_body_from_html(text)
    return _paragraphs_to_html(text)
