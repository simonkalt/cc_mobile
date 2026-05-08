# API repo: app update policy & shipped version endpoints

This document is for the **FastAPI backend** (e.g. Render) that serves the mobile app (`cc_mobile_ui`). Implement the routes below so the Expo client can enforce **optional** (soft) and **required** (forced) updates. The mobile app **fails open**: if these endpoints are missing, erroring, or timing out, users are **never** blocked.

**Example router (file-based; replace reads with MongoDB):**  
[`scripts/fastapi_app_update_policy.example.py`](../scripts/fastapi_app_update_policy.example.py) — swap `_load_version_json()` for Atlas-backed reads.

---

## Source of truth: MongoDB Atlas (production)

**Live semver and update policy on Render must come from the database.** Updating [`version.json`](../version.json) or [`app.json`](../app.json) in `cc_mobile_ui` alone does **not** update what clients see until those values are written somewhere the API reads — committing a bump does not redeploy the API container.

| Location | Purpose |
|----------|---------|
| **Cluster** | Your Atlas cluster (e.g. named `CustomCoverLetter` in the UI). The name is **not** passed to the driver; the hostname lives in `MONGODB_URI`. |
| **Database** | `CoverLetter` |
| **Collection** | `version` |
| **Document** | The canonical document that carries mobile **version policy**, including the existing **`version`** field (semver) and any sibling fields needed for the JSON endpoints below. |

Resolve this document by whatever fits your schema (fixed `_id`, `kind: "app_version"`, etc.). Implementation detail stays in the API repo; mobile clients only consume HTTPS JSON.

---

## Requirements summary

| Requirement | Detail |
|-------------|--------|
| **Authentication** | Both routes MUST be **public** — no `Authorization` / JWT required. Align with existing public routes such as `GET /api/config/client-settings`. |
| **Latency** | Respond quickly; the client uses a **~10s** timeout on `app-update-policy`. Consider caching Mongo reads briefly if needed. |
| **Semantics** | Version fields MUST be **semver strings** (`major.minor.patch`), e.g. `2.3.0`, so they match `expo-application` / Play builds. |
| **Persistence** | **Primary:** Read semver/policy fields from the **`CoverLetter`** database, **`version`** collection (or override via `APP_UPDATE_POLICY_*` env vars). **Fallback:** Optional [`version.json`](../version.json) in the Docker image or env overrides — secondary only. |

---

## Suggested MongoDB document fields (`version` collection)

The HTTP APIs require more than a single semver string. Store whatever subset maps cleanly from your existing **`version`** field plus additions:

**Option A — single config document**

One document in the **`version`** collection (singleton `_id` or a stable query filter) with fields aligned to the APIs:

| Field (suggested) | Maps to API | Notes |
|-------------------|-------------|--------|
| `version` | `latest_version` (Layer B) and/or `version` (Layer A) | Existing semver string — primary “latest shipped”. |
| `min_required_version` | `min_required_version` | For forced updates. |
| `latest_version` | `latest_version` | Optional if redundant with `version`; otherwise derive `latest_version` from `version` in Python. |
| `update_message` | `update_message` | Optional |
| `store_android_url` | `store_android_url` | Default to Play URL server-side if missing |
| `store_ios_url` | `store_ios_url` | Nullable until App Store |
| `android_version_code` | `androidVersionCode` (Layer A) | Optional |
| `build_number` | `buildNumber` (Layer A) | Optional |

**Option B — minimal schema**

Keep **`version`** as today’s semver field only; map `version` → `latest_version` in route handlers and supply defaults / env fallbacks for `min_required_version` until fields are added.

---

## Endpoint 1: `GET /api/version` (Layer A — shipped artifact)

**Purpose:** Ops / debugging / “what semver does policy claim we ship?” Not used for gating logic on the client today.

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
| `version` | string \| null | Semver — prefer the policy document’s **`version`** field in the **`version`** collection. |
| `androidVersionCode` | number \| null | Android `versionCode` if stored |
| `buildNumber` | string \| null | Optional CI/build label |

**Source:** Read from the **`CoverLetter`.`version`** collection (canonical version document). Optional fallback: `version.json` on disk via `VERSION_JSON_PATH` only if Mongo misses optional fields.

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

**Source:** Built from **`CoverLetter`.`version`** (same canonical document as Layer A where possible). Env vars may override individual fields for emergencies.

