# Print Preview PDF API

This endpoint converts **frontend-modified HTML** into a PDF for the Print Preview feature. The backend uses the **user’s print preferences** (margins, font, page size, line height) and passes them to the PDF engine so the resulting document matches the user’s settings.

**Single source of truth:** Use **POST** `/api/files/print-template` to get the exact HTML/CSS used for PDF. Render that HTML in a WebView for a "Match PDF" or "Print Preview" view that matches the PDF exactly. See [PRINT_TEMPLATE_SINGLE_SOURCE_OF_TRUTH.md](./PRINT_TEMPLATE_SINGLE_SOURCE_OF_TRUTH.md).

**PDF engine:** By default the service prefers **Playwright** (Chromium) and falls back to **WeasyPrint** if Playwright is unavailable or fails. If Playwright margins are wrong at page breaks, set **`PRINT_PREVIEW_USE_WEASYPRINT_ONLY=true`** to use **only WeasyPrint** for Print Preview (see [Using WeasyPrint only](#using-weasyprint-only)). When not using WeasyPrint-only, the browser’s print API is used for margins.

## Endpoint

**POST** `/api/files/print-preview-pdf`

Convert HTML to PDF using user print preferences and return base64-encoded PDF data.

## Authentication

Requires a valid **Bearer** token (same as other `/api/files` endpoints).

```
Authorization: Bearer <access_token>
```

## Request Body

### Full Example (with user print preferences)

```json
{
  "htmlContent": "<div><p>Dear Hiring Manager,</p><p>I am writing to apply for...</p></div>",
  "printProperties": {
    "margins": {
      "top": 1.0,
      "right": 0.75,
      "bottom": 0.75,
      "left": 0.75
    },
    "fontFamily": "Calibri",
    "fontSize": 11,
    "lineHeight": 1.15,
    "pageSize": {
      "width": 8.5,
      "height": 11.0
    },
    "useDefaultFonts": false
  },
  "user_id": "693326c07fcdaab8e81cdd2f",
  "user_email": "simonkalt@gmail.com"
}
```

### Minimal Example (required fields only)

```json
{
  "htmlContent": "<div><p>Cover letter content here.</p></div>",
  "printProperties": {
    "margins": {
      "top": 1.0,
      "right": 0.75,
      "bottom": 0.25,
      "left": 0.75
    }
  }
}
```

Other `printProperties` fields use backend defaults (see below) when omitted.

## Request Fields

| Field             | Type   | Required | Description                                                                       |
| ----------------- | ------ | -------- | --------------------------------------------------------------------------------- |
| `htmlContent`     | string | ✅ Yes   | The HTML to convert to PDF (fragment). Placed inside `<body>`.                    |
| `printProperties` | object | ✅ Yes   | User print preferences (margins required; font, page size, line height optional). |
| `user_id`         | string | ❌ No    | User ID for logging (e.g. MongoDB ObjectId).                                      |
| `user_email`      | string | ❌ No    | User email for logging.                                                           |

### `printProperties` (required)

Same structure as **POST** `/api/files/generate-pdf`. These values are passed to the PDF library so the document uses the user’s settings.

| Field             | Type    | Required | Default                        | Description                                                                          |
| ----------------- | ------- | -------- | ------------------------------ | ------------------------------------------------------------------------------------ |
| `margins`         | object  | ✅ Yes   | -                              | Margins in inches (top, right, bottom, left).                                        |
| `fontFamily`      | string  | ❌ No    | `"Times New Roman"`            | Font family. Applied to the document unless `useDefaultFonts` is true.               |
| `fontSize`        | number  | ❌ No    | `12`                           | Font size in points (pt). Applied unless `useDefaultFonts` is true.                  |
| `lineHeight`      | number  | ❌ No    | `1.6`                          | Line height multiplier. Applied unless `useDefaultFonts` is true.                    |
| `pageSize`        | object  | ❌ No    | `{ width: 8.5, height: 11.0 }` | Page size in inches (e.g. Letter). Passed to WeasyPrint `@page`.                     |
| `useDefaultFonts` | boolean | ❌ No    | `false`                        | If `true`, only margins and page size are applied; no font/size/line-height on body. |

### `margins` (required when `printProperties` is present)

| Field    | Type   | Required | Description             |
| -------- | ------ | -------- | ----------------------- |
| `top`    | number | ✅ Yes   | Top margin (inches).    |
| `right`  | number | ✅ Yes   | Right margin (inches).  |
| `bottom` | number | ✅ Yes   | Bottom margin (inches). |
| `left`   | number | ✅ Yes   | Left margin (inches).   |

### `pageSize` (optional)

| Field    | Type   | Required | Description                        |
| -------- | ------ | -------- | ---------------------------------- |
| `width`  | number | ✅ Yes\* | Page width in inches (e.g. 8.5).   |
| `height` | number | ✅ Yes\* | Page height in inches (e.g. 11.0). |

\*Required if `pageSize` is present.

## How the PDF is built

The backend uses **WeasyPrint** and applies user preferences as follows:

1. **Always applied**
   - **@page**: `size` from `printProperties.pageSize` (default 8.5 × 11 in), `margin` from `printProperties.margins`.

2. **Applied when `useDefaultFonts` is false** (default)
   - **body**: `font-family` from `printProperties.fontFamily`, `font-size` from `printProperties.fontSize`, `line-height` from `printProperties.lineHeight`, so the generated PDF matches the user’s font and line height settings.

3. **When `useDefaultFonts` is true**
   - Only `@page` (margins and page size) is applied; no font/size/line-height is set on the document body.

Send the same **printProperties** you use in user settings (or from **POST** `/api/files/generate-pdf`) so the Print Preview PDF matches the rest of the app.

## Response

### Success (200 OK)

```json
{
  "success": true,
  "pdfBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU...",
  "message": "PDF generated successfully"
}
```

| Field       | Type    | Description                                                    |
| ----------- | ------- | -------------------------------------------------------------- |
| `success`   | boolean | `true` on success.                                             |
| `pdfBase64` | string  | Base64-encoded PDF (no `data:application/pdf;base64,` prefix). |
| `message`   | string  | `"PDF generated successfully"`.                                |

### Using the PDF on the frontend

- **Display in WebView / iframe:**  
  `src = "data:application/pdf;base64," + response.pdfBase64`

- **Download:**  
  Decode `pdfBase64` to bytes and trigger a download with `application/pdf` and a filename (e.g. `PrintPreview.pdf`).

## Error Responses

### 400 Bad Request

**Missing or empty `htmlContent`:**

```json
{
  "detail": "htmlContent is required and cannot be empty"
}
```

**Missing `printProperties` or `printProperties.margins`:**

```json
{
  "detail": "printProperties is required"
}
```

```json
{
  "detail": "printProperties.margins is required"
}
```

### 401 Unauthorized

Missing or invalid `Authorization` header:

```json
{
  "detail": "Not authenticated"
}
```

### 500 Internal Server Error

PDF generation failed (e.g. WeasyPrint not available or invalid HTML):

```json
{
  "detail": "Failed to generate PDF: <error message>"
}
```

### 404 Not Found / "Falling back to HTML preview"

If the front-end shows **"Error: Not Found: Falling back to HTML preview"**, the request is hitting a URL that does not exist. Ensure you call the **correct base path**:

- **Print template (HTML/CSS for Match PDF view):** **POST** `/api/files/print-template`
- **Print Preview PDF:** **POST** `/api/files/print-preview-pdf`

Do **not** use paths like `/api/print-preview-pdf` or `/print-template` without the `/api/files/` prefix. In Docker (or any deployment), ensure the app registers the PDF router so these routes exist; check startup logs for `Registered router: pdf` or `Files route registered: ... print-template`.

## Example: Fetch with Bearer token

```javascript
// Use the same printProperties as in user settings (margins, font, page size, line height)
const response = await fetch("/api/files/print-preview-pdf", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify({
    htmlContent: myModifiedHtml,
    printProperties: {
      margins: { top: 1, right: 0.75, bottom: 0.75, left: 0.75 },
      fontFamily: "Calibri",
      fontSize: 11,
      lineHeight: 1.15,
      pageSize: { width: 8.5, height: 11.0 },
      useDefaultFonts: false,
    },
  }),
});

if (!response.ok) {
  const err = await response
    .json()
    .catch(() => ({ detail: response.statusText }));
  throw new Error(err.detail || "Print Preview PDF failed");
}

const { success, pdfBase64 } = await response.json();
// Use pdfBase64 for display or download
```

## Notes for frontend

1. **HTML is wrapped in a constrained container**  
   The backend wraps your HTML in a `.print-content` div with `max-width: 100%`, `overflow-x: hidden`, and `overflow-wrap: break-word` so content cannot spill past the right margin. Avoid sending HTML with fixed widths (e.g. `width: 800px`, `width: 100vw`) or large padding; use relative units or let the container constrain layout.

2. **User print preferences**  
   Send `printProperties` from the user’s settings (margins, font family, font size, page size, line height, useDefaultFonts). The backend passes these to WeasyPrint so the PDF matches the user’s choices.

3. **Same shape as generate-pdf**  
   `printProperties` has the same structure as **POST** `/api/files/generate-pdf`. You can reuse the same object from user preferences for both endpoints.

4. **HTML you send**  
   Send the HTML fragment you use for Print Preview. The backend wraps it in a `.print-content` container (to prevent overflow) and applies margins and, when `useDefaultFonts` is false, body font/size/line-height from `printProperties`. The user’s font/size is the **baseline**; inline styles in your HTML (e.g. larger name, different font from LLM “additional instructions”) are preserved and not overridden.

5. **If custom fonts/sizes still look uniform in the PDF**  
   The backend does not override inline `font-family`, `font-size`, or `line-height`. To verify what the backend received: after generating a Print Preview PDF, check the **HTML snippet** file: same folder as the debug PDF (project `debug/`), filename `print_preview_pdf_<timestamp>_html_snippet.txt`. The server log line “Print preview HTML snippet saved: …” shows the full path. Search for `style="font-size` or `font-size:` inside a `style` attribute. If those are missing, the HTML sent to the API has no inline font/size—so the issue is either (1) the LLM not outputting them, (2) the frontend stripping them before sending, or (3) a format-check/sanitizer removing them. Ensure the payload you send actually contains the inline styles you expect.

6. **Encoding**  
   Use `Content-Type: application/json` and ensure `htmlContent` is a valid JSON string (escape quotes and control characters as needed).

7. **Other endpoint**  
   **POST** `/api/files/generate-pdf` generates PDF from **Markdown** and `printProperties`. Use **POST** `/api/files/print-preview-pdf` when the source is your **modified HTML** for Print Preview.

---

## Frontend guidelines to avoid PDF margin and page-break issues

These steps help prevent cut-off content and odd gaps at page breaks (e.g. bottom of page 1 / top of page 2).

### 1. Use a simple, block-based HTML structure

- Prefer **one root wrapper** (e.g. a single `<div>`) containing **block elements** like `<p>`, `<div>`, `<ul>`, `<ol>`.
- Use **paragraphs** for body text so the backend’s `page-break-inside: avoid` on `.print-content p` can reduce mid-paragraph breaks.

**Good:**

```html
<div>
  <p>Dear Hiring Manager,</p>
  <p>I am writing to apply for...</p>
  <p>Thank you for your consideration.</p>
</div>
```

**Avoid:** One giant `<div>` with all text in spans or inline elements, or deeply nested divs with heavy inline styles.

### 2. Avoid fixed widths and viewport units

- Do **not** set `width`, `min-width`, or `max-width` in **px, vw, or fixed units** on the HTML you send (e.g. no `style="width: 800px"` or `width: 100vw`).
- Let the backend’s `.print-content` constrain width. Use **%** or no width if you need a width at all.

### 3. Keep margins and padding modest

- Avoid **large** `margin` or `padding` on block elements (e.g. `margin-bottom: 2in`). Use small values (e.g. `0.5em`, `1em`) so content doesn’t create big gaps at page breaks.
- Prefer **margin only between elements** (e.g. `p { margin: 0 0 0.5em 0; }`) rather than one big margin on a wrapper.

### 4. Optional: normalize HTML before sending

Before calling the API, you can:

- **Strip or override** inline `style` on the root wrapper that sets `width`, `min-width`, `max-width`, or large `margin`/`padding`.
- **Wrap** the fragment in a single outer div with no width/margin if your editor or template produces a wide or padded root.

Example (pseudo-code):

```javascript
// If your HTML comes from a rich editor, consider wrapping and/or stripping root width/margin
const root = document.createElement("div");
root.innerHTML = editorHtml;
const first = root.firstElementChild;
if (first && first.style) {
  first.style.width = "";
  first.style.minWidth = "";
  first.style.maxWidth = "";
}
const htmlContent = root.innerHTML;
// Then send htmlContent to POST /api/files/print-preview-pdf
```

### 5. Match print properties to the UI

Send the **same** `printProperties` (margins, font size, line height, page size) that the user sees in the app’s print/preview settings. Mismatches can make margins or breaks look wrong even when the HTML is fine.

### 6. When using WeasyPrint only (`PRINT_PREVIEW_USE_WEASYPRINT_ONLY=true`)

Format the HTML so the backend’s page-break CSS applies correctly:

- **Paragraphs:** Use `<p>` for body text. The backend applies `page-break-inside: avoid` to `.print-content p` so paragraphs don’t split across pages.
- **Headings:** Use `<h1>`, `<h2>`, `<h3>` so the backend can apply `page-break-after: avoid` and keep headings with the following content.
- **Sections:** You may wrap logical sections in `<div class="letter-section">` for structure; the backend does **not** apply `page-break-inside: avoid` to `.letter-section` (doing so caused the first page to end right after the company name). Content flows naturally; paragraphs and headings still control breaks.
- **Forced page break:** To start a new page at a specific spot, insert an empty `<div class="page-break"></div>`.
- **No inline page-break styles:** Put page-break logic in structure/classes; the backend injects the CSS in `<style>` in the head.

Example:

```html
<div>
  <p>Dear Hiring Manager,</p>
  <div class="letter-section">
    <p>I am writing to apply for...</p>
    <p>Thank you for your consideration.</p>
  </div>
  <div class="page-break"></div>
  <p>Additional page content here.</p>
</div>
```

---

## Alternatives if margins still fail

If page-break margins are still wrong after frontend changes and the backend uses Playwright with **API margins** (margins passed to `page.pdf(margin={...})` instead of CSS `@page`), consider these options.

### 1. Client-side print (no server PDF)

- **Idea:** Skip the Print Preview PDF API. Show the cover letter in a full-screen print-style view and use the **browser’s print** (e.g. **Print** → “Save as PDF” or a real printer). Margins are then controlled by the browser/OS print dialog.
- **Pros:** No server PDF engine; margins and page breaks match what the user sets in the print dialog.
- **Cons:** User must use “Print” themselves; no direct “download PDF” from your app unless you use a client-side PDF library (see below).

**Variant:** Use a **client-side HTML-to-PDF library** (e.g. **html2pdf.js**, **jsPDF** + **html2canvas**) in the frontend. PDF is generated in the browser; margins are applied by the library. This keeps a “Download PDF” button without calling your backend for PDF. Quality and margin behavior depend on the library.

### 2. WeasyPrint-only (env flag) — **implemented**

- **Idea:** Force the backend to use **only WeasyPrint** for Print Preview (skip Playwright). WeasyPrint uses CSS Paged Media; some setups have more consistent margin behavior at page breaks.
- **How to use:** Set the environment variable **`PRINT_PREVIEW_USE_WEASYPRINT_ONLY=true`** (e.g. in `.env` or your server config). When set, `generate_pdf_from_html` uses the WeasyPrint path only and never calls Playwright.
- **Pros:** Single engine; avoids Chromium/Playwright margin quirks at page breaks.
- **Cons:** WeasyPrint can still have right-margin or font issues on some systems; no JavaScript.

### 3. External PDF API (hosted service)

- **Idea:** Send HTML (and optionally options) to a **hosted HTML-to-PDF API** that uses a different engine (e.g. **Prince**, **DocRaptor**, **PDFShift**, **Api2Pdf**). They handle margins and page breaks in a consistent way.
- **Pros:** Predictable output; less maintenance; often better typography and paged media.
- **Cons:** Cost; dependency on a third party; you may need to proxy requests or call from the frontend with an API key (keep keys server-side if possible).

### 4. Pre-paginated HTML (fixed-height “pages”)

- **Idea:** Don’t rely on the PDF engine to break pages. On the backend (or frontend), split content into **fixed-height “page” divs** (e.g. content height = page height minus top/bottom margin). Each div is one PDF page; you use `@page { margin: 0 }` and put all spacing inside the page divs.
- **Pros:** Full control over where each page ends and margins.
- **Cons:** Requires pagination logic (measure text/layout or approximate by line count); more complex and fragile for dynamic content.

### 5. Backend: Playwright with API margins (current behavior)

The backend now applies margins via **Playwright’s `page.pdf(margin={...})`** (not CSS `@page` margins). Chromium applies these at the PDF layer on every page. If you still see issues, try the options above or a different Chromium version (e.g. another Playwright/Chromium release).

---

## Installing Playwright (recommended for reliable margins)

For correct margins (including the right side), install Playwright and Chromium on the server:

```bash
pip install playwright
playwright install chromium
```

If Playwright is not available, the backend falls back to WeasyPrint, which can sometimes ignore the right margin.

## Using WeasyPrint only

If Playwright margins are wrong at page breaks (e.g. bottom of page 1 / top of page 2), you can force the backend to use **only WeasyPrint** for Print Preview:

1. Set the environment variable:

   ```bash
   PRINT_PREVIEW_USE_WEASYPRINT_ONLY=true
   ```

   (e.g. in `.env`, or in your process manager / deployment config.)

2. Restart the app. Print Preview PDF requests will then use WeasyPrint only: **@page** has explicit size and margins (so breaks are correct on every page), plus page-break CSS (`page-break-after: avoid` on headings, `orphans`/`widows` on body; `.letter-section` is not kept together so the page does not break right after the company name).

WeasyPrint must be installed.

### Seeing the raw HTML output (no server alteration)

To see what the **raw** `htmlContent` produces with no server-side wrapper or CSS, set:

```bash
PRINT_PREVIEW_RAW_HTML=true
```

The backend will then use a minimal wrapper (DOCTYPE, `<html>`, `<head>` charset, `<body>` with your HTML only). No `@page`, no `.print-content`, no injected styles—so the PDF reflects WeasyPrint’s default page size and the styling (if any) in your HTML. Restart the app after changing this. Set back to `false` when you are done comparing. If it is not, the API will return an error when this flag is set.
