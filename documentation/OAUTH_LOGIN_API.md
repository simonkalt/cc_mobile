# OAuth login API (Google & LinkedIn)

**Status:** Implemented (backend). Mobile client in `cc_mobile_ui` implements against this spec.

**Related:** [USER_API_DOCUMENTATION.md](./USER_API_DOCUMENTATION.md) (login response shape), [JWT_FRONTEND_IMPLEMENTATION.md](./JWT_FRONTEND_IMPLEMENTATION.md), [LINKEDIN_JOB_DATA_PHASE2.md](./LINKEDIN_JOB_DATA_PHASE2.md).

**Unchanged routes:** `POST /api/users/login`, `POST /api/users/register`, refresh-token, SMS/email verification, `PUT /api/users/{id}` (phone profile gate).

---

## Overview

Mobile uses **Authorization Code + PKCE** with the identity provider, then sends the code to this API. The server exchanges the code, validates tokens, finds/links/creates the user, and returns the **same JSON shape as password login**.

Secrets (`GOOGLE_CLIENT_SECRET`, `LINKEDIN_CLIENT_SECRET`) live **only** on the API server.

---

## Redirect URIs (register at Google / LinkedIn)

| Platform | Google | LinkedIn |
|----------|--------|----------|
| iOS / Android (native) | Authorize + exchange: `https://<API-host>/api/auth/oauth/google/callback`. Session return: HTTPS in Expo dev (`OAUTH_CALLBACK_DEEP_LINK=false`), else `ccmobile://oauth/google` (API 302) — see `GOOGLE_OAUTH_URI_CHECKLIST.md` | Same pattern for LinkedIn |
| Web (Expo `baseUrl` `/app`) | `{origin}/app/oauth/google` | `{origin}/app/oauth/linkedin` |

LinkedIn’s developer portal **does not accept custom URL schemes**; native apps use `GET /api/auth/oauth/linkedin/callback` on this API (see `app/api/routers/auth.py`).

Examples: UAT `https://cc-mobile-uat.onrender.com/api/auth/oauth/linkedin/callback`; production `https://www.saimonsoft.com/api/auth/oauth/linkedin/callback`.

---

## Server environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `GOOGLE_CLIENT_ID` | Yes | Web client ID used for code exchange (or platform-specific per your IdP setup) |
| `GOOGLE_CLIENT_SECRET` | Yes | Web client secret |
| `LINKEDIN_CLIENT_ID` | Yes | LinkedIn app (OIDC product) |
| `LINKEDIN_CLIENT_SECRET` | Yes | Server only |

Optional: separate Google iOS/Android client IDs if you validate `aud` per platform.

---

## MongoDB user document (additions)

| Field | Type | Notes |
|-------|------|-------|
| `authProviders` | array | `{ provider: "google"\|"linkedin", subject: string, linkedAt: ISO8601, emailFromProvider?: string }` |
| `passwordHash` | string \| null | `null` for OAuth-only users |
| `dataUseSharingNoticeAccepted` | boolean | Existing; required on OAuth **create** |
| `dataUseSharingNoticeAcceptedAt` | datetime | Existing audit field |

**Indexes (recommended):** unique sparse on `(authProviders.provider, authProviders.subject)` or dedicated `googleSub` / `linkedinSub` fields.

Do **not** expose raw `subject` to the client unless product requires it; return sanitized `authProviders` on `UserResponse` (see below).

---

## `POST /api/auth/oauth/google`

**Auth:** Public (no Bearer).

### Request

