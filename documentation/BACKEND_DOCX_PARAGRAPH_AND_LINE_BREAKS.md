# Backend: .docx Paragraph and Line Break Requirements

This document tells the **backend** how to generate cover-letter .docx files so **paragraph and line breaks display correctly** in the mobile app (and in Word / PDF). The app uses only `docxBase64` for display; it does not render from `content`. Line breaks on screen come entirely from the structure inside the .docx.

---

## What we observed on the client

- The app displays the letter via a DOCX editor that converts the .docx to HTML (ProseMirror).
- When we inspected the rendered DOM, we saw **one** `<p>` element for the whole letter body and **25** `<br>` elements inside it — i.e. either:
  - The .docx had only one Word paragraph (`<w:p>`) for the body and many `<w:br/>`, or
  - The editor library merged multiple `<w:p>` into one `<p>` with `<br>`.
- For consistent behavior across Word, PDF (docx-to-pdf), and the in-app editor, the backend should emit a **clear, standard structure**: **one `<w:p>` per logical paragraph**.

---

## Required .docx structure (OOXML)

### 1. One `<w:p>` per paragraph (required)

- **Each logical paragraph** in the letter body (salutation, each body paragraph, closing, signature block lines, etc.) must be a **separate** `<w:p>` element in `word/document.xml`.
- **Do not** put the entire letter body in a single `<w:p>` with newlines or `<w:br/>` between paragraphs. Use a new `<w:p>` for each paragraph.

**Why:** Many docx consumers (including the in-app editor) map one `<w:p>` to one HTML `<p>`. If the backend emits one long `<w:p>`, the client may show a single block with only soft line breaks (`<br>`), which is harder to style and can look wrong.

### 2. Line breaks within a paragraph (optional)

- For a **soft line break** inside a single paragraph (e.g. address line 1, line 2, then blank line), use `<w:br/>` inside a `<w:r>` run.
- Example: two address lines in one “paragraph” (one `<w:p>`) with a line break between them:

```xml
<w:p>
  <w:r><w:t>123 Main Street</w:t></w:r>
  <w:r><w:br/></w:r>
  <w:r><w:t>City, State ZIP</w:t></w:r>
</w:p>
```

### 3. Empty line between paragraphs

- To get a blank line **between** two paragraphs, use **two** `<w:p>` elements: one with no text (or only whitespace) and one with the next paragraph.
- Example: blank line then “Dear Hiring Manager”:

```xml
<w:p><w:r><w:t></w:t></w:r></w:p>
<w:p>
  <w:r><w:t>Dear Hiring Manager,</w:t></w:r>
</w:p>
```

- Alternatively, use paragraph spacing (e.g. `<w:pPr><w:spacing w:after="120"/></w:pPr>`) so a single empty `<w:p>` or normal `<w:p>` elements have visible space; the important part is still **one `<w:p>` per logical paragraph**.

---

## Minimal OOXML example (body only)

```xml
<w:body>
  <!-- Applicant name (one paragraph) -->
  <w:p>
    <w:r><w:t>Jane Doe</w:t></w:r>
  </w:p>
  <!-- Address: one paragraph with line breaks -->
  <w:p>
    <w:r><w:t>123 Main Street</w:t></w:r>
    <w:r><w:br/></w:r>
    <w:r><w:t>City, State 12345</w:t></w:r>
  </w:p>
  <!-- Blank line -->
  <w:p><w:r><w:t></w:t></w:r></w:p>
  <!-- Salutation -->
  <w:p>
    <w:r><w:t>Dear Hiring Manager,</w:t></w:r>
  </w:p>
  <!-- Body paragraph 1 -->
  <w:p>
    <w:r><w:t>I am writing to apply for the Software Engineer role...</w:t></w:r>
  </w:p>
  <!-- Body paragraph 2 -->
  <w:p>
    <w:r><w:t>My experience at Acme Corp...</w:t></w:r>
  </w:p>
  <!-- Closing -->
  <w:p>
    <w:r><w:t>Sincerely,</w:t></w:r>
  </w:p>
  <w:p>
    <w:r><w:t>Jane Doe</w:t></w:r>
  </w:p>
  <w:sectPr>...</w:sectPr>
</w:body>
```

---

## How to verify your .docx

1. Save the generated .docx to disk (from your generation endpoint or a test script).
2. Unzip it (e.g. `unzip letter.docx -d letter_extracted`).
3. Open `word/document.xml` and look at `<w:body>`.
4. Count `<w:p>` elements that belong to the letter body (ignore headers/footers if present). You should see **multiple** `<w:p>` for a normal letter (e.g. name, address, blank, salutation, several body paragraphs, closing, signature).
5. If you see only **one** `<w:p>` containing the whole letter (with or without `<w:br/>`), adjust your docx generation so that each logical paragraph is its own `<w:p>`.

---

## If you use python-docx (or similar)

- **Add paragraphs with `document.add_paragraph()` (or equivalent)** for each logical paragraph. Do **not** put the whole body in one paragraph with newlines and then expect the library to split; ensure you call add_paragraph once per paragraph.
- For a blank line between paragraphs, add an empty paragraph or use paragraph spacing (e.g. `paragraph.paragraph_format.space_after = Pt(12)`).
- For soft line breaks inside one paragraph, use the library’s “add line break” / “add_br” API so it emits `<w:br/>` inside the run.

---

## Summary for backend

| Requirement                    | Action                                                                                                   |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Paragraph breaks               | Emit **one `<w:p>` per logical paragraph** in the letter body. Do not put the whole body in one `<w:p>`. |
| Blank lines                    | Use an empty `<w:p>` or spacing; keep “one paragraph per logical block.”                                 |
| Line breaks inside a paragraph | Use `<w:br/>` inside a run where you need a soft break (e.g. address lines).                             |
| Verify                         | Unzip the .docx, inspect `word/document.xml`, and confirm multiple `<w:p>` in the body.                  |

The frontend uses only `docxBase64` for display and does not use `content` for the letter body. Ensuring the .docx has this structure will fix missing paragraph and line breaks in the app (and in Word and in docx-to-pdf output).

---

## Optional: Style tags in plain-text content (revertable)

When building from **plain-text** `content`, the pipeline supports optional tags so the LLM can set color, font size, and font family without HTML:

- `[color:#RRGGBB]text[/color]` — e.g. `[color:#1f4e79]Company Name[/color]`
- `[size:Npt]text[/size]` — e.g. `[size:14pt]heading[/size]`
- `[font:Name]text[/font]` — e.g. `[font:Arial]text[/font]`

Bold/italic remain `**text**` and `*text*`. Implemented in `app/utils/docx_generator.py`: `_parse_style_segments`, `_bold_italic_to_runs`, and `_plain_line_to_runs` (which composes them).

**To revert:** Remove `_parse_style_segments` and `_bold_italic_to_runs`; restore `_plain_line_to_runs` to a single loop that only parses `**`/`*`/`__`/`_` and does not call `_parse_style_segments`. Remove the style-tag sentence from `system_prompt.json`.
