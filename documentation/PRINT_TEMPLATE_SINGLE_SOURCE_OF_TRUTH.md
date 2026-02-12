# Print Template API — Single Source of Truth for HTML/PDF

This document describes the **Print Template** endpoint and how to use it as a single source of truth so the in-app display and PDF match exactly.

## Problem

Previously, HTML could look correct in the app’s viewer but produce different spacing/line breaks in the PDF (or vice versa). This happened because:

1. **Different normalization** for display vs PDF
2. **Different wrappers** — the app viewer didn’t use the same CSS as the PDF engine
3. **Different engines** — Playwright (Chromium) vs WeasyPrint can render slightly differently

## Solution

**POST** `/api/files/print-template` returns the **exact** HTML document used for PDF generation. Use it for:

- **Match PDF view**: Render the returned HTML in a WebView; it will match the PDF.
- **Print Preview**: Same HTML as the PDF engine receives.
- **Testing**: Verify layout without generating a PDF.

---

## Endpoint

**POST** `/api/files/print-template`

**Auth:** Bearer token (same as other `/api/files` endpoints)

### Request Body

```json
{
  "printProperties": {
    "margins": { "top": 1.0, "right": 0.75, "bottom": 0.25, "left": 0.75 },
    "fontFamily": "Georgia",
    "fontSize": 11,
    "lineHeight": 1.15,
    "pageSize": { "width": 8.5, "height": 11.0 },
    "useDefaultFonts": false
  },
  "htmlContent": "<div>February 12, 2026<br /><br />Simon Kaltgrad<br />..."
}
```

| Field             | Type   | Required | Description                                                                                           |
| ----------------- | ------ | -------- | ----------------------------------------------------------------------------------------------------- |
| `printProperties` | object | ✅ Yes   | Same structure as `print-preview-pdf` (margins required)                                              |
| `htmlContent`     | string | ❌ No    | Letter HTML. If provided, it is normalized and injected. If omitted, the response uses a placeholder. |

### Response

**With `htmlContent`:**

```json
{
  "html": "<!DOCTYPE html>\n<html>\n<head>...</head>\n<body>\n<div class=\"print-content\">normalized content...</div>\n</body>\n</html>"
}
```

**Without `htmlContent`:**

```json
{
  "html": "<!DOCTYPE html>\n<html>...<div class=\"print-content\">{{LETTER_CONTENT}}</div>...</html>",
  "contentPlaceholder": "{{LETTER_CONTENT}}"
}
```

| Field                | Description                                                                             |
| -------------------- | --------------------------------------------------------------------------------------- |
| `html`               | Full HTML document. Render in WebView for “Match PDF” view.                             |
| `contentPlaceholder` | Present only when `htmlContent` was omitted. Replace this with your normalized content. |

---

## Usage

### 1. Match PDF / Print Preview in-app

To show how the letter will look in the PDF:

```
1. User edits letter (or uses generated HTML).
2. Call POST /api/files/print-template with printProperties + htmlContent.
3. Render response.html in a WebView.
4. Layout and spacing will match the PDF.
```

### 2. Generate PDF

Use the same flow as today:

```
1. Call POST /api/files/print-preview-pdf with htmlContent + printProperties.
2. Backend uses the same template and normalization as print-template.
```

### 3. Template only (frontend injects content)

```
1. Call POST /api/files/print-template with printProperties only.
2. Replace {{LETTER_CONTENT}} in response.html with your content.
3. Content must be normalized first (see Normalization section).
```

---

## Normalization (Single Pipeline)

The backend uses a single normalization pipeline for both `print-template` and `print-preview-pdf`:

1. **Merge `</p><p>` → `<br />`** — avoid paragraph margins between every line
2. **Collapse redundant `<br />`** — no double breaks from editor output
3. **Break before "Sincerely,"** — ensure a line break
4. **Strip newlines adjacent to `<br />`** — avoid double breaks
5. **Convert literal `\n` → `<br />`** — single `\n` = one break; `\n\n` = blank line

When you send `htmlContent` to `print-template`, the backend applies this normalization before wrapping. **Do not normalize on the frontend** — let the backend do it so display and PDF stay in sync.

---

## CSS Applied (Print Template)

The template applies:

- **@page**: Size and margins from `printProperties`
- **body**: Font family, size, line-height from `printProperties` (unless `useDefaultFonts`)
- **`.print-content *`**: `margin: 0 !important; padding: 0 !important;`
- **`.print-content br`**: `display: block; margin-top: 0.12em !important;` (single-line break)
- **`.print-content p`**: `margin: 0 !important; padding: 0 !important;`

Use the same `printProperties` as for `print-preview-pdf` for consistent output.

---

## PDF Engine

- **Primary**: Playwright (Chromium) — the template matches this.
- **Fallback**: WeasyPrint — similar wrapper; minor differences possible.
- **Note**: When `PRINT_PREVIEW_USE_WEASYPRINT_ONLY=true`, PDF uses WeasyPrint; the template still reflects the canonical Playwright layout for consistency.

---

## Summary for Frontend

1. For **Match PDF** or **Print Preview** view:  
   Call `POST /api/files/print-template` with `printProperties` and `htmlContent`, then render `response.html` in a WebView.

2. Use the **same `printProperties`** as for `print-preview-pdf`.

3. **Do not** re-normalize on the frontend — the backend handles it.

4. For PDF: keep using `POST /api/files/print-preview-pdf`; it uses the same template and normalization.
