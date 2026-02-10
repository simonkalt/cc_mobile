"""
HTML normalization for cover letter content.

- html_p_to_br: minimal treatment for client response — only replace <p>/</p> with <br />.
- Other functions used for PDF generation or legacy paths.
"""

import re


def html_p_to_br(html_content: str) -> str:
    """
    Only replace </p> and <p...> with <br />. No other changes.
    Use this for HTML returned to the client.
    """
    if not html_content or not html_content.strip():
        return html_content
    html_content = re.sub(r"</p>\s*", "<br />", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"<p(\s[^>]*)?>\s*", "<br />", html_content, flags=re.IGNORECASE)
    return html_content


def normalize_cover_letter_html(html_content: str) -> str:
    """
    Normalize cover letter HTML to a single format suitable for WebView and PDF.

    - Replaces </p> and <p...> with <br /> so paragraph boundaries become <br /><br />.
      This preserves the structure from the system prompt (e.g. <<Date>><br><br><<Name>>).
    - Normalizes all <br> variants to <br /> (does not collapse runs — double <br>s stay).
    - Ensures break after "Dear [Name]," and before "Sincerely," when missing.
    """
    if not html_content or not html_content.strip():
        return html_content
    # </p> and <p...> → <br /> so </p><p> becomes <br /><br /> (preserves prompt's double breaks)
    html_content = re.sub(r"</p>\s*", "<br />", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"<p(\s[^>]*)?>\s*", "<br />", html_content, flags=re.IGNORECASE)
    # Normalize <br> variants to <br /> (do not collapse — keep double <br /><br /> from prompt)
    html_content = re.sub(r"<br\s*/?\s*>|</?\s*br\s*>", "<br />", html_content, flags=re.IGNORECASE)
    # Ensure break after "Dear [Name]," when body runs on (only if no break already)
    html_content = re.sub(
        r"(Dear\s+[^<]+,)(?!\s*<br)(\s*)(</p>|<br\s*/?\s*>|\s*[A-Z])",
        r"\1<br />\2\3",
        html_content,
        flags=re.IGNORECASE,
    )
    # Ensure break before "Sincerely,"
    html_content = re.sub(
        r"([.>])\s*Sincerely\s*,",
        r"\1<br />Sincerely,",
        html_content,
        flags=re.IGNORECASE,
    )
    return html_content


def newlines_to_br(html_content: str, collapse: bool = False) -> str:
    """
    Convert literal newlines in HTML to <br />.

    - collapse=False: each \\n becomes <br />, so \\n\\n → <br /><br /> (preserves paragraph breaks).
    - collapse=True: any run of \\r/\\n becomes one \\n, then one <br /> (legacy behavior).
    """
    if not html_content or ("\n" not in html_content and "\r" not in html_content):
        return html_content
    html_content = html_content.replace("\r", "\n")
    if collapse:
        html_content = re.sub(r"\n+", "\n", html_content)
    return html_content.replace("\n", "<br />")


def normalize_newlines_in_text_nodes(html_content: str, collapse: bool = False) -> str:
    """
    Convert literal newlines to <br /> only inside text (outside tags), so attributes are not broken.

    Preserves paragraph breaks when collapse=False (\\n\\n → <br /><br />).
    """
    if not html_content or ("\n" not in html_content and "\r" not in html_content):
        return html_content
    parts = re.split(r"(<[^>]*>)", html_content)
    result = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            result.append(part)
        else:
            normalized = part.replace("\r", "\n")
            if collapse:
                normalized = re.sub(r"\n+", "\n", normalized)
            result.append(normalized.replace("\n", "<br />"))
    return "".join(result)


def _strip_html(text: str) -> str:
    """Remove HTML tags for content-based checks."""
    return re.sub(r"<[^>]+>", "", text).strip()


def enforce_cover_letter_line_breaks(html_content: str) -> str:
    """
    Post-process HTML so line breaks match the template: single <br /> within blocks,
    double <br /><br /> only between sections (after Date, contact, Company, Re:, Dear,
    Sincerely). Fixes LLM output that uses two breaks between every line.
    """
    if not html_content or not html_content.strip():
        return html_content
    # Normalize br to <br /> then collapse every run of 2+ <br /> to single (uniform single-break doc)
    html_content = re.sub(r"<br\s*/?\s*>|</?\s*br\s*>", "<br />", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"(<br />)(?:\s*<br />)*", r"\1", html_content)
    # Split into segments (lines); drop empty so we have content-only list
    segments = [
        s for s in re.split(r"<br\s*/?\s*>", html_content, flags=re.IGNORECASE) if s.strip()
    ]
    if not segments:
        return html_content

    # Where to add double break after this segment (section boundaries)
    def add_double_after(i: int) -> bool:
        if i < 0 or i >= len(segments):
            return False
        text = _strip_html(segments[i])
        if not text:
            return False
        # First segment = date
        if i == 0:
            return True
        # Contact block end: line contains " | " and "@"
        if " | " in text and ("@" in text or "&#64;" in text.lower()):
            return True
        # Company: next segment starts with "Re:"
        if i + 1 < len(segments):
            next_text = _strip_html(segments[i + 1])
            if next_text.startswith("Re:") or next_text.lower().startswith("re:"):
                return True
        # Re: line
        if text.startswith("Re:") or text.lower().startswith("re:"):
            return True
        # Salutation
        if text.strip().lower().startswith("dear "):
            return True
        # Closing
        if re.match(r"^\s*Sincerely\s*,?\s*$", text, re.IGNORECASE):
            return True
        return False

    out = []
    for i, seg in enumerate(segments):
        out.append(seg)
        if i < len(segments) - 1:
            out.append("<br /><br />" if add_double_after(i) else "<br />")
    return "".join(out)


def to_canonical_cover_letter_html(html_content: str) -> str:
    """
    Full normalization: structure (p→br, Dear/Sincerely) then newlines→br without collapsing,
    then post-process to enforce template single/double line breaks.
    Use this for both API response (WebView) and before sending HTML to PDF.
    """
    html_content = normalize_cover_letter_html(html_content)
    html_content = newlines_to_br(html_content, collapse=False)
    # Collapse multiple spaces to one so we don't get wide gaps
    html_content = re.sub(r" +", " ", html_content)
    html_content = enforce_cover_letter_line_breaks(html_content)
    return html_content
