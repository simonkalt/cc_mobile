# Google OAuth — URI and console checklist (login/register)

Use this for **Sign In with Google (OIDC + PKCE)** via `POST /api/auth/oauth/google`.  
See also `documentation/OAUTH_LOGIN_API.md` and `cc_mobile_ui/documentation/VENDOR_OAUTH_SETUP.md`.

---

## Native app (Web client + HTTPS)

The **Web application** OAuth client is used on mobile (`EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` = API `GOOGLE_CLIENT_ID`).  
`redirect_uri` = `https://<API-host>/api/auth/oauth/google/callback` (must be in Google Cloud).  
The app closes the Custom Tab on that HTTPS URL; no `ccmobile://` is required for Google sign-in.

| Environment | API `OAUTH_CALLBACK_DEEP_LINK` | App `sessionReturnUri` |
|-------------|-------------------------------|-------------------------|
| Expo dev build (`__DEV__`) | **`false`** on UAT | HTTPS callback (same as `redirectUri`) |
| Release / Play Store | **`true`** (default) | `ccmobile://oauth/google` |

**Do not** use `ccmobile://` redirects with Expo development builds on Android — the dev launcher home screen opens instead of your app.

After changing Android `queries` for `ccmobile`, **rebuild** release APKs only (`npx expo run:android`).

---

## Root cause of `Error 400: invalid_request` / Authorization Error

| Check | Fix |
|-------|-----|
| `ccmobile://` in authorize URL | Mobile must use **HTTPS** callback URI (see `oauthRedirectUri.js`) |
| Wrong client ID on phone vs server | `EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` = API `GOOGLE_CLIENT_ID` |
| Missing HTTPS callback in console | Register callback URLs below on the **Web** client |
| Consent screen in Testing | Add your Google account under **Test users** |

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

## Expo dev vs Play Store app

Both use **`ccmobile://`**. Uninstall the Play Store app while testing a dev build from `npx expo run:android` (Expo Go does not support this OAuth flow).

Metro in **dev** should show the same URL for `redirectUri` and `sessionReturnUri` (HTTPS). On Render **UAT**, set `OAUTH_CALLBACK_DEEP_LINK=false` while testing with `npx expo run:android`. Production keeps the default `true` and `OAUTH_NATIVE_APP_SCHEME=ccmobile`.
