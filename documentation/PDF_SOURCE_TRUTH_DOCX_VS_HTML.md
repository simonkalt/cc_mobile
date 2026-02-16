# PDF generation: DOCX vs HTML pipeline

## Current behavior: **no direct DOCX→PDF**

All backend PDF generation uses the **HTML/Markdown pipeline**, not the .docx file:

| Endpoint | Input | How PDF is made |
|----------|--------|------------------|
| `POST /api/files/print-preview-pdf` | `htmlContent` or `markdownContent` | HTML → Playwright, WeasyPrint, or Nutrient.io **(HTML API)**. Our server wraps content in its own CSS (margins, fonts, line-height). |
| `POST /api/files/generate-pdf` | `markdownContent` | Markdown → HTML → WeasyPrint. |

- **Nutrient.io** is called with **HTML** (`files: { "html": ... }`), not with a .docx.
- There is **no** endpoint that accepts a .docx file and converts it to PDF on the server.

So when the source of truth is a **.docx** (e.g. from Syncfusion/Nutrient Document Editor in a WebView):

- If the app sends **HTML** (or text/markdown) derived from that .docx to our API, we render that HTML with **our** template and CSS. The resulting PDF does **not** use the .docx layout; it uses our fonts, margins, and line breaks → **formatting differs from the .docx**.
- The .docx “looks great” in the editor because the editor renders the .docx natively. The PDF “looks different” because it comes from our HTML pipeline, not from the .docx.

## How to get PDF that matches the .docx

### Option A: **Client-side PDF from the DOCX editor (recommended)**

Use the editor’s own export so PDF is generated from the same document as the .docx:

- **Syncfusion Document Editor**: `documentEditor.exportAsPdf()` (or equivalent) in the WebView. No backend call for this PDF.
- **Nutrient Document Authoring**: use their PDF export from the same document.

Then:

- Use **our** PDF API only for legacy flows where the source is HTML/markdown (e.g. “Match PDF” or old print preview).
- For the **docx-based** cover letter, **do not** send HTML/markdown to `print-preview-pdf`; export PDF in the client from the docx editor and use that for share/print.

Result: one source of truth (.docx), one export path (editor → PDF) → **no formatting mismatch**.

### Option B: **Backend DOCX→PDF** ✅ Implemented

**POST /api/files/docx-to-pdf** accepts a .docx file (multipart form field `file`) and returns PDF as base64. Conversion uses **LibreOffice headless** (`soffice --headless --convert-to pdf`) on the server so the PDF matches the .docx layout.

- **Request:** `multipart/form-data` with `file` = the .docx file.
- **Response:** `{ "success": true, "pdfBase64": "...", "message": "..." }`.
- **Auth:** Bearer JWT required (same as other `/api/files` routes).
- **Server:** LibreOffice must be installed (e.g. `soffice` on PATH); otherwise the API returns 503.

See **[DOCX_TO_PDF_API.md](./DOCX_TO_PDF_API.md)** for frontend usage, examples, and cURL.

## Summary

| Question | Answer |
|----------|--------|
| Are we using **direct .docx→PDF** for the cover letter? | **No.** We only have HTML/markdown→PDF (Playwright/WeasyPrint/Nutrient HTML). |
| Why does the .docx look great but the PDF different? | The PDF is produced from our **HTML pipeline** (our template + CSS), not from the .docx. |
| How to get PDF that matches the .docx? | Prefer **client-side PDF export** from the docx editor; or add a **backend docx→PDF** endpoint and send the .docx there. |
