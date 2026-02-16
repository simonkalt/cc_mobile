# Frontend: Cover Letter & Print Preview — Required Logic and Endpoints

This document is the **single reference** for the frontend to implement the required cover letter flow and print preview. The backend uses a **docx-only** contract: the API does not send HTML; all formatting (bold, color, bullets, fonts, sizes) lives in the **.docx** only.

---

## Required flow (high level)

1. **Generate** → Call generation API; receive **docxBase64** (the .docx) and optionally **content** (plain text). No HTML, no markdown.
2. **Display / Edit** → Use the **.docx** as the only formatted artifact: show it via a DOCX viewer or by converting to PDF (docx-to-pdf); let the user edit the .docx (in-app editor or download → edit in Word → re-upload).
3. **Print preview** → Send the **current .docx** to **POST /api/files/docx-to-pdf**; display or download the returned PDF.
4. **Save** → Send the (possibly edited) .docx to **POST /api/files/save-cover-letter** with `contentType` = docx.

---

## 1. Generate cover letter (get the .docx)

**Endpoints (use one):**

- **POST** `/api/job-info` — resume as S3 key, base64 PDF, or file reference.
- **POST** `/api/cover-letter/generate-with-text-resume` — resume as pasted plain text.

**Auth:** Bearer token (JWT) in `Authorization` header.

**Request body (typical fields):**  
`llm`, `date_input`, `company_name`, `hiring_manager`, `ad_source`, `resume` (or `resume_text` for the text-resume endpoint), `jd`, `additional_instructions`, `tone`, `address`, `phone_number`, `user_id`, `user_email`.

**Response (200):**

```json
{
  "docxBase64": "<base64-encoded .docx bytes>",
  "docxTemplateHints": { "version": "1.0", "sourceFormat": "markdown", "outputFormat": "docx", "styleProfile": "cover_letter_standard", "fields": { ... }, "styleInstructions": "...", "style": {} },
  "content": "Optional plain text of the letter (for search/fallback only)."
}
```

The API returns **docx only**: no `html`, no `markdown`. Optional `content` is plain text. All formatting is in the **.docx**.

**Required frontend logic (docx-only):**

- Treat **`docxBase64`** as the single source of truth for the letter and its formatting.
  - Decode base64 to binary and use as the **current cover letter .docx** (e.g. for a DOCX viewer, download, or to send to docx-to-pdf for print preview).
  - Do **not** render any HTML; there is no `html` field. To show the letter on screen, either:
    - Use a **DOCX viewer** component (e.g. docx-preview, or similar), or
    - Call **POST /api/files/docx-to-pdf** with this .docx and display the returned PDF as the “preview”.
  - Editing: use a DOCX-capable editor or “Download .docx → edit in Word → re-upload”. Use the same .docx for print preview and save.
- **`content`** (optional) is plain text only; use for search or fallback. The formatted view is always the .docx (or the PDF from it).

---

## 2. Edit the .docx

- The **source of truth** for the letter is the **.docx** (the one from `docxBase64` or the user’s edited version).
- Let the user edit that .docx in your app (e.g. DOCX-capable editor or “open in Word” and re-upload).
- After edits, the “current” document is the updated .docx file (in memory or on disk). Use that for **Print preview** and **Save**.

No API call in this step; logic is entirely on the client.

---

## 3. Print preview (PDF of the .docx)

**Endpoint:** **POST** `/api/files/docx-to-pdf`

**Auth:** Bearer token (JWT).

**Request:** `multipart/form-data` with one file part.

| Part name | Type | Required | Description        |
|-----------|------|----------|--------------------|
| `file`    | file | ✅ Yes   | The .docx document. |

**Response (200):**

```json
{
  "success": true,
  "pdfBase64": "<base64-encoded PDF>",
  "message": "PDF generated from .docx successfully"
}
```

**Required frontend logic:**

- For “Print preview”, use the **current .docx** (the one from generation or the user’s edited version).
- Call **POST /api/files/docx-to-pdf** with that .docx as the `file` part.
- Decode `pdfBase64` and display or download the PDF.

**Important:** Do **not** use **POST /api/files/print-preview-pdf** (HTML-based) for the primary flow. The required path is: **.docx → docx-to-pdf → PDF**. See also [DOCX_TO_PDF_API.md](./DOCX_TO_PDF_API.md).

**If you get "Error generating PDF for print preview: Error: not Found" (404):** (1) URL must be exactly **`/api/files/docx-to-pdf`** (with the `/api/files/` prefix). See [PRINT_PREVIEW_PDF_API.md](./PRINT_PREVIEW_PDF_API.md) troubleshooting for “Not Found / Falling back to HTML preview”.

---

## 4. Save cover letter

**Endpoint:** **POST** `/api/files/save-cover-letter`

**Auth:** Bearer token (JWT).

**Request body (JSON):**

| Field              | Type   | Required | Description                                                                 |
|--------------------|--------|----------|-----------------------------------------------------------------------------|
| `coverLetterContent` | string | ✅ Yes   | Base64-encoded file content (the .docx bytes when saving as docx).         |
| `fileName`         | string | ❌ No    | Suggested filename (e.g. `cover_letter_CompanyName.docx`).                 |
| `contentType`      | string | ✅ Yes   | For .docx use: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. |
| `user_id`          | string | ❌ No*   | User ID. *Required if `user_email` not sent.                                |
| `user_email`       | string | ❌ No*   | User email. *Required if `user_id` not sent.                               |

**Required frontend logic:**

- When saving the current letter as .docx: encode the .docx bytes as base64, set `contentType` to the docx MIME type above, and send to **POST /api/files/save-cover-letter**.
- Optionally set `fileName` (e.g. with company name and date).

See [COVER_LETTER_MANAGEMENT_API.md](./COVER_LETTER_MANAGEMENT_API.md) for more detail and list/download endpoints.

---

## Quick reference: endpoints

| Action          | Method | Endpoint                                      | Key request                         | Key response              |
|-----------------|--------|-----------------------------------------------|-------------------------------------|---------------------------|
| Generate letter | POST   | `/api/job-info` or `/api/cover-letter/generate-with-text-resume` | JSON body (job info, resume, etc.) | `docxBase64`, `docxTemplateHints`, optional `content` (no html/markdown) |
| Print preview   | POST   | `/api/files/docx-to-pdf`                      | `multipart/form-data`, part `file` = .docx | `pdfBase64`               |
| Save letter     | POST   | `/api/files/save-cover-letter`                | JSON: `coverLetterContent` (base64), `contentType` (docx) | `key`, `fileName`, `success` |
| List saved      | GET    | `/api/cover-letters/list`                     | Query: `user_id` or `user_email`    | `files[]`                 |

All of these require **Authorization: Bearer &lt;JWT&gt;** (and usually `user_id` or `user_email` where applicable).

---

## Related docs

- [COVER_LETTER_DOCX_FLOW.md](./COVER_LETTER_DOCX_FLOW.md) — Backend flow and rationale (DOCX as source of truth).
- [DOCX_TO_PDF_API.md](./DOCX_TO_PDF_API.md) — docx-to-pdf request/response and examples (React Native / Expo).
- [PRINT_PREVIEW_PDF_API.md](./PRINT_PREVIEW_PDF_API.md) — Print-preview troubleshooting (404, correct paths).
- [COVER_LETTER_MANAGEMENT_API.md](./COVER_LETTER_MANAGEMENT_API.md) — List, download, delete saved cover letters.
