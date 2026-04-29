# API repo: app update policy & shipped version endpoints

This document is for the **FastAPI backend** (e.g. Render) that serves the mobile app (`cc_mobile_ui`). Implement the routes below so the Expo client can enforce **optional** (soft) and **required** (forced) updates. The mobile app **fails open**: if these endpoints are missing, erroring, or timing out, users are **never** blocked.

**Reference implementation (copy-paste starting point):**  
[`scripts/fastapi_app_update_policy.example.py`](../scripts/fastapi_app_update_policy.example.py) in this repo.

---

## Requirements summary

| Requirement | Detail |
|-------------|--------|
| **Authentication** | Both routes MUST be **public** — no `Authorization` / JWT required. Align with existing public routes such as `GET /api/config/client-settings`. |
| **Latency** | Respond quickly; the client uses a **~10s** timeout on `app-update-policy`. |
| **Semantics** | Version fields MUST be **semver strings** (`major.minor.patch`), e.g. `2.3.0`, so they match `expo-application` / Play builds. |
| **Shipped metadata** | Optionally ship [`version.json`](../version.json) from the mobile repo in the API Docker image so Layer A is accurate without a database. |

---

## Endpoint 1: `GET /api/version` (Layer A — shipped artifact)

**Purpose:** Ops / debugging / “what semver did we deploy with this API revision?” Not used for gating logic on the client today; safe to add first.

**Response:** `200` `application/json`

```json
{
  "version": "2.3.0",
  "androidVersionCode": 2300,
  "buildNumber": null
}
```

| Field | Type | Notes |
|-------|------|--------|
| `version` | string \| null | Semver from `version.json` |
| `androidVersionCode` | number \| null | Android `versionCode` |
| `buildNumber` | string \| null | Optional CI/build label |

**Source:** Read [`version.json`](../version.json) at startup or per request from path `VERSION_JSON_PATH` (see env vars).

---

## Endpoint 2: `GET /api/config/app-update-policy` (Layer B — update gate)

**Purpose:** Drive **forced** vs **recommended** update UI on native Android/iOS.

**Response:** `200` `application/json`

```json
{
  "min_required_version": "2.1.0",
  "latest_version": "2.3.0",
  "update_message": "Critical security fix — please update.",
  "store_android_url": "https://play.google.com/store/apps/details?id=com.saimonsoft.customcoverlettermobile.app",
  "store_ios_url": null
}
```

| Field | Type | Notes |
|-------|------|--------|
| `min_required_version` | string | Semver. Clients **below** this see a **blocking** update screen (Android: open Play). |
| `latest_version` | string | Semver. Clients **>= min** but **< latest** see a **dismissible** banner. |
| `update_message` | string \| null | Optional copy for modal/banner. |
| `store_android_url` | string | **Required for production Android UX.** Default: [Google Play listing](https://play.google.com/store/apps/details?id=com.saimonsoft.customcoverlettermobile.app) (`com.saimonsoft.customcoverlettermobile.app`). |
| `store_ios_url` | string \| null | **Optional until App Store approval.** Use `null` or omit; TestFlight users may rely on app env `EXPO_PUBLIC_TESTFLIGHT_URL`. Do not invent a fake `apps.apple.com` URL. |

**Client logic (summary):**

- `nativeVersion < min_required_version` → forced update.
- `nativeVersion >= min_required_version` and `nativeVersion < latest_version` → soft nudge.
- Invalid semver from API → client treats as **no gate** (fail-open).

---

## Environment variables (Render / Docker)

| Variable | Purpose |
|----------|---------|
| `VERSION_JSON_PATH` | Absolute path to `version.json` inside the container, e.g. `/app/version.json`. |
| `APP_UPDATE_MIN_REQUIRED_VERSION` | Override minimum semver (when unset, example router may fall back to `version` from `version.json`). |
| `APP_UPDATE_LATEST_VERSION` | Override “latest” semver (when unset, example may fall back to shipped `version`). |
| `APP_UPDATE_MESSAGE` | Optional message string. |
| `APP_UPDATE_STORE_ANDROID_URL` | Optional; defaults to Play URL above. |
| `APP_UPDATE_STORE_IOS_URL` | Optional; leave empty until you have a real App Store or HTTPS beta URL. |

You can later replace env-only policy with a **DB row** (e.g. Supabase) while keeping the same JSON shape.

---

## Docker / deploy: include `version.json`

Copy the file from the mobile monorepo build artifact or pinned tag:

```dockerfile
COPY version.json /app/version.json
ENV VERSION_JSON_PATH=/app/version.json
```

Regenerate `version.json` when you release app builds using `./bump.sh` in `cc_mobile_ui` so backend metadata stays aligned with `app.json`.

---

## FastAPI integration

1. Copy or adapt [`scripts/fastapi_app_update_policy.example.py`](../scripts/fastapi_app_update_policy.example.py).
2. Register the router on your main app **without** requiring auth for these paths:

   ```python
   app.include_router(router)
   ```

3. If your app mounts routers under a global prefix, ensure the final paths are exactly:

   - `/api/version`
   - `/api/config/app-update-policy`

4. Ensure existing **CORS** / middleware allow `GET` from mobile and web origins as you already do for `/api/config/client-settings`.

---

## Testing

```bash
# Replace BASE with your API origin, e.g. https://cc-mobile-docker.onrender.com
curl -sS "${BASE}/api/version"
curl -sS "${BASE}/api/config/app-update-policy"
```

Expect `200` and JSON bodies matching the schemas above. No `Authorization` header.

---

## Operational notes

- **Forced updates:** Raising `min_required_version` blocks old binaries immediately after clients refresh policy (subject to client cache, typically ≤24h).
- **Soft updates:** Set `latest_version` above most installed versions but keep `min_required_version` low for optional banners.
- **Android-first:** Production users use **Google Play** only for public installs today; keep `store_android_url` correct.
- **iOS:** TestFlight-only until App Store approval — nullable `store_ios_url` is expected.
