# Docx to PDF API (frontend guide)

Use this endpoint when the cover letter is **edited as a .docx** (e.g. in a Document Editor WebView). The server converts the **.docx file directly to PDF**, so the PDF matches the document formatting (no HTML pipeline).

---

## Endpoint

**POST** `/api/files/docx-to-pdf`

**Auth:** Bearer token (JWT) required, same as other `/api/files` routes.

**Request:** `multipart/form-data` with a single file.

| Part name | Type   | Required | Description        |
|-----------|--------|----------|--------------------|
| `file`    | file   | ✅ Yes   | The .docx document. |

**Response (200):**

```json
{
  "success": true,
  "pdfBase64": "<base64-encoded PDF>",
  "message": "PDF generated from .docx successfully"
}
```

Decode `pdfBase64` to get the PDF bytes (e.g. for save, share, or print).

---

## Frontend usage

### React Native / Expo

1. Get the .docx as a local file URI or blob (e.g. from your Document Editor export or from `expo-file-system`).
2. Build a `FormData` and append the file under the key **`file`**.
3. Call the API with the same JWT you use for other file endpoints.

**Example (fetch):**

```js
const formData = new FormData();
formData.append('file', {
  uri: docxUri,           // e.g. file:///path/to/letter.docx
  name: 'letter.docx',
  type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
});

const response = await fetch('https://your-api.com/api/files/docx-to-pdf', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
  },
  body: formData,
});

if (!response.ok) {
  const err = await response.json().catch(() => ({ detail: response.statusText }));
  throw new Error(err.detail || 'Docx to PDF failed');
}

const { pdfBase64 } = await response.json();
// Decode base64 to bytes for saving/sharing (e.g. expo-file-system writeAsStringAsync with base64)
```

**Example (axios):**

```js
import * as FileSystem from 'expo-file-system';

const docxUri = 'file:///path/to/letter.docx'; // from your editor or docx package
const formData = new FormData();
formData.append('file', {
  uri: docxUri,
  name: 'cover-letter.docx',
  type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
});

const { data } = await axios.post(
  `${API_BASE}/api/files/docx-to-pdf`,
  formData,
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'multipart/form-data',
    },
  }
);

const pdfBase64 = data.pdfBase64;
// Save: await FileSystem.writeAsStringAsync(outPath, pdfBase64, { encoding: FileSystem.EncodingType.Base64 });
```

---

## cURL

```bash
curl -X POST "https://your-api.com/api/files/docx-to-pdf" \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "file=@/path/to/letter.docx"
```

---

## Error responses

| Status | Meaning |
|--------|--------|
| **400** | No file, not a .docx, or file too small/empty. Body: `{ "detail": "..." }`. |
| **401** | Missing or invalid JWT. |
| **503** | LibreOffice (`soffice`) is not installed on the server. Docx→PDF is unavailable. |
| **500** | Conversion failed (e.g. corrupted .docx or LibreOffice error). |

---

## Server requirement

The backend must have **LibreOffice** installed so the `soffice` command is available (e.g. on Linux: `apt-get install libreoffice-writer`). If it is not installed, the API returns **503** with a message that docx to PDF is not available.

---

## When to use which PDF endpoint

| Source of the content | Use this endpoint |
|------------------------|--------------------|
| **.docx file** (e.g. from Document Editor) | **POST /api/files/docx-to-pdf** (this one). PDF matches the .docx. |
| **HTML or Markdown** (legacy flow) | **POST /api/files/print-preview-pdf** with `htmlContent` or `markdownContent`. |

Do not send HTML or markdown derived from the .docx to `print-preview-pdf` if you want the PDF to match the .docx; use `docx-to-pdf` with the actual .docx file.
