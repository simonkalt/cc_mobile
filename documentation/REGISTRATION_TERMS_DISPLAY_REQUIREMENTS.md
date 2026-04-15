# Registration Terms Display Requirements

This document describes how the mobile frontend displays the **Data Use & Sharing Notice**, SMS consent, Privacy Policy, and Terms of Service in the registration form.

## UI Location

- Screen: Registration modal
- File: `src/components/auth/RegisterModal.js`

## Vertical layout (top to bottom)

Use clear **visual separators** (e.g. horizontal rules or padded divider blocks with a subtle border) between major sections so users can scan **data use** vs **policy / SMS** vs **account fields**.

Recommended order:

1. **Data use & sharing (top of form)**  
   - Load copy from **`GET /api/config/client-settings`** → `registrationDataUseNotice` (see below).  
   - Render **`noticeText`** in *italics* (use `noticeTypographicStyle === "italic"` as the default hint).  
   - Immediately below the notice text, a **required checkbox** bound to local state (e.g. `dataUseSharingNoticeAccepted`).  
   - **Label** for the checkbox: use `checkboxLabel` for the native checkbox + label pattern (the platform draws the box). If you need a single static string that includes the empty box glyph, use `checkboxLabelWithSymbol` / `checkboxLeadingSymbol` from JSON only for non-interactive previews—avoid duplicating the box next to a real `Switch`/`CheckBox`.  
   - Exact label wording (without leading `☐` for the interactive control):

     > I have read and agree to the Data Use & Sharing Notice above, including the sharing of my data with third-party AI services and service providers.

2. **— Visual separator —**

3. **Policy & SMS block** (existing behavior)  
   - Place the **Mobile Number** field and the SMS marketing consent paragraph here (or keep your current field order, but keep this block visually grouped).  
   - **Privacy Policy Here** / **Terms of Service Here** links (URLs from `privacyPolicyUrl` / `termsOfServiceUrl` in client-settings).

4. **— Visual separator —**

5. **Remaining registration fields** (name, email, password, etc.) and **Terms of Service** modal / checkbox flow as today.

## Data Use & Sharing Notice (copy source)

- **Do not hardcode** the long notice in the app for production. Read it from the API so marketing/legal can change **`registration_data_use_notice.json`** on the server without an app release.
- **`GET /api/config/client-settings`** includes **`registrationDataUseNotice`**, an object loaded from `registration_data_use_notice.json` (repo root by default; override path with env `REGISTRATION_DATA_USE_NOTICE_PATH`).
- Typical keys: `noticeText`, `noticeTypographicStyle`, `checkboxLabel`, `checkboxLabelWithSymbol`, `checkboxLeadingSymbol`.

## Displayed SMS consent text (under phone)

> By providing your phone number, you agree to receive recurring automated marketing text messages from sAImon Software at the number provided. Consent is not a condition of purchase. Msg & data rates may apply. Msg frequency varies. Reply HELP for help or STOP to cancel. View our Privacy Policy Here and Terms of Service Here.

## Link behavior (Privacy / Terms)

The words **"Here"** are clickable links:

1. Privacy Policy Here — URL: `privacyPolicyUrl` from client-settings (default `https://www.saimonsoft.com/website/docs/privacy-policy.html`)
2. Terms of Service Here — URL: `termsOfServiceUrl` from client-settings (default `https://www.saimonsoft.com/website/docs/terms-of-service.html`)

Open via React Native `Linking.openURL(...)`.

## Backend: registration consent enforcement

### Direct registration — `POST /api/users/register`

- Body must include **`dataUseSharingNoticeAccepted`: true** (camelCase) or **`data_use_sharing_notice_accepted`: true** (snake_case).
- If the flag is missing or `false`, the API returns **400** with a clear error (or **422** if the field is omitted and validation fails).
- On success, the user document stores **`dataUseSharingNoticeAcceptedAt`** (UTC timestamp) for audit.

### Email verification registration — `POST /api/email/send-code` (`purpose`: `finish_registration`)

- **`registration_data`** must include **`dataUseSharingNoticeAccepted`: true** (or snake_case equivalent) before a code is sent; otherwise **400**.

### Completing email registration

- Unchanged contract for `POST /api/email/complete-registration`; acceptance was already asserted when `registration_data` was stored.

## Backend notes (URLs & JSON file)

- Override legal page URLs with env `PUBLIC_PRIVACY_POLICY_URL` / `PUBLIC_TERMS_OF_SERVICE_URL` when needed (e.g. staging).
- Edit **`registration_data_use_notice.json`** at the repo root to change notice/checkbox strings; restart or rely on file read on each `client-settings` request (no in-process cache today).

## Registration Terms Retrieval API Contract

### When the API is called

- User taps **Create Account** in registration.
- Frontend opens `TermsOfServiceModal`.
- Modal loads Terms from backend on open.

### Request

- Method: `GET`
- Endpoint: `/api/files/terms-of-service`
- Auth: Public (no bearer token)
- Headers (current client): `Accept: application/json` (or as implemented)

### Response expected by app

- Primary payload: **raw markdown** in the response body, rendered in the modal.

### UX behavior

- User can tap **Retry** / refresh on failure.
- User must check **"I have read and agree to the Terms of Service"** before continuing registration (existing flow), **in addition to** the Data Use & Sharing Notice checkbox above.
