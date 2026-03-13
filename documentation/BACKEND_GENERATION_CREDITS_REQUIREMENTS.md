# Backend Requirement: `generation_credits` Must Always Be Returned

This document defines the backend contract needed by the mobile app so free-tier credit gating works correctly after registration and login.

## Problem Being Fixed

The app can show "You have used up your 10 free credits" incorrectly when backend responses omit `generation_credits` for new/free users.

Even if DB has `generation_credits = 10`, if the API payload omits the field, frontend may interpret the user as out of credits.

---

## Required Contract

For free-tier users, backend must **always** include `generation_credits` as a numeric field in all user/subscription responses used by the app.

- Type: number (integer)
- Range: `>= 0`
- Never omit for free-tier users
- Never return `null` for free-tier users

Recommended companion field:

- `max_credits` (number), used for user-facing messaging ("out of X credits")

---

## Endpoints That Must Include Credits

### 1) Login

**Endpoint:** `POST /api/users/login`  
**Required in `user` payload:** `generation_credits`

Example:

```json
{
  "success": true,
  "access_token": "jwt...",
  "refresh_token": "jwt...",
  "user": {
    "id": "693326c07fcdaab8e81cdd2f",
    "email": "user@example.com",
    "generation_credits": 10,
    "max_credits": 10
  }
}
```

### 2) User Profile Fetch

**Endpoint:** `GET /api/users/{user_id}`  
**Required fields:** `generation_credits` (and ideally `max_credits`)

### 3) Subscription Fetch (free-tier fallback path)

**Endpoint:** `GET /api/subscriptions/{user_id}`  
If user has no subscription/free tier, response must still include:

- `subscriptionStatus: "free"`
- `generation_credits`

Example:

```json
{
  "subscriptionStatus": "free",
  "subscriptionPlan": null,
  "subscriptionCurrentPeriodEnd": null,
  "generation_credits": 10,
  "max_credits": 10
}
```

### 4) Registration Completion (if returning user object)

Any registration completion/login-followup response that includes user data should also include `generation_credits`.

---

## Update Semantics

When a generation succeeds:

1. Backend decrements credits atomically (free-tier only).
2. Subsequent `GET /api/users/{id}` and subscription response must return the updated value.
3. Never allow negative credits.

---

## Response Shape Compatibility

Frontend primarily reads snake_case:

- `generation_credits`
- `max_credits`

Camel-case aliases are acceptable but snake_case should remain canonical.

---

## Acceptance Checklist (Backend)

- [ ] New free-tier user login returns `user.generation_credits = 10`.
- [ ] `GET /api/users/{id}` returns `generation_credits` for free users.
- [ ] `GET /api/subscriptions/{id}` free response includes `generation_credits`.
- [ ] After successful generation, credit value decrements and is visible in next fetch.
- [ ] Field is never omitted/null for free-tier users.

---

## Why This Is Required

The mobile app gates generation using subscription status + free credits. Missing credit fields create false "out of credits" states even when DB data is correct. Returning `generation_credits` consistently resolves this class of issue at the source.
