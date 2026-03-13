# Frontend Notice: SMS Opt-In Persistence Update

This document confirms a backend update for registration SMS consent persistence.

## What Changed

The backend now persists SMS opt-in as part of user creation (source of truth), instead of relying only on frontend post-login sync.

Implemented behavior:

- New users are created with:
  - `SMSOpt: "IN"`
  - `SMSOptDate: <UTC timestamp>`
- Registration completion flow (`/api/email/complete-registration`) now results in a user record that already has SMS opt-in persisted.
- User payloads now include `SMSOpt` and `SMSOptDate` fields.

## Why This Matters

Previously, frontend could set local checkbox state and attempt a follow-up API call to persist opt-in.  
Now, backend enforces this directly during registration so consent state is available immediately and consistently.

## API Fields Available to Frontend

The following user fields are now included in backend user responses:

- `SMSOpt` (`"IN"` or `"OUT"`)
- `SMSOptDate` (ISO datetime when opt state was set)

These are available anywhere a `UserResponse` payload is returned (for example login/profile fetch responses).

## Frontend Guidance

- Keep existing frontend safeguard (`setSmsOpt("IN")` after login) if desired for resilience.
- Prefer backend-returned `SMSOpt` as canonical state.
- Treat missing `SMSOpt` as legacy-user fallback only; new registrations should now always return `"IN"`.

## Backward Compatibility

- Legacy users may still have null/missing `SMSOpt` from prior records.
- For legacy migration, frontend can continue existing fallback behavior and/or call the SMS opt endpoint:
  - `PUT /api/users/me/sms-opt`
  - body: `{ "SMSOpt": "IN" | "OUT" }`

