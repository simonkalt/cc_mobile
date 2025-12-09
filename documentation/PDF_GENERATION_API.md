# PDF Generation API Documentation

This endpoint generates properly formatted PDFs from Markdown content on the server-side, ensuring all Markdown formatting (bold, italic, headings, lists, etc.) is preserved correctly.

## Endpoint

**POST** `/api/files/generate-pdf`

Generate a PDF from Markdown content with proper formatting support.

## Request Body

```json
{
  "markdownContent": "# Cover Letter\n\nDear Hiring Manager,\n\nThis is **bold** and this is *italic*.",
  "printProperties": {
    "margins": {
      "top": 1.0,
      "right": 0.75,
      "bottom": 0.25,
      "left": 0.75
    },
    "fontFamily": "Times New Roman",
    "fontSize": 12,
    "lineHeight": 1.6,
    "pageSize": {
      "width": 8.5,
      "height": 11.0
    }
  },
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

## Request Fields

- `markdownContent` (required): The Markdown content to convert to PDF
- `printProperties` (required): Print configuration object
  - `margins` (required): Object with `top`, `right`, `bottom`, `left` (in inches)
  - `fontFamily` (optional): Font family name (default: "Times New Roman")
  - `fontSize` (optional): Font size in points (default: 12)
  - `lineHeight` (optional): Line height multiplier (default: 1.6)
  - `pageSize` (optional): Object with `width` and `height` in inches (default: 8.5 x 11)
- `user_id` (optional): User ID for authentication
- `user_email` (optional): User email for authentication

## Response (200 OK)

```json
{
  "success": true,
  "pdfBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU...",
  "message": "PDF generated successfully"
}
```

## Response Fields

- `success`: Boolean indicating success
- `pdfBase64`: Base64-encoded PDF data (without data URI prefix)
- `message`: Success message

## Error Responses

- `400 Bad Request`: Missing required fields or invalid print properties
- `500 Internal Server Error`: PDF generation error

## Server Implementation

The server should use a robust PDF generation library. Recommended options:

### Option 1: Puppeteer (Recommended)

```python
from playwright.async_api import async_playwright
import base64
from markdown import markdown

async def generate_pdf(markdown_content, print_properties):
    # Convert markdown to HTML
    html = markdown(markdown_content, extensions=['extra', 'codehilite'])

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
    html_content = markdown(markdown_content, extensions=['extra'])

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
        # Generate PDF using your preferred library (Puppeteer, WeasyPrint, etc.)
        pdf_base64 = await generate_pdf_from_markdown(
            request.markdownContent,
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

- The PDF should preserve all Markdown formatting including:
  - **Bold** and _italic_ text
  - Headings (h1-h6)
  - Lists (ordered and unordered)
  - Code blocks and inline code
  - Blockquotes
  - Links
  - Tables (if supported)
- Margins and page sizes are specified in inches
- Font sizes are in points (pt)
- The response should return base64-encoded PDF data without the `data:application/pdf;base64,` prefix
