"""HTML helpers for marketing News articles."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Optional

import markdown

from app.utils.pdf_utils import read_pdf_markdown_from_bytes

_ARTICLE_BODY_MARKER = '<div class="news-article-body">'


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


def _absolute_asset_url(path: str, base_url: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    base = base_url.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def wrap_article_html(
    *,
    title: str,
    author: str,
    body_html: str,
    published_at: Optional[datetime] = None,
    summary: Optional[str] = None,
    featured_image: Optional[str] = None,
    canonical_url: Optional[str] = None,
) -> str:
    published_label = _format_published_date(published_at)
    meta_bits = [f'<span class="news-meta-author">By {html.escape(author)}</span>']
    if published_label:
        meta_bits.append(
            f'<span class="news-meta-date">{html.escape(published_label)}</span>'
        )
    meta_html = "\n          ".join(meta_bits)
    description = html.escape(summary or title)

    og_tags = ""
    if featured_image:
        from app.core.config import settings

        base_url = (getattr(settings, "PUBLIC_WEBSITE_URL", None) or "").strip()
        if not base_url:
            base_url = "https://www.saimonsoft.com"
        og_image = html.escape(_absolute_asset_url(featured_image, base_url))
        og_tags = f"""
    <meta property="og:type" content="article" />
    <meta property="og:title" content="{html.escape(title)}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:image" content="{og_image}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{html.escape(title)}" />
    <meta name="twitter:description" content="{description}" />
    <meta name="twitter:image" content="{og_image}" />"""
        if canonical_url:
            og_tags += f'\n    <meta property="og:url" content="{html.escape(canonical_url)}" />'

    featured_html = ""
    if featured_image:
        featured_html = f"""
        <figure class="news-article-featured">
          <img src="{html.escape(featured_image)}" alt="{html.escape(title)}" loading="eager" />
        </figure>"""

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(title)} | sAImon Software News</title>
    <meta name="description" content="{description}" />{og_tags}
    <link rel="icon" href="/website/images/1.png" type="image/png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap"
      rel="stylesheet"
    />
    <link rel="stylesheet" href="/website/site.css" />
    <link rel="stylesheet" href="/website/news/news.css" />
  </head>
  <body>
    <nav class="site-nav" aria-label="Primary">
      <a class="nav-brand" href="/cover-letters">
        <span class="nav-product">Job Cover Letters – AI</span>
        <span class="nav-company">by sAImon Software</span>
      </a>
      <div class="nav-actions">
        <a class="nav-link-quiet" href="/">sAImon Software</a>
        <a class="btn btn-primary" href="/cover-letters">Try for free</a>
      </div>
    </nav>

    <div class="page-shell">
      <div class="page-card news-article">
        <a class="news-back-link" href="/news">&larr; Back to News</a>
        <div class="news-meta">
          {meta_html}
        </div>
        <h1 class="news-article-title">{html.escape(title)}</h1>{featured_html}
        <div class="news-article-body">
        {body_html}
        </div>
      </div>
    </div>

    <footer class="site-footer">
      <div class="footer-links">
        <a href="/cover-letters">Cover Letters</a>
        <a href="/">sAImon Software</a>
        <a href="/support.html">Support</a>
        <a href="/news">News</a>
      </div>
      <div class="footer-legal">
        <a href="/website/docs/terms-of-service.html">Terms</a>
        ·
        <a href="/website/docs/privacy-policy.html">Privacy</a>
        ·
        <a href="/delete-account.html">Delete account</a>
      </div>
      <p class="copyright">&copy; 2026 sAImon Software. All rights reserved.</p>
    </footer>
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
