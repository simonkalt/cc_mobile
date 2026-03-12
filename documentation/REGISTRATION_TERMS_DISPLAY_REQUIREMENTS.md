# Registration Terms Display Requirements

This document describes how the mobile frontend displays SMS consent, Privacy Policy, and Terms of Service in the registration form.

## UI Location

- Screen: Registration modal
- File: `src/components/auth/RegisterModal.js`
- Placement: Immediately under the **Mobile Number** input field

## Displayed Consent Text

The registration UI shows this note under the phone number field:

> By providing your phone number, you agree to receive recurring automated marketing text messages from sAImon Software at the number provided. Consent is not a condition of purchase. Msg & data rates may apply. Msg frequency varies. Reply HELP for help or STOP to cancel. View our Privacy Policy Here and Terms of Service Here.

## Link Behavior

The words **"Here"** are clickable links in two places:

1. Privacy Policy Here  
   - URL: `https://www.saimonsoft.com/documents/sAImon%20Software%20-%20Privacy%20Policy.pdf`
2. Terms of Service Here  
   - URL: `https://www.saimonsoft.com/documents/sAImon%20Software%20-%20Terms%20of%20Service.pdf`

Important:

- The frontend intentionally shows **"Here"** (not raw URLs).
- Links are opened externally via React Native `Linking.openURL(...)`.

## Backend Notes

- No API payload from backend is required for this display.
- This is static frontend copy and static links.
- If legal copy changes, update the text and URLs in `RegisterModal.js` and this document together.

## Registration Terms Retrieval API Contract

This section is the backend contract for how the app retrieves Terms of Service during registration.

### When the API is called

- User taps **Create Account** in registration.
- Frontend opens `TermsOfServiceModal`.
- Modal loads Terms from backend on open.

### Request

- Method: `GET`
- Endpoint: `/api/files/terms-of-service`
- Auth: Public endpoint (no bearer token required)
- Query parameters: none
- Request body: none
- Request headers (from current client implementation):
  - `Accept: application/json`

### Response expected by app

- Primary expected payload type: **raw markdown text** in response body
- Frontend reads response with `response.text()` and renders it via markdown renderer
- Recommended content type: `text/markdown; charset=utf-8` (or another text content-type)

### Minimum successful response example

Status: `200 OK`

Body (plain text markdown):

```md
# Terms of Service

Welcome to sAImon Software...
```

### Error handling used by frontend

- `404` -> shows: "Terms of Service file not found. Please contact support."
- `503` -> shows: "Service temporarily unavailable. Please try again later."
- `500` -> shows: "Server error. Please try again later or contact support."
- Any other failure -> shows generic load failure message

### UX behavior

- User can tap **Retry** in the modal if load fails.
- User can tap refresh icon to re-fetch Terms.
- User must check "I have read and agree to the Terms of Service" before continuing registration.
