# JWT Interop Guide (Python Backend <-> .NET Service)

This document defines how the Python backend and the external .NET service should interoperate using JWTs.

## Goal

Use the Python backend as token issuer and let the .NET service validate those tokens with:
- HMAC signature (`HS256`)
- optional issuer check (`iss`)
- optional audience check (`aud`)

## Python Backend Settings

Set these environment variables in the Python backend:

```env
JWT_ENABLED=true
JWT_SECRET=<shared-secret-used-for-signing>
JWT_ISSUER=<issuer-string>
JWT_AUDIENCE=<audience-string>
JWT_VALIDATE_ISSUER=false
JWT_VALIDATE_AUDIENCE=false
```

Notes:
- `JWT_SECRET` is the primary signing key now.
- `JWT_SECRET_KEY` is still supported as a fallback for backward compatibility, but new setups should use `JWT_SECRET`.
- `JWT_VALIDATE_ISSUER` and `JWT_VALIDATE_AUDIENCE` control whether the Python backend strictly validates incoming bearer tokens for those claims.

## Token Claims Produced by Python

Access and refresh tokens are signed with `HS256` and include:
- `sub` (user id)
- `email`
- `type` (`access` or `refresh`)
- `iat` (issued at, unix seconds)
- `exp` (expiration, unix seconds)
- `iss` (when `JWT_ISSUER` is configured)
- `aud` (when `JWT_AUDIENCE` is configured)

## .NET Service Settings

Set the same secret and matching issuer/audience values in the .NET service:

```env
JWT_ENABLED=true
JWT_SECRET=<same-value-as-python-JWT_SECRET>
JWT_ISSUER=<same-value-as-python-JWT_ISSUER>
JWT_AUDIENCE=<same-value-as-python-JWT_AUDIENCE>
```

If strict issuer/audience validation is not yet ready in .NET, temporary fallback is:

```env
JWT_VALIDATE_ISSUER=false
JWT_VALIDATE_AUDIENCE=false
```

Keep signature validation enabled at all times.

## Recommended Rollout

1. Configure `JWT_SECRET`, `JWT_ISSUER`, and `JWT_AUDIENCE` in Python.
2. Configure matching values in .NET.
3. Keep strict issuer/audience validation disabled initially in .NET.
4. Re-login users so newly minted tokens include `iss` and `aud`.
5. After confirming tokens contain the expected claims, enable strict issuer/audience validation in .NET.

## Quick Verification

1. Log in from client and capture a fresh access token.
2. Decode JWT payload (middle segment).
3. Confirm:
   - `iss` matches `JWT_ISSUER`
   - `aud` matches `JWT_AUDIENCE`
   - signature validates with shared `JWT_SECRET`

## Common Failure Modes

- `401 invalid signature`:
  - Python and .NET secrets do not match.
- `401 invalid issuer`:
  - `iss` in token does not equal .NET configured issuer.
- `401 invalid audience`:
  - `aud` in token does not equal .NET configured audience.
- Token missing `iss`/`aud`:
  - Token was minted before rollout, or Python env vars were not set at issuance time.

