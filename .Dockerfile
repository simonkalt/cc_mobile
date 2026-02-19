# ---- Base image ----
FROM python:3.12-slim

# ---- Environment ----
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# ENV PORT=8000

# ---- System dependencies ----
# LibreOffice + PDF + WeasyPrint + Playwright deps
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    libreoffice-java-common \
    default-jre \
    fonts-dejavu \
    fonts-liberation \
    fonts-freefont-ttf \
    ghostscript \
    poppler-utils \
    chromium \
    chromium-driver \
    curl \
    ca-certificates \
    build-essential \
    libxml2 \
    libxslt1.1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libjpeg62-turbo \
    libffi-dev \
    libssl-dev \
    default-jre \ 
    && rm -rf /var/lib/apt/lists/*



# ---- Working directory ----
WORKDIR /app

# ---- Python deps first (layer caching) ----
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install chromium

# ---- App code ----
COPY . .

# ---- Expose port ----
EXPOSE 8000

# ---- Run FastAPI ----
# CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port $PORT"]
