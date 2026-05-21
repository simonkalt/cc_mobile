# Google OAuth — URI and console checklist (login/register)

Use this for **Sign In with Google (OIDC + PKCE)** via `POST /api/auth/oauth/google`.  
See also `documentation/OAUTH_LOGIN_API.md` and `cc_mobile_ui/documentation/VENDOR_OAUTH_SETUP.md`.

---

## Do not put `ccmobile://` in Google Cloud

The **Web application** OAuth client’s **Authorized redirect URIs** field only accepts `https://` URLs (with a valid domain). Custom schemes such as `ccmobile://oauth/google` are **rejected** in the console.

Native apps use the same **HTTPS bridge** as LinkedIn:

1. Authorize with `redirect_uri` = `https://<API-host>/api/auth/oauth/google/callback`
2. Google redirects to that HTTPS URL with `?code=…`
3. API responds **302** → `ccmobile://oauth/google?…`
4. App receives the deep link and `POST`s the code with the **HTTPS** `redirect_uri`

---

## Root cause of `Error 400: invalid_request`

| Check | Fix |
|-------|-----|
| Wrong client ID on phone vs server | `EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` = API `GOOGLE_CLIENT_ID` (Web client) |
| Missing HTTPS callback in console | Register callback URLs below on the **Web** client |
| Consent screen in Testing | Add your Google account under **Test users** |
| UAT API not deployed with `/google/callback` | Deploy API; `curl -sI 'https://cc-mobile-uat.onrender.com/api/auth/oauth/google/callback?code=x'` should return **302** + `location: ccmobile://oauth/google?...` |

---

## Hosts (this project)

| Environment | API / web host |
|-------------|----------------|
| **UAT** | `https://cc-mobile-uat.onrender.com` |
| **Production** | `https://www.saimonsoft.com` |

`EXPO_PUBLIC_BACKEND_URL` on the build must match the environment you test.

---

## Copy into Google Cloud → Web application → Authorized redirect URIs

Register **all four** on the same Web client as `GOOGLE_CLIENT_ID`:

| Environment | Native (authorize + token exchange) | Web (Expo `/app` SPA) |
|-------------|-------------------------------------|------------------------|
| **UAT** | `https://cc-mobile-uat.onrender.com/api/auth/oauth/google/callback` | `https://cc-mobile-uat.onrender.com/app/oauth/google` |
| **Production** | `https://www.saimonsoft.com/api/auth/oauth/google/callback` | `https://www.saimonsoft.com/app/oauth/google` |

**Do not add** `ccmobile://oauth/google` — it cannot be saved on the Web client.

**Authorized JavaScript origins** (web): `https://cc-mobile-uat.onrender.com`, `https://www.saimonsoft.com` (no path).

---

## OAuth consent screen

1. APIs & Services → **OAuth consent screen** — app name, support email, privacy policy URL.
2. **Testing** mode: add test Google accounts or sign-in may be blocked.
3. Scopes: `openid`, `email`, `profile` only.

---

## Client ID must match on phone and server

| Location | Variable |
|----------|----------|
| Mobile `.env` / EAS | `EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` |
| API `.secrets` / Render | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |

---

## Android native rebuild

After `app.config.js` `intentFilters` changes, rebuild: `npx expo run:android`.

---

## Debug in Metro

```
[OAuth] google redirectUri (exchange): https://cc-mobile-uat.onrender.com/api/auth/oauth/google/callback
[OAuth] google sessionReturnUri: ccmobile://oauth/google
```

---

## Quick verify

1. Save the **two HTTPS** native callback URLs in Google Cloud (remove invalid `ccmobile://` entry).
2. Deploy UAT API with `GET /api/auth/oauth/google/callback`.
3. Rebuild app with `EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` and matching `EXPO_PUBLIC_BACKEND_URL`.
4. Sign in — browser should briefly hit the API callback, then return to the app.

LinkedIn: `LINKEDIN_OAUTH_URI_CHECKLIST.md`.

---

## Expo dev vs installed store app (same `ccmobile://` conflict)

If OAuth opens the **Play Store / App Store build** instead of your **Expo dev client**, both apps register the same deep link.

| Environment | Mobile `EXPO_PUBLIC_APP_SCHEME` | Render / API `OAUTH_NATIVE_APP_SCHEME` |
|-------------|--------------------------------|----------------------------------------|
| Expo dev + UAT | `ccmobile-dev` | `ccmobile-dev` |
| Production | `ccmobile` (default) | `ccmobile` (default) |

1. UAT Render → Environment → add `OAUTH_NATIVE_APP_SCHEME=ccmobile-dev`
2. `cc_mobile_ui/.env` → `EXPO_PUBLIC_APP_SCHEME=ccmobile-dev`
3. Rebuild dev client: `npx expo run:android` (manifest change)

Metro logs should show `sessionReturnUri: ccmobile-dev://oauth/google`. The store app does not handle `ccmobile-dev://`.

**Quick workaround without rebuild:** uninstall the store app while testing OAuth in Expo.
