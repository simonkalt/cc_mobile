# Server-side PDF generation (removed)

PDF creation that previously lived in this FastAPI service has been **moved to a Syncfusion-based .NET service**.

## What changed

| Route | Status |
| ----- | ------ |
| `POST /api/files/print-template` | **410 Gone** |
| `POST /api/files/generate-pdf` | **410 Gone** |
| `POST /api/files/print-preview-pdf` | **410 Gone** |
| `POST /api/files/docx-to-pdf` | **410 Gone** |

Response body uses FastAPI’s default error shape, e.g. `{"detail": "Server-side PDF generation is disabled on this API. Use the Syncfusion (.NET) service for PDF creation."}`

## Dependencies

- **weasyprint**, **playwright**, and **LibreOffice** are no longer required for this API (`requirements.txt` / Docker image updated accordingly).
- **PyPDF2** / **pymupdf** remain where used for **reading** PDFs (e.g. resume text extraction), not for generating print PDFs.

## Code reference

- `app/services/pdf_service.py` — legacy implementation, **not** called by routes anymore.
- `app/api/routers/pdf.py` — stub routes returning **410**.

## Docs

- `PDF_GENERATION_API.md` — historical API for `generate-pdf` / print preview.
- `DOCX_TO_PDF_API.md` — historical API for `docx-to-pdf`.
