# Cover Letter Flow: DOCX as Source of Truth

This document describes the **intended application flow** and how the server supports it.

> **Frontend:** For required logic and endpoints in one place, see **[FRONTEND_COVER_LETTER_AND_PRINT_REQUIREMENTS.md](./FRONTEND_COVER_LETTER_AND_PRINT_REQUIREMENTS.md)**.

---

## Who produces the .docx?

**The user receives a .docx file** with the requested layout and formatting. That file is produced by **our backend**, not by the LLM. LLM APIs (OpenAI, Claude, Gemini, etc.) return **text or JSON**, not binary files like .docx. So the flow is:

1. **LLM** returns structured content (e.g. plain text with newlines, or JSON) that describes the letter and its structure.
2. **Backend** converts that response into a Word document (.docx) with the correct paragraphs, spacing, and list formatting.
3. **User** receives that .docx (e.g. as `docxBase64` in the API response).

The **document** the user gets has all the formatting requested—paragraphs, spacing, bullets—because we build the .docx from the structure the LLM specified.

---

## Templates in the prompt (line-break consistency)

Templates under `templates/{creative,formal,informal}/*.template` are included in the LLM prompt so the model matches the template structure line-for-line (same number of lines and blank lines). This is intended to make paragraph and line breaks more consistent in the generated .docx.

- **Config:** `USE_TEMPLATE_IN_PROMPT` (env: `USE_TEMPLATE_IN_PROMPT`, default `true`).
- **To revert** (omit template from prompt): set `USE_TEMPLATE_IN_PROMPT=false` in the environment or `.env`.

---

## Line breaks missing: debugging

**Confirmed:** The client uses `docxBase64` only and does not render from `content`. If line breaks are still missing in the app, the cause is one of:

### 1. The .docx has no paragraph/line breaks (backend)

The file may be built with one paragraph for the whole body. To verify:

1. Save the received .docx (decode `docxBase64` and write to a file).
2. Unzip it (e.g. `unzip letter.docx -d letter_docx` or rename to `.zip` and extract).
3. Open `word/document.xml` and look at the body:
   - Each paragraph should be a separate `<w:p>…</w:p>`.
   - Line breaks within a paragraph are `<w:br/>`.
   - If the whole letter is inside a single `<w:p>` with one long `<w:t>`, there are no paragraph breaks in the file.

**Fix:** The backend that builds the .docx (`app/utils/docx_generator.py`) must emit one `<w:p>` per paragraph (and `<w:br/>` where line breaks are intended). Plain-text content is split by `\n\n` into paragraphs and by `\n` into runs with line breaks; ensure `_plain_text_to_blocks` and the block→document loop produce separate paragraphs.

### 2. The editor library is dropping them (frontend)

If the .docx has correct structure (multiple `<w:p>` or `<w:br/>`) but the app still shows no breaks, the docx→DOM conversion (e.g. **@eigenpal/docx-js-editor**) may be merging paragraphs. Next step: inspect the WebView DOM (e.g. via remote debugging) and check whether the letter body is a single `<p>` or multiple `<p>`/`<br>` elements.

---

## Desired Regimen

1. **LLM prompts** are sent to the server; the server processes them and produces a **.docx** document (the “fully adorned” cover letter).
2. The **fully adorned .docx** is sent to the client for editing.
3. **Print preview** generates a PDF from the (possibly edited) .docx: client sends the .docx to the server, server returns PDF.

---

## Step-by-Step: What We Have vs What We Need

### Step 1: Server produces a .docx from LLM output

| Aspect | Current state | Target |
|--------|----------------|--------|
| LLM output | Server gets markdown + HTML from LLM and returns `markdown`, `html`, `docxTemplateHints`. | Same; in addition the server **builds a .docx** from that content. |
| .docx creation | **Not done on server.** Frontend is expected to create .docx from markdown/hints (e.g. client-side lib or export from editor). | **Done on server:** after generation, server creates a .docx (e.g. via python-docx from markdown/HTML), applies font/margins from user print settings, and returns it. |
| Can it be direct? | N/A | **Yes.** We do not need to “receive HTML and apply to a local .docx” as a separate step. We can generate the .docx directly from the same content we already have (markdown or HTML). A “local template .docx” is optional (e.g. for letterhead); the minimal path is: LLM → markdown/HTML → server builds .docx in memory → return .docx. |

**Implementation:** Server-side module (e.g. `app/utils/docx_generator.py` or `app/services/cover_letter_docx_service.py`) that:

- Inputs: markdown (or HTML), optional print properties (font, size, margins).
- Uses **python-docx** to create a `Document`, set default font/size, and add paragraphs/runs from the content.
- Returns .docx as **bytes**.

