# Google OAuth — URI and console checklist (login/register)

Use this for **Sign In with Google (OIDC + PKCE)** via `POST /api/auth/oauth/google`.  
See also `documentation/OAUTH_LOGIN_API.md` and `cc_mobile_ui/documentation/VENDOR_OAUTH_SETUP.md`.

---

## Native app (restored flow — `ccmobile://`)

The mobile app uses **platform OAuth clients** and `redirect_uri` = `ccmobile://oauth/google` (via `promptAsync`, not an HTTPS bridge).

| Platform | Mobile env | Google Cloud client type |
|----------|------------|---------------------------|
| Android | `EXPO_PUBLIC_GOOGLE_OAUTH_ANDROID_CLIENT_ID` | Android OAuth client — add custom URI scheme / redirect as documented for that client type |
| iOS | `EXPO_PUBLIC_GOOGLE_OAUTH_IOS_CLIENT_ID` | iOS OAuth client |
| Web | `EXPO_PUBLIC_GOOGLE_OAUTH_WEB_CLIENT_ID` | Web application — **https://** redirect URIs only (table below) |

Server `POST /api/auth/oauth/google` still exchanges the code; `redirect_uri` in the request body must match what the app used (`ccmobile://oauth/google` on native).

LinkedIn native still uses the **HTTPS bridge** (`/api/auth/oauth/linkedin/callback` → 302 → `ccmobile://oauth/linkedin`).

---

## Root cause of `Error 400: invalid_request`

| Check | Fix |
|-------|-----|
| Using Web client ID on Android with `ccmobile://` | Use **Android** (or iOS) client ID in `.env`, not Web-only |
| Missing redirect on Android/iOS client | Register `ccmobile://oauth/google` on the matching platform client |
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

Metro should show `redirectUri: ccmobile://oauth/google` for Google. On Render UAT, remove `OAUTH_NATIVE_APP_SCHEME=ccmobile-dev` if it is still set (default `ccmobile` is fine for LinkedIn’s 302).
