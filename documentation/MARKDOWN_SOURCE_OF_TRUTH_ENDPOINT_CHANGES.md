# Cover Letter: HTML as Source of Truth — Endpoint Reference for Frontend

This document describes the **current** API contract: **HTML is the source of truth** for display and Print Preview. The backend returns both `markdown` and `html` from generation; the frontend uses **`html`** for the editor and sends **`htmlContent`** for Print Preview (or `markdownContent` for backward compatibility).

---

## 1. Summary

| Area                    | Contract                                                                     |
| ----------------------- | ---------------------------------------------------------------------------- |
| **Canonical format**    | **HTML** for display and Print Preview                                       |
| **Generation response** | `{ markdown, html, printProperties }` — use **`html`** for the editor        |
| **Print Preview PDF**   | Request: **`htmlContent`** (preferred) or **`markdownContent`** (accepted)   |
| **Save cover letter**   | Send **`coverLetterContent`** as HTML or markdown; **`contentType`** matches |
| **Display / editor**    | Use returned **`html`** in WebView/rich editor (TenTap, etc.)                |

---

## 2. Cover letter generation

**Endpoints (unchanged):**

- `POST /api/job-info`
- `POST /api/cover-letter/generate-with-text-resume`
- `POST /api/chat` (when body is a job-info request)

**Response shape — NEW contract:**

```json
{
  "markdown": "February 12, 2025\n\nYour Name\n...",
  "html": "<div style=\"font-family: ...\">...</div>",
  "printProperties": {
    "margins": { "top": 0.5, "right": 0.5, "bottom": 0.5, "left": 0.5 },
    "fontFamily": "Calibri",
    "fontSize": 12,
    "lineHeight": 1.15,
    "pageSize": { "width": 8.5, "height": 11.0 },
    "useDefaultFonts": false
  }
}
```

- **`markdown`** (string): **Required.** The cover letter in Markdown. Source of truth for storage, editing, and Print Preview.
- **`printProperties`** (object): **Required.** The user’s font/print settings. Use this when rendering the markdown so fonts, sizes, and layout match the user’s preferences. Same shape as the `printProperties` sent to Print Preview (margins, fontFamily, fontSize, lineHeight, pageSize, useDefaultFonts). Apply these when converting markdown → HTML for display (e.g. wrap in a div with `font-family`, `font-size`, `line-height`, `color: #000` from these values).
- **`html`** (string): **Optional.** Pre-rendered HTML with the user’s font wrapper already applied. Can be used for display; store and edit **markdown** and use **printProperties** for styling.

**Formatting (fonts, sizes, colors):** Standard markdown does **not** support font family, font size, or color. It only supports: **bold** (`**text**`), _italic_ (`*text*`), headings (`#`, `##`, `###`), lists, and links. So:

- For “multiple fonts, sizes, and colors,” the **backend/LLM** should output **markdown structure**: use `##` or `###` for headings (the app will display them larger/different), `**bold**` and `*italic*` for emphasis. The frontend then applies distinct sizes/colors to those elements when rendering markdown → HTML.
- If the backend needs true font/color control (e.g. “Arial 14pt blue”), it can return **`html`** (optional) with inline styles; the frontend can use that for display while still storing **markdown** as source of truth.

**Inline spans in `html` (color, fonts, font sizes):** The API may return **`html`** containing `<span style="...">...</span>` for color, font family, and font size. Allowed style properties: `color:#RRGGBB` (hex), `font-family: Name, fallback`, `font-size: Npt` or `Npx`. Example: `<span style="color:#c00000">red</span>` or `<span style="font-family: Georgia, serif; font-size: 14pt">text</span>`. The backend preserves these spans. Use **`html`** for display in the rich-text editor (e.g. TenTap) so color, font, and size are preserved.

**Frontend actions:**

1. Store and edit the **`markdown`** value.
2. When displaying the letter, use the returned **`html`** for the editor/WebView when the response includes inline spans (color, font, font-size) so formatting is visible; otherwise apply **`printProperties`** to a markdown-rendered view.
3. Use **markdown** when calling Print Preview and Save; send the same **printProperties** (or the user’s current settings) with Print Preview so the PDF matches.

---

## 3. Print Preview PDF

**Endpoint:** `POST /api/files/print-preview-pdf`

**Request body (HTML as source of truth):**

Send **`htmlContent`** (preferred) with the current HTML from the editor. The backend also accepts **`markdownContent`** for backward compatibility.

```json
{
  "htmlContent": "<div style=\"font-family: Calibri;\">February 12, 2025<br /><br />Your Name<br />...</div>",
  "printProperties": {
    "margins": { "top": 0.5, "right": 0.5, "bottom": 0.5, "left": 0.5 },
    "fontFamily": "Times New Roman",
    "fontSize": 12,
    "lineHeight": 1.6,
    "pageSize": { "width": 8.5, "height": 11.0 },
    "useDefaultFonts": false
  },
  "user_id": "optional",
  "user_email": "optional"
}
```

