# Print Preview PDF API

This endpoint converts **frontend-modified HTML** into a PDF for the Print Preview feature. The backend uses the **user’s print preferences** (margins, font, page size, line height) and passes them to the PDF engine so the resulting document matches the user’s settings.

**PDF engine:** The service prefers **Playwright** (Chromium) for PDF generation because it applies margins via the browser’s print API, so all four sides (including the right margin) are reliable. If Playwright is not installed or fails, it falls back to **WeasyPrint**. To get reliable margins (and avoid right-side cutoff), install Playwright and Chromium (see below).

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

1. **User print preferences**  
   Send `printProperties` from the user’s settings (margins, font family, font size, page size, line height, useDefaultFonts). The backend passes these to WeasyPrint so the PDF matches the user’s choices.

2. **Same shape as generate-pdf**  
   `printProperties` has the same structure as **POST** `/api/files/generate-pdf`. You can reuse the same object from user preferences for both endpoints.

3. **HTML you send**  
   Send the HTML fragment you use for Print Preview. The backend wraps it in a document that applies `@page` (margins, page size) and, when `useDefaultFonts` is false, body font/size/line-height from `printProperties`.

4. **Encoding**  
   Use `Content-Type: application/json` and ensure `htmlContent` is a valid JSON string (escape quotes and control characters as needed).

5. **Other endpoint**  
   **POST** `/api/files/generate-pdf` generates PDF from **Markdown** and `printProperties`. Use **POST** `/api/files/print-preview-pdf` when the source is your **modified HTML** for Print Preview.

## Installing Playwright (recommended for reliable margins)

For correct margins (including the right side), install Playwright and Chromium on the server:

```bash
pip install playwright
playwright install chromium
```

If Playwright is not available, the backend falls back to WeasyPrint, which can sometimes ignore the right margin.