The **generation response** (e.g. `POST /api/job-info` and `POST /api/cover-letter/generate-with-text-resume`) is extended to include **`docxBase64`** (or a **`docxUrl`** if we prefer to store the file and return a download link). The client can then use this as the “fully adorned .docx” for step 2.

---

### Step 2: Fully adorned .docx sent to client for editing

| Aspect | Current state | Target |
|--------|----------------|--------|
| What client gets | `markdown`, `html`, `docxTemplateHints`. Client must create .docx itself or use an editor that exports .docx. | Client receives the **actual .docx** (e.g. in the generation response as `docxBase64`, or via a download URL). |
| Editing | User edits in whatever editor the app provides; that editor might work on HTML/markdown and then export .docx. | User edits the **.docx** (e.g. in a DOCX-capable editor or after downloading). The “source of truth” for the letter is the .docx. |

**Implementation:** Once the server returns `docxBase64` (or a URL) in the generation response, the frontend should:

- Prefer the .docx as the main artifact: show “Download .docx” and/or open it in an editor that can edit .docx.
- Optionally keep showing markdown/HTML for preview, but the canonical document for “save” and “print preview” is the .docx (possibly re-uploaded after editing).

---

### Step 3: Print preview = PDF of the (edited) .docx

| Aspect | Current state | Target |
|--------|----------------|--------|
| Print preview input | Today: **HTML** is sent to `POST /api/files/print-preview-pdf` (with `htmlContent` + `printProperties`). Server converts HTML → PDF (e.g. LibreOffice or previously Playwright/WeasyPrint). There is also **`POST /api/files/docx-to-pdf`**: client uploads a .docx and gets PDF. | **Print preview should be “PDF of the .docx”.** So the client sends the **(possibly edited) .docx** to the server; the server returns PDF. No HTML path required for this flow. |
| Endpoint to use | `POST /api/files/docx-to-pdf` already exists: request body = multipart with **`file`** = .docx; response = `pdfBase64`. | Same. **Use `POST /api/files/docx-to-pdf`** for print preview when the user is working from a .docx. |

**Implementation:** No server change needed for step 3. The frontend should:

- For “Print preview,” take the current .docx (the one the user is editing, or the one from the last generation if unchanged).
- Call **POST /api/files/docx-to-pdf** with that .docx file.
- Display or download the returned PDF.

If the client still has an “HTML-only” path (e.g. user never requested .docx), you could keep `print-preview-pdf` for that legacy path; but the **primary** flow should be: .docx → docx-to-pdf → PDF.

---

## Summary Table

| Step | Desired | Current | Action |
|------|---------|---------|--------|
| 1 | Server produces .docx from LLM output | Server returns only markdown + html + hints | Add server-side .docx generation; add `docxBase64` (or URL) to generation response. |
| 2 | Client receives .docx for editing | Client gets markdown/html/hints and must create .docx itself | Frontend uses `docxBase64` (or URL) as the main artifact; user edits that .docx. |
| 3 | Print preview = PDF of .docx | docx-to-pdf exists; print-preview-pdf uses HTML | Use **POST /api/files/docx-to-pdf** for print preview when the letter is a .docx. |

---

## Optional: “HTML applied to a local .docx”

You asked: *“Can we only receive HTML and apply it to a local .docx?”*

- **We can do either:**
  - **Direct:** Build the .docx from markdown/HTML in code (python-docx, no template file). This is enough for the regimen above.
  - **Template-based:** Keep a “template.docx” on the server (e.g. with letterhead, styles). After generation, create a copy of the template and replace a placeholder (e.g. `{{BODY}}`) with the generated content, or use a library that merges HTML into a docx template. That gives more control over layout/letterhead but is not required for the basic flow.
- Recommendation: implement **direct** .docx generation first (content + font/size from print settings). Add a template-based path later if you need letterhead or strict corporate formatting.

---

## Files to Touch (server)

1. **New (or existing) module:** e.g. `app/utils/docx_generator.py` or `app/services/cover_letter_docx_service.py` – build .docx from markdown/HTML + optional print props; return bytes.
2. **Cover letter generation:** After `get_job_info()` returns `{ markdown, html }`, call the docx generator, then include **docxBase64** (and optionally **docxTemplateHints** unchanged) in the JSON response.
3. **Response model:** Extend `CoverLetterGenerationResponse` (or the actual response dict) with an optional **docxBase64** (and optionally **fileName** for the suggested download name).
4. **Print preview (frontend):** Use **POST /api/files/docx-to-pdf** with the current .docx file for the “print preview” action.

No change to **POST /api/files/docx-to-pdf** or **POST /api/files/save-cover-letter** is required for the regimen; both already support .docx.