| Field                    | Type   | Required  | Notes                                                                 |
| ------------------------ | ------ | --------- | --------------------------------------------------------------------- |
| **`htmlContent`**        | string | **Yes\*** | Cover letter HTML. Preferred when using HTML as source of truth.      |
| **`markdownContent`**    | string | **Yes\*** | Alternative: markdown. Accepted for backward compatibility.           |
| `printProperties`        | object | Yes       | margins, fontFamily, fontSize, lineHeight, pageSize, useDefaultFonts. |
| `user_id` / `user_email` | string | No        | For logging / user context.                                           |

\* At least one of **`htmlContent`** or **`markdownContent`** is required.

**Response (unchanged):**

```json
{
  "success": true,
  "pdfBase64": "base64-encoded-pdf-string",
  "message": "PDF generated successfully"
}
```

**Frontend actions:**

1. Send **`htmlContent`** (current HTML from the editor) plus **`printProperties`** for Print Preview.
2. If your client still sends **`markdownContent`**, the backend accepts it and converts markdown → PDF.

---

## 4. Save cover letter

**Endpoint:** `POST /api/files/save-cover-letter`

**Request body (preferred for new flow):**

```json
{
  "coverLetterContent": "February 12, 2025\n\nYour Name\n...",
  "contentType": "text/markdown",
  "fileName": "optional_custom_name",
  "user_id": "optional",
  "user_email": "optional"
}
```

| Field                    | Type   | Required | Notes                                                                                                                     |
| ------------------------ | ------ | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| **`coverLetterContent`** | string | Yes      | **Prefer markdown.** The cover letter body. For markdown, use plain UTF-8 text (not base64).                              |
| **`contentType`**        | string | Yes      | Use **`"text/markdown"`** when saving the canonical letter. Server will store as `.md` and `Content-Type: text/markdown`. |
| `fileName`               | string | No       | Base name without extension; server appends `.md` / `.html` / `.pdf` from `contentType`.                                  |
| `user_id` / `user_email` | string | No       | For identifying the user (required in practice for auth).                                                                 |

**Other content types (unchanged):**

- `contentType: "text/html"` — server saves as `.html`. Use only when persisting an HTML export, not as the main letter source.
- `contentType: "application/pdf"` — **`coverLetterContent`** must be **base64-encoded PDF**. Server saves as `.pdf`.

**Frontend actions:**

1. Save the **markdown** version of the letter: `coverLetterContent` = markdown string, `contentType` = `"text/markdown"`.
2. When loading a saved letter for editing or Print Preview, use the stored markdown (and send that same markdown to Print Preview).

---

## 5. Generate PDF (from markdown)

**Endpoint:** `POST /api/files/generate-pdf`

**No change.** This endpoint already takes markdown:

```json
{
  "markdownContent": "...",
  "printProperties": { ... },
  "user_id": "optional",
  "user_email": "optional"
}
```

Use it when generating a PDF directly from markdown (e.g. final export). Same **`printProperties`** shape as Print Preview.

---

## 6. Backward compatibility and migration

- **Generation:** Backend returns **`markdown`**, **`html`**, and **`printProperties`**. Use **`html`** for display (HTML is source of truth).
- **Print Preview:** Send **`htmlContent`** (preferred) or **`markdownContent`**; at least one required.
- **Save:** Backend accepts `contentType: "text/html"` or `"text/markdown"` or `"application/pdf"`.

---

## 7. Quick reference: what to send where

| Action           | Primary field / value                                                    | Endpoint                                                        |
| ---------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------- |
| After generation | Use **`html`** from response for editor (HTML is source of truth)        | N/A (response from job-info / generate-with-text-resume / chat) |
| Print Preview    | **`htmlContent`** (preferred) or **`markdownContent`** + printProperties | `POST /api/files/print-preview-pdf`                             |
| Save letter      | **`coverLetterContent`** = HTML or markdown, **`contentType`** matches   | `POST /api/files/save-cover-letter`                             |
| Generate PDF     | **`markdownContent`** (unchanged)                                        | `POST /api/files/generate-pdf`                                  |

---

## 8. Auth and headers

All endpoints above use the same auth as today (e.g. Bearer token in `Authorization` header). No changes to auth or CORS from this migration.

---

## 9. LLM / generation: making “formatting” visible

When the user asks for “multiple fonts, sizes, and colors” or “format the letter,” **markdown cannot represent font family, size, or color**. The backend/LLM should:

- **Output markdown structure** so the app can show clear hierarchy and emphasis:
  - Use `##` or `###` for section headings (e.g. date block, salutation, closing).
  - Use `**bold**` for names, role titles, or key phrases.
  - Use `*italic*` for light emphasis where appropriate.
- The **frontend** then renders that markdown with distinct sizes and colors for `h1`/`h2`/`h3`, `strong`, and `em`, so the letter looks formatted.
- If the model is instructed only with “format with fonts, sizes, and colors” and returns **plain text** (no `##` or `**`), the app will show it as one uniform block. So the **system or user prompt** should explicitly ask for **markdown** when formatting is requested, e.g.:  
  *“Use markdown: ## for section headings, **bold** for names and key phrases, and *italic* for emphasis so the letter has clear visual hierarchy.”*

---

_Document version: 1.1 — HTML as source of truth for display and Print Preview; markdownContent accepted for backward compatibility._
