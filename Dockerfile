# Python app with LibreOffice (for docx→PDF) and Playwright (for HTML→PDF).
# Use this for local Docker and for Render when you need docx-to-pdf.
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install LibreOffice (for POST /api/files/docx-to-pdf) and deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Ensure soffice is on PATH (Debian packages put it in /usr/bin)
ENV PATH="/usr/bin:${PATH}"

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Playwright Chromium (for HTML print preview when used)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
RUN python -m playwright install chromium || true

# App code
COPY . .

# Render sets PORT; default 8000 for local
ENV PORT=8000
EXPOSE $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
