# DOCX Source-of-Truth Frontend Guide

This document defines the new approach for cover-letter editing and PDF conversion:

- **Source of truth is `.docx`** (not HTML).
- Frontend creates and edits DOCX natively.
- PDF export should come from the DOCX editor engine (Syncfusion/Nutrient), not HTML conversion.

---

## Goal

Move from:

- LLM -> markdown + HTML -> HTML editor -> HTML-to-PDF

to:

- LLM -> text/markdown -> **DOCX generated in app** -> DOCX editor in WebView -> **editor-native PDF export**

This avoids HTML round-tripping and improves consistency between editable content and final PDF.

---

## Backend Contract (Current Branch)

### 1) Generate cover letter content

Use existing generation endpoints to get the raw letter content (markdown/text) and treat that as input for DOCX creation on the client.

- `POST /api/job-info`
- `POST /api/cover-letter/generate-with-text-resume`

### 2) Save generated cover letter (DOCX-first)

`POST /api/files/save-cover-letter`

The backend now accepts DOCX binary as base64 and stores it in S3.

#### Request (DOCX)

```json
{
  "coverLetterContent": "<base64_docx_bytes>",
  "fileName": "cover_letter_company_name",
  "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "user_id": "507f1f77bcf86cd799439011"
}
```

#### Notes

- `contentType` can be:
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (preferred)
  - `application/pdf`
  - `text/markdown`
- DOCX is validated as base64 ZIP payload (`PK` signature).
- Saved extension is `.docx` for DOCX uploads.

---

## Frontend Implementation (React Native + WebView)

## Step 1: Build DOCX from LLM output

Use:

- `docx`
- `expo-file-system`

```tsx
import { Document, Packer, Paragraph, TextRun } from "docx";
import * as FileSystem from "expo-file-system";

export async function createInitialDocx(letterText: string) {
  const paragraphs = letterText
    .split("\n")
    .map((line) => new Paragraph({ children: [new TextRun(line)] }));

  const doc = new Document({
    sections: [{ properties: {}, children: paragraphs }],
  });

  const blob = await Packer.toBlob(doc);
  const buffer = await blob.arrayBuffer();
  const base64 = Buffer.from(buffer).toString("base64");

  const uri = `${FileSystem.documentDirectory}cover_letter.docx`;
  await FileSystem.writeAsStringAsync(uri, base64, {
    encoding: FileSystem.EncodingType.Base64,
  });
  return { uri, base64 };
}
```

---

## Step 2: Edit DOCX in WebView

Use:

- `react-native-webview`
- Web bundle with either:
  - `@syncfusion/ej2-react-documenteditor`, or
  - Nutrient Document Authoring SDK

The RN app sends DOCX bytes/URI into WebView via `postMessage`.
The web editor imports DOCX natively and edits without HTML conversion.

---

## Step 3: Export PDF in editor

Export PDF directly from the same DOCX editor engine (Syncfusion/Nutrient), then return bytes to RN via `window.ReactNativeWebView.postMessage`.

Do not use HTML-to-PDF for this flow.

---

## Recommended Data Flow

1. Call backend generation endpoint -> receive cover letter text/markdown.
2. RN creates `cover_letter.docx` using `docx`.
3. Open DOCX in WebView editor.
4. User edits.
5. Save edited DOCX:
   - Convert to base64
   - `POST /api/files/save-cover-letter` with DOCX content type.
6. Export PDF from editor only when user needs share/print.

---

## Why this approach

- Prevents HTML formatting drift.
- Keeps editable state in the same format users download/share (`.docx`).
- Produces higher-fidelity PDF because conversion runs from native DOCX model.

---

## Migration Notes

- Existing HTML storage is still backward-compatible, but **new flow should not send HTML**.
- Frontend should treat HTML payloads as deprecated.
- New feature work should target DOCX + editor-native PDF only.
