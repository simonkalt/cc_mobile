# Frontend Impact: JWT Interop Update

This document explains whether frontend changes are required after adding JWT `iss` and `aud` support for Python <-> .NET service interop.

## Short Answer

For the existing frontend auth flow, **no breaking change** is required.

The login and refresh API response shapes are unchanged:
- `access_token`
- `refresh_token`
- `token_type`

The backend now includes additional standard claims (`iss`, `aud`) inside JWTs when configured, which does not break normal token storage or bearer usage.

## What Frontend Should Do

1. **Keep current login flow** as-is.
2. **Keep sending bearer token** as-is:
   - `Authorization: Bearer <access_token>`
3. **Ensure refresh flow remains active** using `/api/users/refresh-token`.
4. **Trigger a fresh login after rollout** so users receive tokens that include `iss` and `aud`.

## Optional Frontend Improvements

If frontend decodes JWT payload locally (for diagnostics/UI), ensure it:
- does not fail when new claims (`iss`, `aud`) are present
- does not depend on exact claim set beyond required fields used by the app

## For Calls to External .NET Service

If the frontend calls the .NET service directly with the same bearer token:
- keep forwarding the backend-issued access token unchanged
- do not rewrite token contents client-side

If the Python backend proxies calls to .NET, no frontend change is needed for forwarding.

## Rollout Checklist (Frontend + Backend)

1. Backend sets:
   - `JWT_SECRET`
   - `JWT_ISSUER`
   - `JWT_AUDIENCE`
2. .NET sets matching values.
3. Initially keep strict issuer/audience validation disabled in .NET (if needed).
4. Frontend prompts re-login (or natural token refresh/login cycle).
5. Enable strict .NET issuer/audience validation after confirming live tokens include matching `iss` and `aud`.

## Troubleshooting

- Users authenticated before rollout may have tokens without `iss`/`aud`.
  - Fix: re-login to mint fresh tokens.
- `401` from .NET with `invalid issuer` or `invalid audience`.
  - Verify `.NET` values exactly match Python-issued claims.
- `401 invalid signature`.
  - Verify both services use the same shared `JWT_SECRET`.

## Copy/Paste Frontend Examples

### Axios interceptor (attach access token)

```javascript
import axios from "axios";

const dotnetApi = axios.create({
  baseURL: process.env.REACT_APP_DOTNET_API_BASE_URL,
});

dotnetApi.interceptors.request.use((config) => {
  const accessToken = localStorage.getItem("access_token");
  if (accessToken) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

export default dotnetApi;
```

### Fetch wrapper (attach access token)

```javascript
export async function dotnetFetch(path, options = {}) {
  const baseUrl = process.env.REACT_APP_DOTNET_API_BASE_URL;
  const accessToken = localStorage.getItem("access_token");
  const body = options.body;
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const headers = new Headers(options.headers || {});
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  // Important: do not force Content-Type for FormData.
  // Browser must set multipart boundary automatically.
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });
}
```

### 401 retry pattern with refresh token

Use this only if your app already supports refresh. Keep retry count to one attempt to avoid loops.
Only auto-retry backend-auth API calls that are safe to replay.
Do not auto-retry non-idempotent uploads/saves (for example DOCX upload/save) unless you have idempotency keys or duplicate guards.

```javascript
async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("refresh_token");
  const resp = await fetch("/api/users/refresh-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) throw new Error("Refresh failed");
  const data = await resp.json();
  localStorage.setItem("access_token", data.access_token);
  return data.access_token;
}

export async function dotnetFetchWithRetry(path, options = {}, retryPolicy = { allow: false }) {
  let response = await dotnetFetch(path, options);
  if (response.status !== 401) return response;
  if (!retryPolicy.allow) return response;

  const newAccessToken = await refreshAccessToken();
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${newAccessToken}`);
  const body = options.body;
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return dotnetFetch(path, { ...options, headers });
}
```

