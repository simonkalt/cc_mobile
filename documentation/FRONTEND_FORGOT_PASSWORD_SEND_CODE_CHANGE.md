# Frontend: Forgot-password send-code behavior change

**Audience:** `cc_mobile_ui` (Expo / React Native) and any web client using the verification APIs.  
**Backend branch:** `uat` (and later `production` after promote).  
**Date:** 2026-05-20

---

## Summary

`POST /api/email/send-code` and `POST /api/sms/send-code` with `purpose: "forgot_password"` **no longer return HTTP 404** when the account is missing (or when SMS cannot be sent). They always return **HTTP 200** with the same JSON shape as a successful send.

This restores **anti-enumeration**: attackers cannot discover registered emails/phones by comparing 404 vs 200.

---

## What changed

| Scenario | Before (broken) | After (current) |
|----------|-----------------|-----------------|
| Email not registered | **404** `User not found` | **200** generic success (no email sent) |
| SMS: email not registered | **404** | **200** generic (no SMS sent) |
| SMS: phone not registered | **404** | **200** generic (no SMS sent) |
| SMS: user exists but no phone on file | **400** `User does not have a phone number registered` | **200** generic (no SMS sent) |
| Known user, delivery OK | **200** + code sent | **200** + code sent (unchanged) |

**Unchanged:**

- `purpose: "change_password"` — still **404** if user not found.
- `purpose: "finish_registration"` — still **409** if email already exists, etc.
- `verify-code`, `reset-password`, `change-password` — same as before (invalid code still fails verification).

---

## Response body (`forgot_password` send-code)

**HTTP 200** in all cases above (whether or not a code was actually sent):

```json
{
  "success": true,
  "message": "If an account exists for this email or phone number, a verification code has been sent.",
  "expires_in_minutes": 10
}
```

When delivery succeeds for a real account, the body is the same shape; only the `message` string may differ in older clients — prefer treating any **200** with `success: true` as “proceed to enter code.”

---

## Required frontend updates

### 1. Stop using 404 on send-code for “account not found”

**Remove** logic like:

```ts
// ❌ Old — do not use
try {
  await api.post('/api/email/send-code', { email, purpose: 'forgot_password' });
  navigateToEnterCode();
} catch (e) {
  if (e.status === 404) {
    showError('No account found with this email');
    stayOnEmailStep();
  }
}
```

### 2. Always advance to the code-entry step on 200

```ts
// ✅ New
const res = await api.post('/api/email/send-code', {
  email,
  purpose: 'forgot_password',
});
if (res.status === 200 && res.data.success) {
  showNeutralMessage(
    res.data.message ??
      'If an account exists, a verification code has been sent.'
  );
  navigateToEnterCode();
}
```

Use the same pattern for `POST /api/sms/send-code` with `email` or `phone`.

### 3. Copy / UX

- **Do not** say “Account not found” after send-code.
- **Do** show neutral copy, e.g. *If an account exists for this email, we sent a verification code. Check your inbox.* (email) or *…text message* (SMS).
- Wrong or unknown accounts only discover failure at **verify-code** or **reset-password** (invalid/expired code), which is intentional.

### 4. Non-200 errors (still handle)

| Status | Meaning | UX |
|--------|---------|-----|
| 400 | Bad request (missing email, invalid purpose, etc.) | Show validation error |
| 500 | Provider failure (Zoho/Telnyx) | Retry / support message |
| 503 | Database down | Generic “try again” |

---

## Endpoints (reference)

| Method | Path | `purpose` |
|--------|------|-----------|
| POST | `/api/email/send-code` | `forgot_password` |
| POST | `/api/sms/send-code` | `forgot_password` |

Request bodies unchanged — see `documentation/VERIFICATION_API.md`.

---

## Testing checklist

- [ ] Unknown email → **200**, UI goes to code step, **no** “account not found” on send step.
- [ ] Known email → **200**, user receives code (or test env logs).
- [ ] Wrong code on verify → still fails (invalid/expired).
- [ ] SMS forgot with unknown phone → **200**, generic message, no 404.
- [ ] `change_password` send-code with unknown user → still **404** (if you use that flow).

---

## Related backend docs

- `documentation/VERIFICATION_API.md` — full API (anti-enumeration section updated)
- `documentation/SMS_VERIFICATION_API.md` — SMS-specific notes

---

## Questions

If the app still needs a dedicated “no account” path for product reasons, that must be a **separate** non-security-sensitive flow; the send-code endpoints cannot expose account existence.
