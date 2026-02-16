# LibreOffice setup (for docx→PDF)

The **POST /api/files/docx-to-pdf** endpoint needs LibreOffice (`soffice`) on the machine where the API runs. Use one of the approaches below depending on where you run the app.

---

## 1. Local development (no Docker)

Install LibreOffice with your OS package manager so `soffice` is on your PATH.

| OS | Command |
|----|--------|
| **Ubuntu / Debian** | `sudo apt-get update && sudo apt-get install -y libreoffice-writer` |
| **macOS** | `brew install --cask libreoffice` |
| **Windows** | Download and install from [libreoffice.org](https://www.libreoffice.org/download/download/). Ensure the install directory is on PATH, or the app looks for `soffice.exe`. |

Check:

```bash
soffice --version
```

---

## 2. Local Docker

The repo **Dockerfile** already installs LibreOffice in the image. Build and run:

```bash
docker build -t cover-letter-api .
docker run -p 8000:8000 --env-file .env cover-letter-api
```

No extra steps; LibreOffice is in the container.

---

## 3. Render (deploy)

Render’s **native Python** runtime does not let you install system packages like LibreOffice. To have LibreOffice on Render you must run the app in **Docker**.

### Use the Dockerfile on Render

1. In the [Render Dashboard](https://dashboard.render.com), open your **Web Service**.
2. Go to **Settings**.
3. Set **Environment** to **Docker** (not “Python 3”).
4. Leave **Dockerfile Path** blank if your Dockerfile is in the repo root (Render will use it automatically).
5. **Docker Command** (optional): leave empty to use the Dockerfile `CMD`, or set e.g.:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Save. Redeploy.

Render will build the image from the Dockerfile (which installs LibreOffice) and run the app. The docx-to-pdf endpoint will work.

### If you stay on native Python on Render

- You **cannot** install LibreOffice in the build or runtime.
- **POST /api/files/docx-to-pdf** will return **503** (“LibreOffice is not installed”).
- Use **Docker** (above) if you need docx-to-pdf on Render.

---

## Summary

| Where you run | How LibreOffice is available |
|---------------|------------------------------|
| **Local (no Docker)** | Install via apt / Homebrew / Windows installer. |
| **Local (Docker)** | Use the repo Dockerfile; it’s already in the image. |
| **Render** | Deploy as **Docker** and use the repo Dockerfile; native Python cannot install LibreOffice. |
