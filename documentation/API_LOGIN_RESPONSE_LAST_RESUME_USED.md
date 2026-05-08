# Login response contract — resume hydration (`lastResumeUsed` + file list)

**This document is the canonical contract** for **`POST /api/users/login`** (and equivalent auth responses): **`user.preferences.appSettings.lastResumeUsed`**, **`files`** at the payload root (or the documented **`resumeFiles`** alternative), and parity with **`GET /api/users/:id`** and **`GET /api/files/list`**. Client **`PUT`** patterns and copy-paste snippets live in [`FRONTEND_LAST_RESUME_CONTRACT.md`](./FRONTEND_LAST_RESUME_CONTRACT.md).

This note is aimed at **API / backend** implementors. Mobile and web clients cold-start faster when authentication responses include everything needed to restore **resume selection** and **resume picker contents** without waiting on **`GET /api/users/:id`** and a separate **`GET /api/files/list`**.

CamelCase **`PUT`** body shape (`lastResumeUsed` only — no snake_case) and client pitfalls are summarized in [**`FRONTEND_LAST_RESUME_CONTRACT.md`**](./FRONTEND_LAST_RESUME_CONTRACT.md).

---

## 1. `preferences.appSettings.lastResumeUsed`

| Path | Type | Notes |
|------|------|--------|
| `user.preferences.appSettings.lastResumeUsed` | `string` \| `null` | Full storage **key** (e.g. `{userId}/{filename}`). **camelCase** — do not use `last_resume_used`. |

**Behavior**

1. Include **`lastResumeUsed`** on the **`user`** object returned from **login** (and any token-granting auth response you want optimized—e.g. post-registration login).
2. Emit **`"lastResumeUsed": null`** explicitly when unset so clients do not treat “missing key” as unknown state.
3. Value must match **`GET /api/users/:id`** for the same field.

---

## 2. Resume file list (same contract as `GET /api/files/list`)

Today the client loads bucket files with **`GET /api/files/list?user_id=...`**, which returns (see [`SERVER_API_REQUIREMENTS.md`](./SERVER_API_REQUIREMENTS.md)):

```json
{
  "files": [
    {
      "key": "507f1f77bcf86cd799439011/resume.pdf",
      "name": "resume.pdf",
      "size": 18210,
      "lastModified": "2024-01-15T10:30:00.000Z"
    }
  ]
}
```

**Requirement:** Include an equivalent **`files`** array on the **login response** (same object shape per entry: **`key`**, **`name`**, **`size`**, **`lastModified`** as ISO 8601 string).

### Placement (recommended)

Put **`files` at the root** of the login JSON payload **alongside** `user`, `access_token`, etc., so it mirrors **`GET /api/files/list`** exactly and can reuse the same serializer:

```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": "...",
    "preferences": {
      "appSettings": {
        "lastResumeUsed": "507f1f77bcf86cd799439011/resume.pdf",
        "personalityProfiles": [],
        "docxServiceBaseUrl": "https://example.com"
      }
    }
  },
  "files": [
    {
      "key": "507f1f77bcf86cd799439011/resume.pdf",
      "name": "resume.pdf",
      "size": 18210,
      "lastModified": "2026-04-27T12:00:00.000Z"
    }
  ],
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

If root-level **`files`** is awkward for your router, an acceptable alternative is **`user.preferences.appSettings.resumeFiles`** with the **same array element shape** — but then clients must map one extra path; **root-level `files` is preferred** for parity with **`/api/files/list`**.

### Rules

- **`files`**: always an **array** (use **`[]`** when the user has no files).
- **Ordering:** **newest first** by **`lastModified`** is recommended (the client also sorts, but matching **`/api/files/list`** avoids churn).
- **Scope:** Only objects belonging to the authenticated user (same rules as **`/api/files/list`**).
- **Consistency:** Prefer returning the **same** list the user would get from **`GET /api/files/list`** immediately after login (same filters, prefixes, and metadata).

---

## 3. Why both pieces matter

| Piece | Avoids |
|--------|--------|
| **`lastResumeUsed`** | Extra **`GET /users/:id`** just to learn which resume key was last selected. |
| **`files`** | Extra **`GET /api/files/list`** round trip before the Resume UI can show names and resolve **`lastResumeUsed`** → file row. |

Together they remove the main sequential “profile → list → match key” delay on load.

---

## 4. Frontend reference (this repo)

- Resume preference hydration: `src/services/authService.js`, `src/contexts/SettingsContext.js`
- File list today: `src/hooks/useFiles.js` (`api.listFiles` → `GET /api/files/list`)

The client will need a follow-up change to **seed bucket state from login `files`** when present; this document defines the **backend contract** for that work.

---

## 5. Registration / other auth responses

Apply the same **`user.preferences.appSettings.lastResumeUsed`** and **`files`** rules wherever you return **`user` + tokens** and want cold-start parity with login (e.g. registration completion that logs the user in).
