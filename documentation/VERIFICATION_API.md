# Verification API Documentation

Unified reference for all verification code flows: **SMS**, **Email**, and **Admin 2FA**.

All endpoints validate that the target phone number or email address exists in the user collection **before** dispatching any verification code. No code is ever sent to an unregistered contact.

---

## Table of Contents

1. [Pre-Send Validation Rules](#pre-send-validation-rules)
2. [SMS Endpoints (`/api/sms/…`)](#sms-endpoints)
3. [Email Endpoints (`/api/email/…`)](#email-endpoints)
4. [Admin 2FA Endpoints (`/api/admin/…`)](#admin-2fa-endpoints)
5. [Common Behaviour](#common-behaviour)
6. [Error Code Reference](#error-code-reference)
7. [Flow Diagrams](#flow-diagrams)

---

## Pre-Send Validation Rules

Every `send-code` endpoint enforces the following **before** any code is generated or sent:

| Channel | Lookup identifier | Validation performed | `forgot_password` when not found |
|---------|-------------------|----------------------|----------------------------------|
| SMS (by email) | `email` | `get_user_by_email` — 404 if no match | Returns **404** |
| SMS (by phone) | `phone` | MongoDB query on normalised phone — 404 if no match | Returns **404** |
| SMS (any purpose) | — | Confirms `user.phone` is set after lookup | **400** "User does not have a phone number registered" |
| Email (existing user) | `email` | `get_user_by_email_ignore_case` — 404 if no match | Returns **404** |
| Email (registration) | `email` | `get_user_by_email` — **409** if user already exists | N/A (registration only) |
| Admin login | `email` + `password` | Loads user by email; checks `isActive`, `super_user`, password | **401** / **403** |
| Admin resend | `user_id` | Loads user by ObjectId; checks `super_user` | **403** |

---

## SMS Endpoints

Base path: `/api/sms`

### POST `/api/sms/send-code`

Send a 6-digit verification code via SMS.

**Request**

```json
{
  "email": "user@example.com",
  "phone": "+1234567890",
  "purpose": "forgot_password"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string (email) | One of `email` or `phone` required | Looks up user by email, then sends to their registered phone |
| `phone` | string | One of `email` or `phone` required | Looks up user by normalised phone number |
| `purpose` | string | Yes | `"forgot_password"` \| `"change_password"` \| `"finish_registration"` |

**Success Response (200)**

```json
{
  "success": true,
  "message": "Verification code sent successfully",
  "expires_in_minutes": 10
}
```

**Error Responses**

| Status | Condition |
|--------|-----------|
| 400 | Invalid purpose, neither `email` nor `phone` provided, or user has no phone on file |
| 404 | User not found (all purposes including `forgot_password`) |
| 500 | SMS provider failure |
| 503 | Database unavailable |

---

### POST `/api/sms/verify-code`

Verify a previously sent 6-digit code.

**Request**

```json
{
  "email": "user@example.com",
  "phone": "+1234567890",
  "code": "123456",
  "purpose": "forgot_password"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string (email) | One of `email` or `phone` | — |
| `phone` | string | One of `email` or `phone` | — |
| `code` | string | Yes | 6-digit code |
| `purpose` | string | Yes | Must match the purpose used when sending |

**Response (200)** — always 200; check `verified` field:

```json
{ "success": true,  "message": "Code verified successfully", "verified": true }
{ "success": false, "message": "Invalid or expired code",    "verified": false }
```

---

### POST `/api/sms/reset-password`

Reset password using a verified code (forgot-password flow).

**Request**

```json
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "N3wS3cure!Pass"
}
```

| Field | Type | Required |
|-------|------|----------|
| `email` | string (email) | Yes |
| `code` | string | Yes |
| `new_password` | string | Yes |

**Success (200)**

```json
{ "success": true, "message": "Password reset successfully" }
```

**Errors:** 400 (invalid/expired code, weak password), 404 (user not found)

---

### POST `/api/sms/change-password`

Change password for a logged-in user using a verified code.

**Request**

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "code": "123456",
  "new_password": "N3wS3cure!Pass"
}
```

| Field | Type | Required |
|-------|------|----------|
| `user_id` | string | Yes — MongoDB ObjectId |
| `code` | string | Yes |
| `new_password` | string | Yes |

**Success (200)**

```json
{ "success": true, "message": "Password changed successfully" }
```

**Errors:** 400 (invalid/expired code, weak password), 404 (user not found)

---

### POST `/api/sms/complete-registration`

Complete registration by verifying the SMS code. Marks the user's email as verified.

**Request**

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Success (200)**

```json
{ "success": true, "message": "Registration completed successfully" }
```

**Errors:** 400 (invalid/expired code), 404 (user not found)

---

## Email Endpoints

Base path: `/api/email`

### POST `/api/email/send-code`

Send a 6-digit verification code via email.

**Request**

```json
{
  "email": "user@example.com",
  "purpose": "forgot_password",
  "registration_data": null,
  "delivery_method": "email"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string (email) | Yes | — |
| `purpose` | string | Yes | `"forgot_password"` \| `"change_password"` \| `"finish_registration"` |
| `registration_data` | object \| null | Required for `finish_registration` | `{ "name": "...", "email": "...", "password": "...", "phone": "..." }` |
| `delivery_method` | string | No (default `"email"`) | `"email"` or `"sms"` |

**Purpose-specific behaviour:**

| Purpose | User must exist? | Extra validation |
|---------|------------------|------------------|
| `finish_registration` | Must **not** exist (409 if they do) | `registration_data` required; password strength enforced |
| `forgot_password` | If not found → **404** | Frontend uses the 404 to hold the user on the send-code step (see note below) |
| `change_password` | Must exist (404 if not) | — |

**Success Response (200)**

```json
{
  "success": true,
  "message": "Verification code sent successfully",
  "expires_in_minutes": 10
}
```

**Error Responses**

| Status | Condition |
|--------|-----------|
| 400 | Invalid purpose, missing `registration_data`, weak password |
| 404 | User not found (**all** non-registration purposes, including `forgot_password`) |
| 409 | User already exists (registration only) |
| 500 | Email delivery failure |
| 503 | Database unavailable |

> **Design note:** Both SMS and email `send-code` endpoints return **404** for `forgot_password` with an unknown user. This is intentional — the frontend uses the 404 to keep the user on the send-code step. The trade-off is that account existence can be probed via these endpoints; this was a deliberate UX-over-enumeration-protection decision.

---

### POST `/api/email/verify-code`

Verify a code sent via email.

**Request**

```json
{
  "email": "user@example.com",
  "code": "123456",
  "purpose": "forgot_password"
}
```

**Response (200)**

```json
{ "success": true,  "message": "Code verified successfully", "verified": true }
{ "success": false, "message": "Invalid or expired code",    "verified": false }
```

---

### POST `/api/email/reset-password`

Reset password using a verified email code.

**Request**

```json
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "N3wS3cure!Pass"
}
```

**Success (200)**

```json
{ "success": true, "message": "Password reset successfully" }
```

**Errors:** 400 (invalid/expired code, code already used, weak password), 404 (user not found)

> The email reset-password endpoint additionally guards against code reuse — once a code has been used to reset a password, it is marked `verified: true` and cannot be resubmitted.

---

### POST `/api/email/change-password`

Change password for a logged-in user using a verified email code.

**Request**

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "code": "123456",
  "new_password": "N3wS3cure!Pass"
}
```

**Success (200)**

```json
{ "success": true, "message": "Password changed successfully" }
```

**Errors:** 400 (invalid/expired code, weak password), 404 (user not found)

---

### POST `/api/email/complete-registration`

Complete registration by verifying email code and creating the user from Redis data.

**Request**

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Success (200)**

```json
{ "success": true, "message": "Registration completed successfully" }
```

**Errors:** 400 (invalid/expired code), 409 (user already exists), 500 (creation failure)

> Unlike the SMS registration flow, this endpoint creates the user from data stored in Redis during the `send-code` step. The user does **not** need to call `/api/users/register` first.

---

## Admin 2FA Endpoints

Base path: `/api/admin`

These endpoints require the user to have `super_user: true` in their user document.

### POST `/api/admin/login`

Authenticate an admin and send a 2FA code.

**Request**

```json
{
  "email": "admin@example.com",
  "password": "adminPass123",
  "delivery_method": "sms"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string (email) | Yes | — |
| `password` | string | Yes | — |
| `delivery_method` | string | No (default `"sms"`) | `"sms"` or `"email"` |

**Pre-send validation:** Loads user by email → checks `isActive` → checks `super_user` → verifies password → checks phone exists (if SMS delivery). All checks pass before any code is sent.

**Success (200)**

```json
{
  "requires_2fa": true,
  "user_id": "507f1f77bcf86cd799439011",
  "delivery_method": "sms",
  "message": "Verification code sent via sms"
}
```

**Errors:** 400 (no phone on file for SMS delivery), 401 (bad credentials), 403 (inactive or not admin)

---

### POST `/api/admin/verify-2fa`

Verify the 2FA code and receive a JWT.

**Request**

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "code": "123456"
}
```

**Success (200)**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 14400
}
```

**Errors:** 401 (invalid/expired code), 403 (not admin)

---

### POST `/api/admin/resend-code`

Resend a 2FA code for an in-progress admin login.

**Request**

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "delivery_method": "sms"
}
```

**Pre-send validation:** Loads user by ObjectId → checks `super_user` → checks phone exists (if SMS).

**Success (200)**

```json
{ "message": "Code resent via sms" }
```

**Errors:** 400 (no phone on file), 403 (not admin)

---

## Common Behaviour

### Verification Codes

- **Format:** 6-digit numeric string (e.g., `"482917"`)
- **Expiry:** 10 minutes from generation
- **Single-use:** Cleared from the database after successful verification or password action
- **Purpose-bound:** A code generated for `forgot_password` cannot be used for `change_password`

### Phone Number Normalisation

Phone numbers are normalised to E.164 format before lookup. All of these are equivalent:

```
+12125551234
(212) 555-1234
212-555-1234
2125551234
```

US numbers without a country code default to `+1`.

### Password Strength

When `ENFORCE_STRONG_PASSWORDS` is enabled (production default), `new_password` fields must meet the configured policy. A **400** with a descriptive message is returned for violations. See `documentation/PASSWORD_POLICY.md`.

### Anti-Enumeration

Both SMS and Email `send-code` endpoints return **404** for `forgot_password` when the user is not found. This is a deliberate UX-over-enumeration-protection decision — the frontend uses the 404 to keep the user on the send-code step and display "No account found with this email address." Account existence can therefore be probed via these endpoints.

---

## Error Code Reference

| Status | Meaning | When |
|--------|---------|------|
| 200 | Success | Request completed (check `success` / `verified` fields for logical outcome) |
| 400 | Bad Request | Invalid purpose, missing required fields, invalid/expired code, weak password, no phone on file |
| 401 | Unauthorized | Bad credentials (admin login), invalid 2FA code |
| 403 | Forbidden | Account inactive, not an admin |
| 404 | Not Found | User not found (all purposes including `forgot_password` — see [Anti-Enumeration](#anti-enumeration)) |
| 409 | Conflict | User already exists (email registration) |
| 500 | Server Error | SMS/email provider failure |
| 503 | Service Unavailable | Database connection down |

All error responses use the standard format:

```json
{ "detail": "Human-readable error message" }
```

---

## Flow Diagrams

### Forgot Password (SMS or Email)

```
Client                          Server
  │                                │
  │  POST /api/{sms|email}/send-code
  │  { email, purpose: "forgot_password" }
  │  ─────────────────────────────►│
  │                                │── Lookup user by email
  │                                │── If not found → 404 { detail: "User not found" }
  │                                │── If found → generate code, send via SMS/email
  │  ◄──── 200 { success: true }───│
  │                                │
  │  POST /api/{sms|email}/verify-code
  │  { email, code, purpose: "forgot_password" }
  │  ─────────────────────────────►│
  │                                │── Verify code + purpose + expiry
  │  ◄──── 200 { verified: true } ─│
  │                                │
  │  POST /api/{sms|email}/reset-password
  │  { email, code, new_password }
  │  ─────────────────────────────►│
  │                                │── Re-verify code, update password
  │  ◄──── 200 { success: true }───│
```

### Email Registration

```
Client                          Server
  │                                │
  │  POST /api/email/send-code
  │  { email, purpose: "finish_registration",
  │    registration_data: { name, email, password, phone } }
  │  ─────────────────────────────►│
  │                                │── Check user does NOT exist (409 if they do)
  │                                │── Store registration_data in Redis
  │                                │── Send code via email
  │  ◄──── 200 { success: true }───│
  │                                │
  │  POST /api/email/complete-registration
  │  { email, code }
  │  ─────────────────────────────►│
  │                                │── Verify code from Redis
  │                                │── Create user from stored registration_data
  │                                │── Mark email verified
  │  ◄──── 200 { success: true }───│
```

### Admin Login + 2FA

```
Client                          Server
  │                                │
  │  POST /api/admin/login
  │  { email, password, delivery_method }
  │  ─────────────────────────────►│
  │                                │── Verify email + active + super_user + password
  │                                │── Send 2FA code via chosen channel
  │  ◄──── 200 { requires_2fa, user_id, delivery_method }
  │                                │
  │  POST /api/admin/verify-2fa
  │  { user_id, code }
  │  ─────────────────────────────►│
  │                                │── Verify 2FA code
  │  ◄──── 200 { access_token, expires_in }
```