**Client logic (summary):**

- `nativeVersion < min_required_version` → forced update.
- `nativeVersion >= min_required_version` and `nativeVersion < latest_version` → soft nudge.
- Invalid semver from API → client treats as **no gate** (fail-open).

---

## Environment variables (Render / Docker)

| Variable | Purpose |
|----------|---------|
| `MONGODB_URI` | **Primary:** Atlas connection string. Should resolve to database **`CoverLetter`** (path in URI or `MONGODB_DB_NAME`). |
| `APP_UPDATE_POLICY_DB_NAME` | Optional. If unset, uses the same database as the active connection (from URI / `MONGODB_DB_NAME`). Set if policy data lives in a different DB. |
| `APP_UPDATE_POLICY_COLLECTION` | Optional. Default in code: **`version`**. Override only if your collection name differs. |
| `APP_UPDATE_MIN_REQUIRED_VERSION` | Optional emergency override for minimum semver (bypasses DB field if set). |
| `APP_UPDATE_LATEST_VERSION` | Optional emergency override for latest semver. |
| `APP_UPDATE_MESSAGE` | Optional override for banner/message text. |
| `APP_UPDATE_STORE_ANDROID_URL` | Optional override; defaults to Play URL in code if unset. |
| `APP_UPDATE_STORE_IOS_URL` | Optional override; empty until App Store / HTTPS beta URL exists. |
| `VERSION_JSON_PATH` | **Optional fallback only:** path to baked [`version.json`](../version.json) when Atlas fields are absent or during migration. |

Prefer **MongoDB as truth**; use env overrides only for incidents or gradual rollout.

---

## Docker / deploy: `version.json` is optional

Baking [`version.json`](../version.json) into the image is **not** sufficient for live semver on Render — clients rely on **Atlas**.

Optional Dockerfile snippet if you still want a static fallback:

```dockerfile
# Optional fallback only — does not replace Mongo reads for production policy.
# COPY version.json /app/version.json
# ENV VERSION_JSON_PATH=/app/version.json
```

Ensure production reads **`CoverLetter`.`version`** first (unless overridden by env).

---

## Bump / release workflow (mobile repo + Atlas)

Preferred automation (future **Node or Python** script in CI or `cc_mobile_ui`):

1. Bump Expo **`app.json`**, **`package.json`**, and **[`version.json`](../version.json)** (e.g. `./bump.sh`).
2. **In the same release step**, write the same semver (and policy fields such as `latest_version` / `min_required_version` / `update_message`) into MongoDB Atlas **`CoverLetter`.`version`** so Render serves updated values immediately without redeploying only from git file bumps.

Until that automation exists, update Atlas manually or via admin tooling when you ship a store build.

---

## FastAPI integration

1. Implementation reads **`CoverLetter`.`version`** via PyMongo (see `app/services/app_version_policy_service.py`). See [`scripts/fastapi_app_update_policy.example.py`](../scripts/fastapi_app_update_policy.example.py) for pointers.
2. Register the router on your main app **without** requiring auth for these paths:

   ```python
   app.include_router(router)
   ```

3. Final paths must remain:

   - `/api/version`
   - `/api/config/app-update-policy`

4. Ensure **CORS** / middleware allow `GET` from mobile and web origins as for `/api/config/client-settings`.

---

## Testing

```bash
# Replace BASE with your API origin, e.g. https://cc-mobile-docker.onrender.com
curl -sS "${BASE}/api/version"
curl -sS "${BASE}/api/config/app-update-policy"
```

Expect `200` and JSON bodies matching the schemas above. No `Authorization` header.

**After updating** the canonical document in the **`version`** collection (including **`version`** and policy fields), **`curl` responses should reflect those DB values** — use this to verify reads before relying on clients.

---

## Operational notes

- **Forced updates:** Raising `min_required_version` in Atlas blocks old binaries after clients refresh policy (subject to client cache, typically ≤24h).
- **Soft updates:** Set `latest_version` (or map from **`version`**) above most installed versions while keeping `min_required_version` low for optional banners.
- **Android-first:** Production users use **Google Play** only for public installs today; keep `store_android_url` correct (default in handlers if DB omits it).
- **iOS:** TestFlight-only until App Store approval — nullable `store_ios_url` is expected.