```json
{
  "code": "authorization_code_from_redirect",
  "redirect_uri": "https://cc-mobile-uat.onrender.com/api/auth/oauth/google/callback",
  "code_verifier": "pkce_verifier",
  "intent": "login",
  "dataUseSharingNoticeAccepted": true
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `code` | Yes | Authorization code |
| `redirect_uri` | Yes | Must match authorize step exactly |
| `code_verifier` | Yes | PKCE verifier |
| `intent` | No | `"login"` \| `"register"`. Default: link/login if user exists; create if new and register path allows |
| `dataUseSharingNoticeAccepted` | Conditional | **Required `true`** when creating a new user |

### Success `200 OK`

Same as [Login User](./USER_API_DOCUMENTATION.md#2-login-user):

```json
{
  "success": true,
  "message": "Login successful",
  "user": { },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "linkedProvider": "google"
}
```

| Field | Notes |
|-------|-------|
| `linkedProvider` | Optional. Set to `"google"` or `"linkedin"` when provider was **newly linked** to an existing account (auto-link). Omit on normal login. |

### Server logic

1. Exchange `code` + `code_verifier` at Google token endpoint.
2. Validate ID token (JWKS); read `sub`, `email`, `email_verified`, `name`, `picture`.
3. Find user by `(google, sub)` in `authProviders`.
4. Else find by normalized `email`:
   - If found and `email_verified` → append provider, set `linkedProvider`, return JWT.
   - If found and not verified → `409 link_not_allowed`.
5. Else if creating: require `dataUseSharingNoticeAccepted === true`, insert user with defaults (same as register), `phone: null`, no password.
6. Else `intent=login` and no user → `401` with `code: "user_not_found"`.
7. Update `lastLogin`; issue JWT.

---

## `POST /api/auth/oauth/linkedin`

**Auth:** Public.

Same request/response/error contract as Google, with provider `linkedin` and LinkedIn OIDC token/userinfo endpoints.

**Scopes at authorize (client):** `openid`, `profile`, `email`.

**LinkedIn + PKCE:** `code_verifier` is optional in the JSON body (omit for LinkedIn). **Do not** pass it to LinkedIn `POST /oauth/v2/accessToken`. Google still requires a non-empty `code_verifier`.

---

## `POST /api/auth/oauth/apple` (Sign in with Apple)

**Auth:** Public. **Status:** Implemented.

Native flow (no PKCE / browser code). The iOS client posts the identity token returned by `AppleAuthentication.signInAsync`; the server verifies it against Apple's JWKS and returns the same login JSON as Google/LinkedIn.

### Request

```json
{
  "identity_token": "eyJraWQi... (Apple JWT)",
  "authorization_code": "c1a2...",
  "apple_user": "001234.abcd...1234",
  "email": "user@example.com",
  "full_name": { "givenName": "Jane", "familyName": "Doe" },
  "intent": "login",
  "dataUseSharingNoticeAccepted": true
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `identity_token` | Yes | Apple JWT; the **only** trusted source of `sub`/`email`. |
| `authorization_code` | No | Currently unused server-side; reserved for refresh-token revocation checks. |
| `apple_user` | No | Apple stable user id (informational; `sub` is authoritative). |
| `email` | No | Untrusted; the token's `email` is used. Apple returns email in the token on first consent. |
| `full_name` | Conditional | Apple sends name **only on first authorization**; persisted as the display name on create. |
| `intent` | No | `login` \| `register`. |
| `dataUseSharingNoticeAccepted` | Conditional | Required `true` on new-user create. |

### Server logic

1. Verify token signature (RS256) against `https://appleid.apple.com/auth/keys`, with `iss == https://appleid.apple.com` and `aud == APPLE_OAUTH_CLIENT_ID` (defaults to the app bundle id `com.saimonsoft.customcoverlettermobile.app`).
2. Read `sub`, `email`, `email_verified` (Apple may send it as the string `"true"`).
3. Reuse the shared login path: find by `(apple, sub)`, else auto-link by verified email, else create (with `oauthRegistrationPending: true`). Same `authProviders`/error contract as Google/LinkedIn (`provider: "apple"`).

### Config

`APPLE_OAUTH_CLIENT_ID` (optional) overrides the audience; otherwise falls back to `APP_STORE_BUNDLE_ID`, then the default bundle id `com.saimonsoft.customcoverlettermobile.app`. On UAT, leave unset or set to that exact value so JWT `aud` matches the iOS app. iOS Simulator debugging: see `cc_mobile_ui/documentation/APPLE_SIGN_IN_SIMULATOR.md`.

---

## `POST /api/users/me/link-oauth/{provider}`

**Auth:** Bearer required. `{provider}` is `google` or `linkedin`. Apple uses a dedicated route, `POST /api/users/me/link-oauth/apple`, with the Apple identity-token body (same shape as the Apple login request, minus `intent`).

### Request

Same body as public OAuth routes (code, redirect_uri, code_verifier). Do **not** send `intent` for link; server links to JWT user.

### Success `200 OK`

```json
{
  "success": true,
  "user": { },
  "linkedProvider": "linkedin"
}
```

Does not re-issue tokens unless you choose to; client may keep existing session.

---

## `DELETE /api/users/me/link-oauth/{provider}`

**Auth:** Bearer required. `{provider}` is `google`, `linkedin`, or `apple` (same path as link; Apple does not need a separate route).

Removes that provider from `authProviders`. Success `200 OK` with updated `user` and optional `unlinkedProvider`.

### Errors

- `409 provider_not_linked`
- `409 last_signin_method` — no password and this is the user's only OAuth sign-in method

---

### Link errors (`POST`)

- `409 provider_already_linked` — this user already has that provider.
- `409 provider_sub_conflict` — `sub` belongs to another user.
- `409 link_not_allowed` — IdP email does not match account email (if strict mode enabled).

---

## Error responses

All errors should include a stable machine-readable `code` and human `message` / `detail`:

| HTTP | `code` | When |
|------|--------|------|
| 400 | `data_use_notice_required` | New user create without notice acceptance |
| 401 | `invalid_code` | Code exchange or token validation failed |
| 401 | `oauth_provider_misconfigured` | IdP rejected server credentials (e.g. LinkedIn `invalid_client`) |
| 401 | `oauth_not_configured` | Server missing OAuth client id/secret for provider |
| 401 | `user_not_found` | Login intent, no matching user |
| 403 | `inactive_account` | Same as password login |
| 409 | `link_not_allowed` | Cannot link (unverified email, mismatch, etc.) |
| 409 | `provider_already_linked` | Duplicate link attempt |
| 409 | `provider_sub_conflict` | Provider account tied to another user |

Example:

```json
{
  "detail": "An account with this email already exists. Sign in with your password or link from Settings.",
  "code": "link_not_allowed"
}
```

---

## `UserResponse` extensions (client-visible)

Add to user object returned on login/register/get:

```json
"authProviders": [
  { "provider": "google", "linkedAt": "2026-05-19T12:00:00.000Z" },
  { "provider": "linkedin", "linkedAt": "2026-05-20T08:00:00.000Z" }
]
```

Omit `subject` in API responses.

---

## Account linking rules (normative)

1. **Auto-link:** If IdP `email_verified` is true and email matches an existing user (case-insensitive), attach provider to that `id`. Do not create a duplicate. Return `linkedProvider`.
2. **Register intent + existing email:** Same as auto-link (sign-up or link), not `409` solely for duplicate email.
3. **New user:** Create only when no user matches; require `dataUseSharingNoticeAccepted: true`.
4. **Phone:** Leave `phone` null; client collects via `PUT /api/users/{id}`.

---

## curl examples

```bash
# OAuth login (after client obtains code via PKCE)
curl -s -X POST "$BASE/api/auth/oauth/google" \
  -H "Content-Type: application/json" \
  -d '{"code":"...","redirect_uri":"https://cc-mobile-uat.onrender.com/api/auth/oauth/google/callback","code_verifier":"...","intent":"login"}'

# Link LinkedIn while logged in
curl -s -X POST "$BASE/api/users/me/link-oauth/linkedin" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code":"...","redirect_uri":"ccmobile://oauth/linkedin","code_verifier":"..."}'
```

---

## Implementation checklist (backend)

- [x] Token exchange + JWKS validation (Google, LinkedIn)
- [x] `authProviders` persistence (indexes recommended in ops)
- [x] Auto-link on verified email
- [x] Register defaults (credits, personalities, `dataUseSharingNoticeAcceptedAt`)
- [x] Error `code` fields
- [ ] CORS allows mobile/web origins (configure per deployment)
