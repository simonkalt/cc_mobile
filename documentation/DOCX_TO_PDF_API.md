# DOCX to PDF API Documentation

> **Removed from this Python API (2026).** `POST /api/files/docx-to-pdf` is **disabled** and returns **HTTP 410 Gone**. **LibreOffice** and **WeasyPrint** are no longer used or required in this repo for PDFs. Use the **Syncfusion (.NET)** service for `.docx` → PDF and other PDF workflows. The document below is **historical**.

---

This endpoint ~~converts~~ *previously converted* a **Word `.docx` file** to **PDF** on the server. It used **LibreOffice headless** (`soffice`), not the Markdown/HTML PDF pipeline used by `POST /api/files/generate-pdf` (also removed).

## Endpoint

**POST** `/api/files/docx-to-pdf`

## Authentication

This endpoint accepts **either** authentication scheme:

- **User JWT**: `Authorization: Bearer <your_access_token>`
- **Integration key**: `X-Service-Auth: <SERVICE_AUTH_KEY>`

### How this is configured

Integration-auth routes are controlled by `integration_auth_endpoints.json` in repo root.
When `POST /api/files/docx-to-pdf` is listed there with `"enabled": true`, the server enforces:

- valid JWT **or**
- valid `X-Service-Auth`

## Request

### Content type

Use **`multipart/form-data`** with a single file part.

| Part name | Type   | Required | Description |
| --------- | ------ | -------- | ----------- |
| `file`    | file   | Yes      | The `.docx` file. Filename must end with `.docx` (case-insensitive). |

**Important for browsers:** append the file with `FormData` and **do not** set `Content-Type` manually—the runtime must set the `multipart/form-data` boundary.

### Constraints

- Uploaded body must be at least **100 bytes** (very small uploads are rejected).
- Only **`.docx`** is accepted (Office Open XML). Legacy `.doc` is not handled by this endpoint.

## Response

### Success (200 OK)

```json
{
  "success": true,
  "pdfBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU...",
  "message": "PDF generated from .docx successfully"
}
```

| Field       | Type    | Description |
| ----------- | ------- | ----------- |
| `success`   | boolean | `true` on success |
| `pdfBase64` | string  | Base64-encoded PDF **without** the `data:application/pdf;base64,` prefix |
| `message`   | string  | Human-readable success message |

Decode `pdfBase64` to binary PDF bytes for download, preview, or upload to storage.

## Error responses

| Status | When | Example `detail` |
| ------ | ---- | ------------------ |
| **400** | Missing/invalid filename, empty file, read failure, or invalid content | `A .docx file is required. Use the 'file' form field.` |
| **400** | File too small | `Uploaded file is too small or empty` |
| **400** | Invalid `.docx` content | `Invalid or empty .docx content` |
| **401** | Missing or invalid `X-Service-Auth` | `Invalid or missing X-Service-Auth header` |
| **500** | LibreOffice ran but conversion failed | `Conversion failed: ...` |
| **503** | LibreOffice not installed on server | `Docx to PDF is not available: LibreOffice (soffice) is not installed on the server.` |

## Server requirements

- **LibreOffice** must be installed and **`soffice` on PATH** (e.g. Debian/Ubuntu: `libreoffice-writer`).
- Conversion runs in a worker thread with a **120s** timeout; very large documents may hit timeout errors.

## Integration examples (server-side only)

`X-Service-Auth` is a shared secret. Do not send it from browser/mobile WebView code.
If the caller is frontend, route through your host backend proxy and add this header there.

### JavaScript / TypeScript (Fetch + FormData)

```javascript
async function convertDocxToPdf(docxFile, serviceAuthKey, baseUrl = "") {
  const formData = new FormData();
  formData.append("file", docxFile, docxFile.name);

  const response = await fetch(`${baseUrl}/api/files/docx-to-pdf`, {
    method: "POST",
    headers: {
      "X-Service-Auth": serviceAuthKey,
      // Do NOT set Content-Type — browser sets multipart boundary
    },
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }

  const data = await response.json();
  const pdfBlob = base64ToBlob(data.pdfBase64, "application/pdf");
  return { ...data, pdfBlob };
}

function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
}
```

### Download the PDF in the browser

```javascript
const { pdfBlob } = await convertDocxToPdf(fileInput.files[0], token);
const url = URL.createObjectURL(pdfBlob);
const a = document.createElement("a");
a.href = url;
a.download = "document.pdf";
a.click();
URL.revokeObjectURL(url);
```

### Axios

```javascript
import axios from "axios";

async function convertDocxToPdf(docxFile, serviceAuthKey) {
  const formData = new FormData();
  formData.append("file", docxFile);

  const { data } = await axios.post("/api/files/docx-to-pdf", formData, {
    headers: {
      "X-Service-Auth": serviceAuthKey,
      // Let axios set Content-Type for multipart
    },
  });

  return data.pdfBase64;
}
```

## Testing with cURL

Replace `SERVICE_AUTH_KEY` and path to your `.docx`:

```bash
curl -X POST "http://localhost:8000/api/files/docx-to-pdf" \
  -H "X-Service-Auth: SERVICE_AUTH_KEY" \
  -F "file=@/path/to/cover-letter.docx"
```

Save PDF from JSON (requires `jq`):

```bash
curl -s -X POST "http://localhost:8000/api/files/docx-to-pdf" \
  -H "X-Service-Auth: SERVICE_AUTH_KEY" \
  -F "file=@/path/to/cover-letter.docx" \
  | jq -r .pdfBase64 | base64 -d > output.pdf
```

## Relationship to other PDF endpoints

| Endpoint | Input | Use case |
| -------- | ----- | -------- |
| **`POST /api/files/docx-to-pdf`** | Multipart `.docx` | PDF must match edited Word document |
| **`POST /api/files/generate-pdf`** | JSON Markdown + print properties | PDF from markdown (see `PDF_GENERATION_API.md`) |
| **`POST /api/files/print-preview-pdf`** | JSON HTML + print properties | Print preview / styled HTML pipeline |

## Frontend checklist

- [ ] `POST` to `/api/files/docx-to-pdf`
- [ ] `X-Service-Auth: <SERVICE_AUTH_KEY>` header set
- [ ] Body is `multipart/form-data` with field name **`file`**
- [ ] Do not manually set `Content-Type` for `FormData` in the browser
- [ ] Filename ends with `.docx`
- [ ] On success, decode `pdfBase64` to a Blob or binary buffer
- [ ] Handle 400 (bad file), 401 (service auth), 500 (conversion error), 503 (LibreOffice missing)

## Implementation reference

Server logic: `app/api/routers/pdf.py` (`docx_to_pdf_endpoint`), conversion: `app/services/pdf_service.py` (`convert_docx_to_pdf`).
