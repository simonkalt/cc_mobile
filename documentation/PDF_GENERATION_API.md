# PDF Generation API Documentation

This endpoint generates properly formatted PDFs from Markdown content on the server-side, ensuring all Markdown formatting (bold, italic, headings, lists, etc.) is preserved correctly.

## Endpoint

**POST** `/api/files/generate-pdf`

Generate a PDF from Markdown content with proper formatting support.

## Request Body

### Complete Example Request

```json
{
  "markdownContent": "SIMON KALTGRAD\nPhone: (818) 419-5986 | Email: simonkalt@gmail.com\nLas Vegas, NV\nhttps://www.linkedin.com/in/simon-kaltgrad/\n\nDecember 23, 2025\n\nJobgether\n\nRe: Director / VP of Engineering\n\nTo the Jobgether Hiring Team,\n\nI'm applying for the Director / VP of Engineering role...",
  "printProperties": {
    "margins": {
      "top": 1.0,
      "right": 0.75,
      "bottom": 0.5,
      "left": 0.75
    },
    "fontFamily": "Verdana",
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

### Minimal Example Request (using defaults)

```json
{
  "markdownContent": "# Cover Letter\n\nDear Hiring Manager,\n\nThis is **bold** and this is *italic*.",
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

## Request Fields

### Top-Level Fields

| Field             | Type   | Required | Description                                                                                                                      |
| ----------------- | ------ | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `markdownContent` | string | ✅ Yes   | The Markdown content to convert to PDF. Can contain newlines (`\n`), bold (`**text**`), italic (`*text*`), headings, lists, etc. |
| `printProperties` | object | ✅ Yes   | Print configuration object (see below)                                                                                           |
| `user_id`         | string | ❌ No    | User ID for authentication/tracking (MongoDB ObjectId format)                                                                    |
| `user_email`      | string | ❌ No    | User email for authentication/tracking                                                                                           |

### `printProperties` Object

| Field             | Type    | Required | Default                      | Description                                            |
| ----------------- | ------- | -------- | ---------------------------- | ------------------------------------------------------ |
| `margins`         | object  | ✅ Yes   | -                            | Margin configuration (see below)                       |
| `fontFamily`      | string  | ❌ No    | `"Times New Roman"`          | Font family name (e.g., "Verdana", "Arial", "Georgia") |
| `fontSize`        | number  | ❌ No    | `12`                         | Font size in points (pt)                               |
| `lineHeight`      | number  | ❌ No    | `1.6`                        | Line height multiplier                                 |
| `pageSize`        | object  | ❌ No    | `{width: 8.5, height: 11.0}` | Page size in inches (see below)                        |
| `useDefaultFonts` | boolean | ❌ No    | `false`                      | Whether to use default system fonts                    |

### `margins` Object

| Field    | Type   | Required | Description             |
| -------- | ------ | -------- | ----------------------- |
| `top`    | number | ✅ Yes   | Top margin in inches    |
| `right`  | number | ✅ Yes   | Right margin in inches  |
| `bottom` | number | ✅ Yes   | Bottom margin in inches |
| `left`   | number | ✅ Yes   | Left margin in inches   |

### `pageSize` Object

| Field    | Type   | Required | Description                                            |
| -------- | ------ | -------- | ------------------------------------------------------ |
| `width`  | number | ✅ Yes   | Page width in inches (typically 8.5 for Letter size)   |
| `height` | number | ✅ Yes   | Page height in inches (typically 11.0 for Letter size) |

## Response

### Success Response (200 OK)

```json
{
  "success": true,
  "pdfBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU...",
  "message": "PDF generated successfully"
}
```

### Response Fields

| Field       | Type    | Description                                                             |
| ----------- | ------- | ----------------------------------------------------------------------- |
| `success`   | boolean | Always `true` for successful responses                                  |
| `pdfBase64` | string  | Base64-encoded PDF data (without `data:application/pdf;base64,` prefix) |
| `message`   | string  | Success message: "PDF generated successfully"                           |

## Error Responses

### 400 Bad Request

**Missing required field:**

```json
{
  "detail": "markdownContent is required"
}
```

**Missing printProperties:**

```json
{
  "detail": "printProperties is required"
}
```

**Missing margins:**

```json
{
  "detail": "printProperties.margins is required"
}
```

**Validation error (example):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "markdownContent"],
      "msg": "Field required",
      "input": {...}
    }
  ]
}
```

### 500 Internal Server Error

**PDF generation failed:**

```json
{
  "detail": "Failed to generate PDF: [error message]"
}
```

### 503 Service Unavailable

**PDF generation libraries not available:**

```json
{
  "detail": "PDF generation service is not available. markdown library is not installed."
}
```

or

```json
{
  "detail": "PDF generation service is not available. weasyprint library is not installed."
}
```

## Frontend Integration Examples

### JavaScript/TypeScript (Fetch API)

```javascript
async function generatePDF(
  markdownContent,
  printProperties,
  userId = null,
  userEmail = null
) {
  try {
    const response = await fetch("/api/files/generate-pdf", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        markdownContent: markdownContent,
        printProperties: printProperties,
        user_id: userId,
        user_email: userEmail,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // Convert base64 to blob for download or display
    const pdfBlob = base64ToBlob(data.pdfBase64, "application/pdf");

    // Option 1: Download the PDF
    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cover-letter.pdf";
    a.click();
    URL.revokeObjectURL(url);

    // Option 2: Display in iframe
    // const iframe = document.createElement('iframe');
    // iframe.src = URL.createObjectURL(pdfBlob);
    // document.body.appendChild(iframe);

    return data;
  } catch (error) {
    console.error("Error generating PDF:", error);
    throw error;
  }
}

// Helper function to convert base64 to Blob
function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

// Example usage
const markdown = `# Cover Letter

Dear Hiring Manager,

This is my **cover letter** with *formatting*.`;

const printProps = {
  margins: {
    top: 1.0,
    right: 0.75,
    bottom: 0.5,
    left: 0.75,
  },
  fontFamily: "Verdana",
  fontSize: 11,
  lineHeight: 1.15,
  pageSize: {
    width: 8.5,
    height: 11.0,
  },
};

generatePDF(markdown, printProps, "user123", "user@example.com");
```

### React Example

```jsx
import React, { useState } from "react";

function PDFGenerator() {
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGeneratePDF = async () => {
    setLoading(true);
    setError(null);

    try {
      const printProperties = {
        margins: {
          top: 1.0,
          right: 0.75,
          bottom: 0.5,
          left: 0.75,
        },
        fontFamily: "Verdana",
        fontSize: 11,
        lineHeight: 1.15,
        pageSize: {
          width: 8.5,
          height: 11.0,
        },
      };

      const response = await fetch("/api/files/generate-pdf", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          markdownContent: markdown,
          printProperties: printProperties,
          user_id: getUserId(), // Your user ID retrieval logic
          user_email: getUserEmail(), // Your user email retrieval logic
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to generate PDF");
      }

      const data = await response.json();

      // Download PDF
      const pdfBlob = base64ToBlob(data.pdfBase64, "application/pdf");
      const url = URL.createObjectURL(pdfBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "cover-letter.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <textarea
        value={markdown}
        onChange={(e) => setMarkdown(e.target.value)}
        placeholder="Enter markdown content..."
        rows={10}
      />
      <button onClick={handleGeneratePDF} disabled={loading || !markdown}>
        {loading ? "Generating..." : "Generate PDF"}
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Axios Example

```javascript
import axios from "axios";

async function generatePDF(
  markdownContent,
  printProperties,
  userId,
  userEmail
) {
  try {
    const response = await axios.post("/api/files/generate-pdf", {
      markdownContent: markdownContent,
      printProperties: printProperties,
      user_id: userId,
      user_email: userEmail,
    });

    // Handle success
    const pdfBlob = base64ToBlob(response.data.pdfBase64, "application/pdf");
    // ... download or display PDF
  } catch (error) {
    if (error.response) {
      // Server responded with error status
      console.error("Error:", error.response.data.detail);
    } else if (error.request) {
      // Request made but no response
      console.error("No response:", error.request);
    } else {
      // Error setting up request
      console.error("Error:", error.message);
    }
  }
}
```

## Validation Rules

1. **markdownContent**: Must be a non-empty string
2. **printProperties**: Must be an object
3. **printProperties.margins**: Must be an object with all four margin values (top, right, bottom, left) as numbers
4. **printProperties.pageSize**: If provided, must have both `width` and `height` as numbers
5. **Margins and page sizes**: Must be positive numbers (in inches)

## Testing the Endpoint

### Using cURL

```bash
curl -X POST http://localhost:8000/api/files/generate-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "markdownContent": "# Test Cover Letter\n\nThis is a **test**.",
    "printProperties": {
      "margins": {
        "top": 1.0,
        "right": 0.75,
        "bottom": 0.5,
        "left": 0.75
      },
      "fontFamily": "Verdana",
      "fontSize": 11,
      "lineHeight": 1.15,
      "pageSize": {
        "width": 8.5,
        "height": 11.0
      }
    }
  }'
```

### Using Postman

1. **Method**: POST
2. **URL**: `http://localhost:8000/api/files/generate-pdf`
3. **Headers**:
   - `Content-Type: application/json`
4. **Body** (raw JSON):
   ```json
   {
     "markdownContent": "# Cover Letter\n\nDear Hiring Manager,\n\nThis is a test.",
     "printProperties": {
       "margins": {
         "top": 1.0,
         "right": 0.75,
         "bottom": 0.5,
         "left": 0.75
       },
       "fontFamily": "Verdana",
       "fontSize": 11,
       "lineHeight": 1.15,
       "pageSize": {
         "width": 8.5,
         "height": 11.0
       }
     }
   }
   ```

### Expected Response

```json
{
  "success": true,
  "pdfBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU...",
  "message": "PDF generated successfully"
}
```

To save the PDF from the response:

```bash
# Extract base64 from JSON response and save
echo "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU..." | base64 -d > output.pdf
```

### Frontend Checklist

Use this checklist to verify your frontend implementation:

- [ ] Request uses `POST` method
- [ ] Request URL is `/api/files/generate-pdf`
- [ ] Request includes `Content-Type: application/json` header
- [ ] Request body includes `markdownContent` as a string
- [ ] Request body includes `printProperties` object
- [ ] `printProperties` includes `margins` object with `top`, `right`, `bottom`, `left`
- [ ] Optional fields (`fontFamily`, `fontSize`, `lineHeight`, `pageSize`, `useDefaultFonts`) are included if needed
- [ ] Response handling checks for `success: true`
- [ ] Response handling extracts `pdfBase64` from response
- [ ] Base64 PDF is converted to Blob before use
- [ ] Error handling checks for 400, 500, and 503 status codes
- [ ] Error messages are displayed to the user

## Server Implementation

The server should use a robust PDF generation library. Recommended options:

### Option 1: Puppeteer (Recommended)

```python
from playwright.async_api import async_playwright
import base64
from markdown import markdown

async def generate_pdf(markdown_content, print_properties):
    # Normalize markdown content: replace escaped newlines with actual newlines
    # This prevents backslashes from appearing in the PDF output
    normalized_markdown = markdown_content.replace('\\n', '\n').replace('\\r', '\r')

    # Convert markdown to HTML
    html = markdown(normalized_markdown, extensions=['extra', 'codehilite'])

    # Create styled HTML document
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: "{print_properties.get('fontFamily', 'Times New Roman')}";
                font-size: {print_properties.get('fontSize', 12)}pt;
                line-height: {print_properties.get('lineHeight', 1.6)};
                margin: 0;
                padding: 0;
            }}
            @page {{
                margin: {print_properties['margins']['top']*72}pt
                        {print_properties['margins']['right']*72}pt
                        {print_properties['margins']['bottom']*72}pt
                        {print_properties['margins']['left']*72}pt;
                size: {print_properties['pageSize']['width']*72}pt
                      {print_properties['pageSize']['height']*72}pt;
            }}
            h1, h2, h3, h4, h5, h6 {{
                font-weight: bold;
                margin-top: 1em;
                margin-bottom: 0.5em;
            }}
            h1 {{ font-size: 2em; }}
            h2 {{ font-size: 1.5em; }}
            h3 {{ font-size: 1.25em; }}
            strong, b {{ font-weight: bold; }}
            em, i {{ font-style: italic; }}
            ul, ol {{ margin: 1em 0; padding-left: 2em; }}
            code {{ background-color: #f4f4f4; padding: 2px 4px; }}
            pre {{ background-color: #f4f4f4; padding: 10px; }}
            blockquote {{ border-left: 4px solid #ddd; padding-left: 1em; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(styled_html)
        pdf_bytes = await page.pdf(
            format='Letter',
            margin={
                'top': f"{print_properties['margins']['top']}in",
                'right': f"{print_properties['margins']['right']}in",
                'bottom': f"{print_properties['margins']['bottom']}in",
                'left': f"{print_properties['margins']['left']}in"
            }
        )
        await browser.close()
        return base64.b64encode(pdf_bytes).decode('utf-8')
```

### Option 2: WeasyPrint (Python)

```python
from weasyprint import HTML, CSS
from markdown import markdown
import base64

def generate_pdf(markdown_content, print_properties):
    # Normalize markdown content: replace escaped newlines with actual newlines
    # This prevents backslashes from appearing in the PDF output
    normalized_markdown = markdown_content.replace('\\n', '\n').replace('\\r', '\r')

    html_content = markdown(normalized_markdown, extensions=['extra'])

    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{
                size: {print_properties['pageSize']['width']}in
                      {print_properties['pageSize']['height']}in;
                margin: {print_properties['margins']['top']}in
                       {print_properties['margins']['right']}in
                       {print_properties['margins']['bottom']}in
                       {print_properties['margins']['left']}in;
            }}
            body {{
                font-family: "{print_properties.get('fontFamily', 'Times New Roman')}";
                font-size: {print_properties.get('fontSize', 12)}pt;
                line-height: {print_properties.get('lineHeight', 1.6)};
            }}
            /* Add all the CSS styles from the client-side version */
        </style>
    </head>
    <body>{html_content}</body>
    </html>
    """

    pdf_bytes = HTML(string=styled_html).write_pdf()
    return base64.b64encode(pdf_bytes).decode('utf-8')
```

### Option 3: pdfkit (Node.js)

```javascript
const pdfkit = require("pdfkit");
const markdown = require("markdown-it")();
const fs = require("fs");

function generatePDF(markdownContent, printProperties) {
  const html = markdown.render(markdownContent);
  // Use html-pdf or similar library to convert HTML to PDF
  // Then return as base64
}
```

## FastAPI Example Implementation

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import base64

router = APIRouter()

class Margins(BaseModel):
    top: float
    right: float
    bottom: float
    left: float

class PageSize(BaseModel):
    width: float
    height: float

class PrintProperties(BaseModel):
    margins: Margins
    fontFamily: Optional[str] = "Times New Roman"
    fontSize: Optional[float] = 12
    lineHeight: Optional[float] = 1.6
    pageSize: Optional[PageSize] = PageSize(width=8.5, height=11.0)

class GeneratePDFRequest(BaseModel):
    markdownContent: str
    printProperties: PrintProperties
    user_id: Optional[str] = None
    user_email: Optional[str] = None

@router.post("/api/files/generate-pdf")
async def generate_pdf(request: GeneratePDFRequest):
    try:
        # Normalize markdown content: replace escaped newlines with actual newlines
        # This prevents backslashes from appearing in the PDF output
        normalized_markdown = request.markdownContent.replace('\\n', '\n').replace('\\r', '\r')

        # Generate PDF using your preferred library (Puppeteer, WeasyPrint, etc.)
        pdf_base64 = await generate_pdf_from_markdown(
            normalized_markdown,
            request.printProperties.dict()
        )

        return {
            "success": True,
            "pdfBase64": pdf_base64,
            "message": "PDF generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
```

## Notes

### Important Implementation Details

1. **Markdown Normalization**: The server automatically normalizes markdown content before processing:

   ```python
   # Replace escaped newlines with actual newlines to prevent backslashes in PDF
   normalized_markdown = markdown_content.replace('\\n', '\n').replace('\\r', '\r')
   ```

   This ensures that if the client sends markdown with escaped newlines (like `"\\n"` as a string), they are converted to actual newline characters before processing.

2. **Markdown Formatting Support**: The PDF preserves all Markdown formatting including:

   - **Bold** (`**text**`) and _italic_ (`*text*`) text
   - Headings (h1-h6) using `#`, `##`, etc.
   - Lists (ordered `1.` and unordered `-`)
   - Code blocks (```) and inline code (`code`)
   - Blockquotes (`>`)
   - Links (`[text](url)`)
   - Tables (if supported by markdown extensions)
   - Horizontal rules (`---`)

3. **Units**:

   - Margins and page sizes are specified in **inches**
   - Font sizes are in **points (pt)**
   - Line height is a **multiplier** (e.g., 1.15 means 15% spacing)

4. **Response Format**:

   - The response returns base64-encoded PDF data **without** the `data:application/pdf;base64,` prefix
   - The frontend must add this prefix if creating a data URI: `data:application/pdf;base64,${pdfBase64}`

5. **Current Server Implementation**:
   - Uses **WeasyPrint** for PDF generation
   - Uses **markdown** library with extensions: `extra`, `codehilite`, `tables`, `nl2br`
   - Automatically handles markdown normalization
   - Supports all standard Markdown features plus tables and code highlighting

### Common Issues and Solutions

**Issue**: PDF contains literal `\n` characters instead of line breaks

- **Solution**: Ensure the server is normalizing markdown (already implemented)

**Issue**: Font not rendering correctly

- **Solution**: Check that the font family name is correct and available on the server. Use `useDefaultFonts: true` to fall back to system fonts.

**Issue**: Margins not applied correctly

- **Solution**: Verify margins are provided in inches (not pixels or points). Default margins are 1.0" top, 0.75" sides, 0.25" bottom.

**Issue**: Base64 PDF won't display

- **Solution**: Ensure you're creating a proper Blob or data URI. The response doesn't include the `data:application/pdf;base64,` prefix.

**Issue**: 503 Service Unavailable error

- **Solution**: Ensure `markdown` and `weasyprint` Python packages are installed on the server.
