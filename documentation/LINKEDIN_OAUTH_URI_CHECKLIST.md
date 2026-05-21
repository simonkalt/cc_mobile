# LinkedIn OAuth — URI and portal checklist (login/register)

Use this for **Sign In with LinkedIn (OIDC)** via `POST /api/auth/oauth/linkedin`.  
It is **not** the job-library 3-legged flow (`LINKEDIN_REDIRECT_URI` → `/api/linkedin/callback`).

---

## Two different LinkedIn flows (do not mix)

| Flow | Who opens LinkedIn | Redirect URI in portal | Server env |
|------|-------------------|------------------------|------------|
| **Login / register / link** | Mobile app (`expo-auth-session`) | HTTPS URLs below (portal rejects `ccmobile://`) | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` in `.secrets` |
| **Job library (optional)** | Browser via `GET /api/linkedin/auth-url` | Whatever you set as `LINKEDIN_REDIRECT_URI` (e.g. `https://api…/api/linkedin/callback`) | Same client id/secret + `LINKEDIN_REDIRECT_URI`, `LINKEDIN_SCOPE` |

URI mismatch on login almost always means the **first row** URLs are missing or spelled differently in the LinkedIn Developer Portal.

---

## Hosts (this project)

| Environment | API / web host |
|-------------|----------------|
| **UAT** | `https://cc-mobile-docker.onrender.com` |
| **Production** | `https://www.saimonsoft.com` |

`EXPO_PUBLIC_BACKEND_URL` on mobile builds must match the environment you are testing.

---

## Copy into LinkedIn → Auth → Authorized redirect URLs

Register **all four** (one LinkedIn app can list multiple). LinkedIn only allows `http://` or `https://`.

| Environment | Native (iOS/Android) | Web (`/app` SPA) |
|-------------|-------------------|------------------|
| **UAT** | `https://cc-mobile-docker.onrender.com/api/auth/oauth/linkedin/callback` | `https://cc-mobile-docker.onrender.com/app/oauth/linkedin` |
| **Production** | `https://www.saimonsoft.com/api/auth/oauth/linkedin/callback` | `https://www.saimonsoft.com/app/oauth/linkedin` |

Native flow: LinkedIn → HTTPS callback (page stays on that URL with `?code=…`) → Expo closes the browser tab and returns the code to the app → `POST /api/auth/oauth/linkedin`.  
Do **not** 302 to `ccmobile://` on the callback; that prevents `openAuthSessionAsync` from completing on Android/iOS.

**Local `http://192.168.x.x:8675` will not work** in the LinkedIn portal. For device testing, point `EXPO_PUBLIC_BACKEND_URL` at your public HTTPS API host, or use an HTTPS tunnel (ngrok, etc.).

---

## LinkedIn Developer Portal steps

1. [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) → your app.
2. **Products** → enable **Sign In with LinkedIn using OpenID Connect** (required for login; different from Marketing/Ads products).
3. **Auth** tab:
   - **Authorized redirect URLs:** paste the four URLs from the table above.
   - Do **not** put only `LINKEDIN_REDIRECT_URI` here unless you also use the job callback flow — that URL is for `/api/linkedin/callback`, not mobile login.
4. Scopes used by the app: `openid`, `profile`, `email` (OIDC).

---

## Client ID must match on phone and server

| Location | Variable |
|----------|----------|
| Mobile `.env` / EAS | `EXPO_PUBLIC_LINKEDIN_CLIENT_ID` |
| API `.secrets` / Render Secret File | `LINKEDIN_CLIENT_ID` |

They must be the **same LinkedIn application** Client ID. The server secret (`LINKEDIN_CLIENT_SECRET`) is only on the API.

**Render:** Secret File `.secrets` must include `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` (not only commented placeholders in `.env`).

**EAS production:** `eas.json` currently sets `EXPO_PUBLIC_LINKEDIN_CLIENT_ID` to `""` for the `production` profile — production builds will fail LinkedIn login until you set the real ID in EAS env or `eas.json`.

---

## How to see the exact redirect URI (web / ambiguous cases)

In `cc_mobile_ui`, temporarily log before `promptAsync`:

```js
console.log("LinkedIn redirectUri:", redirectUri);
```

Run the app on the **same platform** you are debugging, tap LinkedIn sign-in, and copy the string from Metro/logs. Add **that** string to Authorized redirect URLs.

Native redirect URI is built in `cc_mobile_ui/src/utils/oauthRedirectUri.js` as  
`{EXPO_PUBLIC_BACKEND_URL or dev default}/api/auth/oauth/linkedin/callback`.  
The deep link `ccmobile://oauth/linkedin` is only used **after** the HTTPS bridge redirect.

---

## Verify UAT/prod deploy (before testing on a phone)

```bash
# Must return HTTP/2 200 (HTML body), not {"detail":"Not Found"}
curl -sI "https://cc-mobile-docker.onrender.com/api/auth/oauth/linkedin/callback" | head -1

curl -s "https://cc-mobile-docker.onrender.com/openapi.json" | grep -o '"/api/auth/oauth[^"]*"' | sort -u
```

Expected after a good deploy: `/api/auth/oauth/google`, `/api/auth/oauth/linkedin`, `/api/auth/oauth/linkedin/callback`.

If the callback is **404**, Render is still on an **old build** or the **auth router failed to import** (service logs: `Auth router NOT registered`). The route is defined in both `main.py` (Docker `main:app`) and `app/api/routers/auth.py` — redeploy the branch that contains those files.

---

## Symptom → likely cause

| What you see | Likely fix |
|--------------|------------|
| LinkedIn error page right after “Sign in with LinkedIn” (before API call) | Redirect URL not listed in portal, or typo (`ccmobile://oauth/linkedin` vs missing `/oauth`, wrong scheme) |
| App returns to app but API returns 401 `invalid_code` | `redirect_uri` in token exchange ≠ authorize step; or wrong `LINKEDIN_CLIENT_SECRET` on server |
| “LinkedIn sign-in is not configured” in app | Missing `EXPO_PUBLIC_LINKEDIN_CLIENT_ID` in mobile `.env` or EAS profile |
| Works locally, fails on Render | Render `.secrets` missing or different `LINKEDIN_CLIENT_ID` than mobile build |
| `curl` callback URL returns `Not Found` | UAT not redeployed with OAuth code, or wrong Render service/branch |

---

## Quick API smoke test (after a successful redirect in app)

Replace `CODE`, `VERIFIER`, and `REDIRECT` with values from a real run (same `REDIRECT` as logged redirect URI):

```bash
curl -s -X POST "$BASE/api/auth/oauth/linkedin" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "CODE",
    "redirect_uri": "REDIRECT",
    "code_verifier": "VERIFIER",
    "intent": "login"
  }'
```

If the portal and redirect URI are correct, this returns tokens; otherwise 401 `invalid_code`.

---

## Next: Google

Same pattern: native `ccmobile://oauth/google`, web `https://<host>/app/oauth/google`. See `documentation/OAUTH_LOGIN_API.md` and `cc_mobile_ui/documentation/VENDOR_OAUTH_SETUP.md`.
