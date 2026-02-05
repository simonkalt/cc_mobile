# SMS Opt-In / Opt-Out API — Front-End Implementation Guide

This document describes the API and user fields for SMS marketing/notifications opt-in and opt-out, for use by the front-end.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Overview

- Users can set their SMS preference to **opt-in** (`"IN"`) or **opt-out** (`"OUT"`).
- The backend stores:
  - **SMSOpt**: `"IN"` or `"OUT"`
  - **SMSOptDate**: UTC timestamp when the preference was last changed.
- These values are returned on all endpoints that return user/settings (e.g. `GET /api/users/me`, login response, `GET /api/users/{user_id}`).

---

## 1. Set SMS opt-in / opt-out

**PUT** `/api/users/me/sms-opt`

Set the current user’s SMS opt-in or opt-out. Requires authentication.

**Headers**

- `Authorization: Bearer <access_token>` (required)
- `Content-Type: application/json`

**Request body**

| Field    | Type   | Required | Description                    |
| -------- | ------ | -------- | ------------------------------ |
| `SMSOpt` | string | Yes      | Must be `"IN"` or `"OUT"` only |

**Example request**

```json
{
  "SMSOpt": "IN"
}
```

**Example: opt-out**

```json
{
  "SMSOpt": "OUT"
}
```

**Response (200 OK)**

Returns the full user object (same shape as `GET /api/users/me`), including the updated `SMSOpt` and `SMSOptDate`:

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+15551234567",
  "SMSOpt": "IN",
  "SMSOptDate": "2025-02-05T14:30:00.000Z",
  "preferences": { ... },
  "dateCreated": "...",
  "dateUpdated": "..."
}
```

**Error responses**

- `401 Unauthorized`: Missing or invalid access token.
- `422 Unprocessable Entity`: Body validation failed (e.g. `SMSOpt` missing or not `"IN"`/`"OUT"`).
- `503 Service Unavailable`: Database unavailable.

**cURL example**

```bash
curl -X PUT "https://your-domain.com/api/users/me/sms-opt" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"SMSOpt":"IN"}'
```

---

## 2. User response fields (settings)

All endpoints that return the current user or a user by ID include **SMSOpt** and **SMSOptDate** in the payload. Use these to show and persist the user’s choice in your UI.

**Endpoints that include these fields**

- **GET** `/api/users/me` — current user (authenticated).
- **GET** `/api/users/{user_id}` — user by ID (authenticated).
- **POST** `/api/users/login` — response includes `user` object with these fields.
- **PUT** `/api/users/me/sms-opt` — response is the updated user object.

**Field definitions**

| Field        | Type                      | Description                                               |
| ------------ | ------------------------- | --------------------------------------------------------- |
| `SMSOpt`     | string \| null            | `"IN"`, `"OUT"`, or `null` if never set.                  |
| `SMSOptDate` | string (ISO 8601) \| null | UTC date/time of last opt change, or `null` if never set. |

**Example snippet from any user/settings response**

```json
{
  "id": "...",
  "email": "...",
  "SMSOpt": "OUT",
  "SMSOptDate": "2025-02-01T10:00:00.000Z"
}
```

- If the user has never set a preference, both may be `null`.
- After calling `PUT /api/users/me/sms-opt`, the next `GET /api/users/me` (or any user fetch) will reflect the new values.

---

## 3. Front-end implementation notes

### Reading the current preference

- After login or when loading settings, read `user.SMSOpt` and `user.SMSOptDate` from the user object (e.g. from `GET /api/users/me` or the login response).
- Treat `null` or missing as “not set” and show a neutral/default state if needed.

### Updating the preference

1. Call **PUT** `/api/users/me/sms-opt` with body `{ "SMSOpt": "IN" }` or `{ "SMSOpt": "OUT" }`.
2. Use the returned user object to update local state so the UI shows the new `SMSOpt` and `SMSOptDate` without an extra GET.

### Validation

- Only send `SMSOpt` values `"IN"` or `"OUT"` (case-sensitive). Any other value will result in `422`.

### TypeScript / type definitions

```ts
// Request body for PUT /api/users/me/sms-opt
interface SMSOptRequest {
  SMSOpt: "IN" | "OUT";
}

// Fields present on user/settings responses
interface User {
  id: string;
  email: string;
  // ... other user fields
  SMSOpt?: "IN" | "OUT" | null;
  SMSOptDate?: string | null; // ISO 8601 datetime
}
```

### Example: React state and toggle

```ts
// After fetching user (e.g. GET /api/users/me)
const smsOptIn = user.SMSOpt === "IN";

const setSmsOpt = async (optIn: boolean) => {
  const res = await fetch("/api/users/me/sms-opt", {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ SMSOpt: optIn ? "IN" : "OUT" }),
  });
  if (!res.ok) throw new Error("Failed to update SMS preference");
  const updatedUser = await res.json();
  setUser(updatedUser); // Update local user state
};
```

---

## Summary

| Item                    | Detail                                                                         |
| ----------------------- | ------------------------------------------------------------------------------ |
| **Set preference**      | `PUT /api/users/me/sms-opt` with `{ "SMSOpt": "IN" \| "OUT" }`                 |
| **Auth**                | Required (Bearer token)                                                        |
| **Where it’s stored**   | User document fields `SMSOpt` and `SMSOptDate`                                 |
| **Where it’s returned** | All user/settings responses: `/me`, `/{user_id}`, login, and after PUT sms-opt |
