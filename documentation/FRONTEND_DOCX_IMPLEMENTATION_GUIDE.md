# Frontend DOCX Implementation Guide

This is the frontend handoff for the DOCX source-of-truth workflow.

- Source of truth is `.docx` (not HTML)
- Frontend creates and edits DOCX natively
- PDF export should come from the DOCX editor engine (Syncfusion/Nutrient)

See also:

- `documentation/DOCX_SOURCE_OF_TRUTH_FRONTEND_GUIDE.md` (full detailed version)
- `documentation/COVER_LETTER_GENERATION_API.md` (updated response contract)
- `documentation/SAVE_COVER_LETTER_API.md` (DOCX save contract)
- `documentation/COVER_LETTER_MANAGEMENT_API.md` (DOCX management/download guidance)

---

## Recommended Frontend Flow

1. Generate cover letter content from backend (`markdown` + `docxTemplateHints`).
2. Build initial DOCX in RN using `docx` + `expo-file-system`.
3. Open/edit DOCX in `react-native-webview` using Syncfusion or Nutrient web editor.
4. Save edited DOCX to backend with:
   - `POST /api/files/save-cover-letter`
   - `contentType: application/vnd.openxmlformats-officedocument.wordprocessingml.document`
   - `coverLetterContent: <base64_docx_bytes>`
5. Export PDF from the editor engine (not HTML conversion) when user needs print/share.

---

## Why

- Avoids HTML round-trip drift
- Maintains DOCX fidelity in editable and stored artifacts
- Produces more consistent PDFs from native DOCX model
