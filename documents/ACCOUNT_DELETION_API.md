# Account deletion request API (backend reference)

The mobile app **Settings → User** tab exposes **Delete My Account**. On confirmation, the client calls the endpoint below, then **closes Settings** and **clears local auth** (logout). All email delivery, data retention, and MongoDB work are **server-side**.

---

## Endpoint

| Item | Value |
|------|--------|
| **Method** | `POST` |
| **Path** | `/api/users/me/account-deletion-request` |
| **Auth** | `Authorization: Bearer <access_token>` (required) |
| **Body** | JSON object, may be empty `{}` |

The authenticated user is identified from the JWT (`sub` / `user_id` / whatever the stack uses). **Do not** accept a different `user_id` in the body for this route (prevents confused-deputy issues).

---

## Success response

- **HTTP 200** (or **202** if you only enqueue work; the app treats any 2xx JSON body as success today).
- Suggested JSON shape (optional fields are fine; the app does not depend on them):

```json
{
  "message": "Account deletion scheduled.",
  "deletion_request_id": "<opaque id>",
  "scheduled_completion_by": "<ISO-8601 datetime>"
}
```

---

## Error responses

| Code | Meaning |
|------|--------|
| **401** | Missing/invalid/expired token |
| **403** | Authenticated but not allowed to request deletion (e.g. admin lock) |
| **404** | User record not found |
| **409** | Duplicate pending request (optional) |
| **429** | Rate limit |
| **5xx** | Server error |

Use a JSON body the client already surfaces, e.g. FastAPI-style `{"detail": "..."}` or `{"message": "..."}`.

---

## Server responsibilities (product / compliance)

Implement the following on the backend (not in the mobile repo):

1. **Confirmation email**  
   After accepting the request, send a message via **Zoho Mail** (or your configured provider) to the user’s registered email stating that:
   - a deletion was requested,
   - when processing is expected to complete (e.g. within **30 days**),
   - and how to contact support if this was not them.

2. **Session / tokens**  
   Invalidate refresh tokens and/or mark the session revoked so further API calls fail after logout. The app clears local tokens after a successful response.

3. **MongoDB Atlas**  
   Within **30 days** (or your published policy), **delete or anonymize** the user’s documents (user profile, preferences, file metadata, subscriptions pointers, etc.) according to retention and legal requirements.

4. **Idempotency**  
   If the same user submits again while a request is already pending, return **200/202** with the same logical outcome or **409** with a clear message.

5. **Audit**  
   Store `user_id`, `requested_at`, `source` (e.g. `mobile_app`), and optional `ip` / `user_agent` for support.

---

## Distinction from other routes

- The app also defines `DELETE /api/users/:userId` as `api.deleteUser` for **admin-style** immediate delete, if your API supports it. **Self-service deferred deletion** should use **`POST /api/users/me/account-deletion-request`** only, so behavior (email, grace window, logging) stays consistent.

---

## Client implementation (reference)

- **API**: `src/services/api.js` → `api.requestAccountDeletion(authToken)`
- **UI**: `src/components/modals/SettingsModal.js` → `UserTab` (confirmation `Alert`, then request + `onSettingsClose` + `onForceLogout`)

If you change the path or method, update `requestAccountDeletion` in `api.js` and this document together.
