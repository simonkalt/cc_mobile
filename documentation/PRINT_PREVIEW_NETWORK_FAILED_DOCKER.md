# Print Preview (PDF) "Network Request Failed" When Server Runs in Docker

When the client gets **"Network Request Failed"** calling the Print Preview / docx-to-PDF endpoint (`POST /api/files/docx-to-pdf`) while the **server is running in Docker**, the request often never reaches the server or the response never reaches the client. Below are the most likely causes and how to fix them.

---

## 1. Client is using the wrong API URL (most common)

**Symptom:** Other API calls (e.g. generate cover letter) may work from the same machine as Docker, but Print Preview fails; or all requests fail when the client runs on a **different device** (e.g. phone, another PC).

**Cause:** The client is still using `http://localhost:8000` (or `http://127.0.0.1:8000`). From the browser’s point of view, "localhost" is the **device where the app is running**. So:

- On the **same machine** as Docker: `localhost` can work if the container port is published (e.g. `-p 8000:8000`).
- On a **phone or another PC**: `localhost` is that device, not the host running Docker, so the connection fails → "Network Request Failed".

**Fix:**

- Run Docker with the port **published** to the host, e.g.:
  ```bash
  docker run -p 8000:8000 ...
  ```
- From another device (phone, other PC), the client must use the **host’s IP** (or hostname) and that port, e.g.:
  - `http://192.168.1.100:8000` (replace with your host’s LAN IP).
- Ensure the app’s API base URL is configurable (e.g. env or config) and set to that URL when testing from another device.

---

## 2. CORS: client origin not allowed

**Symptom:** Request shows in the browser’s Network tab as blocked or "CORS error"; or you see a CORS error in the console. Sometimes the browser surfaces this as a generic "Network Request Failed".

**Cause:** The server only allows requests from origins listed in `CORS_ORIGINS`. Defaults include `http://localhost:3000`, `http://localhost:3001`, `http://127.0.0.1:3000`, `http://127.0.0.1:3001`. If the client runs at a different origin (e.g. `http://192.168.1.5:3000`, or a Capacitor/WebView origin), the browser blocks the request.

**Fix:**

- Set the **exact** client origin (protocol + host + port, no trailing slash) in the server’s environment, e.g. in Docker:
  ```bash
  docker run -e CORS_ORIGINS="http://192.168.1.5:3000,http://localhost:3000" -p 8000:8000 ...
  ```
- Or in `.env` / Render (or your host env) used when starting the container:
  ```env
  CORS_ORIGINS=http://192.168.1.5:3000,http://localhost:3000
  ```
- Restart the container after changing env. See `documentation/CORS_EXPLANATION.md` for more scenarios.

---

## 3. Request or conversion timeout

**Symptom:** Request hangs then fails with "Network Request Failed"; server logs may show the docx-to-pdf conversion completing after the client has already given up.

**Cause:** Docx→PDF uses LibreOffice (`soffice`) and can take **10–120 seconds** for larger documents. The client (or a reverse proxy in front of the server) may use a timeout shorter than that.

**Fix:**

- **Client:** Increase the timeout for the Print Preview request (e.g. 90–120 seconds). Do not use a very short timeout (e.g. 5–10 s) for this endpoint.
- **Reverse proxy (nginx, etc.):** If the API is behind nginx (or similar), increase proxy read/timeout for this location (e.g. 120 s).
- **Server:** The backend already uses a 120 s timeout for the LibreOffice subprocess; no change needed there unless you want to raise it further.

---

## 4. Docker port not published

**Symptom:** From the host machine, `curl http://localhost:8000/api/health` fails when the server runs in Docker.

**Cause:** The container’s port was not published to the host, so nothing outside the container can reach the app.

**Fix:**

- Publish port 8000 (or whatever `PORT` the app uses) when running the container:
  ```bash
  docker run -p 8000:8000 your-image
  ```
- With docker-compose, expose the port on the host:
  ```yaml
  ports:
    - "8000:8000"
  ```

---

## 5. Authentication (401) reported as "Network Request Failed"

**Symptom:** Server returns 401 Unauthorized; the client might show it as "Network Request Failed" if it doesn’t handle 4xx clearly.

**Cause:** `POST /api/files/docx-to-pdf` is protected by `get_current_user` (JWT). Missing or invalid `Authorization` header causes 401.

**Fix:**

- Ensure the client sends the same auth used for other API calls (e.g. `Authorization: Bearer <token>`).
- If the client only shows a generic "Network Request Failed", check the **Network** tab for the real status (e.g. 401) and add better error handling for 4xx/5xx.

---

## 6. LibreOffice not available in the container (503)

**Symptom:** Server returns **503** with a message like "LibreOffice (soffice) is not installed on the server." The client may surface this as "Network Request Failed" if it doesn’t distinguish error responses.

**Cause:** The image used for the container doesn’t include LibreOffice, or `soffice` is not on `PATH`.

**Fix:**

- Use the project’s **Dockerfile** (or an image derived from it), which installs `libreoffice-writer` and exposes `soffice` on `PATH`.
- If you use a different image, install LibreOffice and ensure `soffice` is available in the container, e.g.:
  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer
  ```

---

## Quick checklist

| Check | Action |
|-------|--------|
| **API URL** | From phone/other device, use host IP (e.g. `http://192.168.1.100:8000`), not `localhost`. |
| **CORS** | Add the client’s origin (e.g. `http://192.168.1.5:3000`) to `CORS_ORIGINS` and restart the container. |
| **Port** | Run Docker with `-p 8000:8000` (or your `PORT`). |
| **Timeout** | Use at least 90–120 s for the Print Preview request (and proxy if applicable). |
| **Auth** | Send a valid JWT in `Authorization` for `POST /api/files/docx-to-pdf`. |
| **LibreOffice** | Use the Dockerfile that installs `libreoffice-writer` so `soffice` is available. |

---

## Debugging

1. **Browser DevTools → Network:** Inspect the failing request: URL, status (e.g. 0 = connection failed, 401, 503), and any CORS or timeout messages.
2. **Server logs:** Confirm whether the request hits the server and whether docx-to-pdf runs (or times out / 503).
3. **From host:** `curl -v -X POST http://localhost:8000/api/files/docx-to-pdf -F "file=@test.docx" -H "Authorization: Bearer YOUR_JWT"` to verify the endpoint and auth when the server is in Docker.
