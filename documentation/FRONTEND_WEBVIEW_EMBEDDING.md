# Frontend / WebView embedding

## Division of responsibility

| Layer | Who owns it | Role |
| ----- | ------------ | ---- |
| **Host app** (Expo / React Native / native WebView) | Your frontend | Gives the WebView a **real width and height** (including after rotation). Your team’s own doc covers `onLayout`, explicit dimensions, `injectJavaScript` resize nudges, etc. |
| **This page** (`editor.html` + `editor.js`) | DOCX service | Uses **100% width/height** and a **flex column** so the Syncfusion control **fills that WebView**. Listens for resize/orientation/visualViewport and calls Syncfusion `resize(w, h)` on `#editorContainer`. |

If `#editorContainer` ends up with **0×0** pixels, the editor cannot paint. That is almost always a **host sizing** issue; this page still does everything below so that *when* the WebView has size, we use all of it.

---

## What `editor.html` guarantees (fill the container)

- **`html`, `body`:** `width: 100%`, `height: 100%`, `overflow: hidden` — no stray margins; the document matches the WebView’s content box.
- **`#editorShell`:** column flex, `width: 100%`, `min-width: 0`, `min-height: 0`, height `100vh` / **`100dvh`** (dynamic viewport), `max-height: 100%` — shell fills the body and can shrink inside flex parents.
- **`#formatToolbar`:** `flex-shrink: 0` — fixed chrome height; does not steal flex space from the document incorrectly.
- **`#editorPane`:** `flex: 1 1 auto`, `width: 100%`, **`min-width: 0`**, **`min-height: 0`**, column flex — the document area gets all remaining vertical space; `min-*` avoids the flex “zero-height child” trap.
- **`#editorContainer`:** same flex + `min-width` / `min-height` + `position: relative` — Syncfusion mounts here; this is the box whose `clientWidth` / `clientHeight` drive `resize()`.
- **Landscape:** toolbar stays one row with horizontal scroll so more vertical space stays for the document.

**`editor.js`:** creates `DocumentEditor` with `height: "100%"`, `width: "100%"`, `appendTo("#editorContainer")`, sets component **`width` / `height`** in px when resizing, calls Syncfusion **`resize(w, h)`**, uses a **`ResizeObserver`** on `#editorContainer` so rotation/layout updates after the DOM has real dimensions (avoids a narrow document while the toolbar is already wide), and listens for **`resize`**, **`orientationchange`** (delayed), and **`visualViewport` `resize`**.

**`body.mobile-mode` (narrow “phone frame”):** applied when viewport width ≤768px and not overridden by URL. It sets `max-width: 420px`, centered shell, padding, and the visible **border**—fine in portrait, wrong in landscape if the class never updates. **`editor.js` re-applies this on `resize` / `orientationchange` / `visualViewport` resize** so rotating to a wide width clears `mobile-mode`. **CSS:** in **landscape**, `.mobile-mode #editorShell` is forced to **full width** with **no border/padding** so the editor fills the WebView even if `mobile-mode` were briefly stale.

**Embedded full-bleed everywhere:** add **`layout=fullscreen`** or **`mobile_mode=0`** to skip the phone frame in portrait too.

---

## Optional: `ReactNativeWebView` messages

| `type` | When |
| ------ | ---- |
| `docx_saved` | After a successful save (if the bridge exists). |
| `pdf_share_done` | After Share-as-PDF completes (same as before). |
| `share_pdf_export` | **Opt-in only** (`?host_pdf_share=1` on `editor.html`). Delivers PDF + export URLs/headers for the **host** to share natively (not `location.href`). |

## Share as PDF

**Update:** PDF creation is handled by the **Syncfusion (.NET)** stack, not by `POST /api/files/docx-to-pdf` on this Python API (that route returns **410 Gone**). See **`PDF_SERVER_SIDE_REMOVED.md`**.

Historical notes: **`DOCX_TO_PDF_API.md`** and **`THIRD_PARTY_SERVICE_AUTH.md`** described the old Python conversion path. If your host still proxies PDF work, point it at your **.NET / Syncfusion** service rather than the FastAPI docx-to-pdf endpoint.

### Integration auth from frontend (recommended pattern)

If the external DOCX/PDF service requires integration authentication (shared secret), use this pattern:

1. **Frontend/WebView calls your host or .NET PDF service** (not the disabled Python `docx-to-pdf` route).
2. **Host service** applies integration auth or forwards to the **Syncfusion** pipeline as your architecture defines.
3. Return the PDF or share payload to the frontend.

This keeps `SERVICE_AUTH_KEY` out of JavaScript, app bundles, and device logs.

**Do not send `SERVICE_AUTH_KEY` directly from the frontend/WebView.**

#### Frontend detection/behavior

- Read `GET /api/config`.
- If `pdfShareViaProxy: true`, send the DOCX to your same-origin proxy endpoint only.
- If proxy mode is unavailable, use direct API mode with user token (`access_token`) and without service key.

#### Required identifier/parameter for host service

If your host service now requires an explicit marker that traffic is coming from this app, include a stable request identifier from the frontend (for example `source=cc_mobile` as query param, or `X-Client-App: cc_mobile` header), and let the host service enforce it.

- Frontend sends marker to **host service**.
- Host service validates marker + user/session context.
- Host service then forwards with `X-Service-Auth` server-side.

This marker is not a secret; it is only a routing/policy signal.

### Optional: host-owned share (no change to default behavior)

**Default (no flags, no hook):** unchanged — WebView runs **`navigator.share`** with the PDF file, or download fallback, then **`pdf_share_done`**.

**`window.__ccDocxSharePdfFromApi(payload)`** (assigned by the host, e.g. via `injectJavaScript`): if present, it is called after the PDF is ready with:

- **`pdfBase64`**, **`fileName`**, **`mimeType`**
- **`export`**: **`mode`** (`proxy` \| `direct`), **`pdfPostUrl`**, **`docxSaveUrl`** (absolute URLs for the same requests the page uses)
- **`requestHeaders`**: e.g. **`Authorization`** when the page sent a Bearer token (same values the WebView would use)

If the function returns **`true`** or **`{ handled: true }`** (sync or Promise), the page **skips** `navigator.share` / download (host handles UX). Otherwise the usual in-page share runs.

**Query (embedded `editor.html` only):**

- **`host_pdf_share=1`** — also **`postMessage`** JSON with **`type: "share_pdf_export"`** and the same payload fields (for RN listeners).
- **`host_skip_webview_share=1`** — only with **`host_pdf_share=1`** and when **`ReactNativeWebView`** exists: skip in-WebView share/download so the native layer must share (avoid using skip without handling **`share_pdf_export`**).

## Further reading

- **`SYNCFUSION_INTEGRATION.md`** — session, JWT, APIs.  
- **`DOCX_TO_PDF_API.md`** — PDF conversion.  
- **`JWT_DOTNET_INTEROP.md`** / **`FRONTEND_JWT_INTEROP_IMPACT.md`** — auth.
