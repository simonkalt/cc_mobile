# Print Preview PDF API

This endpoint converts **frontend-modified HTML** into a PDF for the Print Preview feature. The frontend sends its styled HTML; the backend wraps it in a minimal document with optional page layout and returns the PDF.

## Endpoint

**POST** `/api/files/print-preview-pdf`

Convert HTML to PDF and return base64-encoded PDF data.

## Authentication

Requires a valid **Bearer** token (same as other `/api/files` endpoints).

```
Authorization: Bearer <access_token>
```

## Request Body

### Full Example (with page options)

```json
{
  "htmlContent": "<div style=\"font-family: 'Calibri', serif; font-size: 11pt;\"><p>Dear Hiring Manager,</p><p>I am writing to apply for...</p></div>",
  "pageOptions": {
    "margins": {
      "top": 1.0,
      "right": 0.75,
      "bottom": 0.75,
      "left": 0.75
    },
    "pageSize": {
      "width": 8.5,
      "height": 11.0
    }
  },
  "user_id": "693326c07fcdaab8e81cdd2f",
  "user_email": "simonkalt@gmail.com"
}
```

### Minimal Example (HTML only, default page)

```json
{
  "htmlContent": "<div><p>Cover letter content here.</p></div>"
}
```

With no `pageOptions`, the backend uses default margins (1 in top, 0.75 in right/bottom/left) and page size 8.5 × 11 in.

## Request Fields

| Field         | Type   | Required | Description                                                                   |
| ------------- | ------ | -------- | ----------------------------------------------------------------------------- |
| `htmlContent` | string | ✅ Yes   | The HTML to convert to PDF (fragment or full markup). Placed inside `<body>`. |
| `pageOptions` | object | ❌ No    | Optional page layout (margins, page size). Omitted = defaults.                |
| `user_id`     | string | ❌ No    | User ID for logging (e.g. MongoDB ObjectId).                                  |
| `user_email`  | string | ❌ No    | User email for logging.                                                       |

### `pageOptions` (optional)

| Field      | Type   | Required | Default                                            | Description                        |
| ---------- | ------ | -------- | -------------------------------------------------- | ---------------------------------- |
| `margins`  | object | ❌ No    | top:1, right:0.75, bottom:0.75, left:0.75 (inches) | Margins in inches.                 |
| `pageSize` | object | ❌ No    | width:8.5, height:11.0 (inches)                    | Page size in inches (e.g. Letter). |

### `margins` (when provided)

| Field    | Type   | Description            |
| -------- | ------ | ---------------------- |
| `top`    | number | Top margin (inches)    |
| `right`  | number | Right margin (inches)  |
| `bottom` | number | Bottom margin (inches) |
| `left`   | number | Left margin (inches)   |

### `pageSize` (when provided)

| Field    | Type   | Description                       |
| -------- | ------ | --------------------------------- |
| `width`  | number | Page width in inches (e.g. 8.5)   |
| `height` | number | Page height in inches (e.g. 11.0) |

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
const response = await fetch("/api/files/print-preview-pdf", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify({
    htmlContent: myModifiedHtml,
    pageOptions: {
      margins: { top: 1, right: 0.75, bottom: 0.75, left: 0.75 },
      pageSize: { width: 8.5, height: 11.0 },
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

1. **HTML you send**  
   Send the exact HTML you use for Print Preview (including inline styles, fonts, font sizes). The backend does not change your styling; it only wraps the content in a document with `@page` (margins and size).

2. **Page options**  
   Use `pageOptions` to match your app’s print settings (margins and page size). If omitted, backend defaults (above) are used.

3. **Encoding**  
   Send the request with `Content-Type: application/json`. Ensure `htmlContent` is a valid JSON string (escape quotes and control characters as needed).

4. **Existing endpoint**  
   The existing **POST** `/api/files/generate-pdf` still generates PDF from **Markdown** and `printProperties`. Use **POST** `/api/files/print-preview-pdf` when the source is your **modified HTML** for Print Preview.
