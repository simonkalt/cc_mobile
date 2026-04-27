# Frontend: last resume & login hydration

**Canonical backend contract:** [`documentation/API_LOGIN_RESPONSE_LAST_RESUME_USED.md`](./API_LOGIN_RESPONSE_LAST_RESUME_USED.md) (**`lastResumeUsed`**, **`files`**, registration parity). Use it for **`POST /api/users/login`** shape and **`GET /api/users/:id` / `GET /api/files/list`** parity.

This page covers **client-facing** **`PUT`** usage, repo pointers, and common mistakes.

---

## `lastResumeUsed` — field to persist

- JSON path: `preferences.appSettings.lastResumeUsed`
- Type: `string | null`
- Example value: `"693326c07fcdaab8e81cdd2f/my_resume.pdf"`

Do not send snake_case variants such as `last_resume_used` or `last_resume`.

---

## Cold start (`POST /api/users/login`)

On success, hydrate from **`loginResponse`** per **[`API_LOGIN_RESPONSE_LAST_RESUME_USED.md`](./API_LOGIN_RESPONSE_LAST_RESUME_USED.md)**:

- **`user.preferences.appSettings.lastResumeUsed`**
- Root-level **`files`** (same entries as **`GET /api/files/list`**), **`[]`** if none

If your server uses the alternative **`user.preferences.appSettings.resumeFiles`** array instead of root **`files`**, read that path—but prefer implementing root **`files`** so clients map one field like the list endpoint.

## API calls

### 1) Save when user picks/uploads/uses a resume

**PUT** `/api/users/{user_id}`

```json
{
  "preferences": {
    "appSettings": {
      "lastResumeUsed": "693326c07fcdaab8e81cdd2f/my_resume.pdf"
    }
  }
}
```

### 2) Restore on login / cold start

**POST** `/api/users/login`

1. From **`user`**, read **`preferences.appSettings.lastResumeUsed`** (camelCase — see [`API_LOGIN_RESPONSE_LAST_RESUME_USED.md`](./API_LOGIN_RESPONSE_LAST_RESUME_USED.md)).
2. From the **same** response, read **`files`** and resolve the selected resume against **`files[].key`**. **`GET /api/files/list`** is optional when **`files`** is populated with the documented shape.

**GET** `/api/users/{user_id}`

Still use where you need profile fields not present on login, or after flows that omit **`files`** (if applicable).

Read **`user.preferences?.appSettings?.lastResumeUsed`**.

Fetch **`GET /api/files/list`** after login only when login did **not** include **`files`** (legacy) or after mutations that invalidate the bundled list.

## Frontend implementation checklist

Implementation in this repo: `src/contexts/SettingsContext.js` (`updateLastResumeUsed`, loads from `GET /api/users/{id}`), `src/hooks/useCoverLetter.js` (persist after successful generate), `App.js` (manual file selection, upload success, stale-key cleanup, delete of last-used file). Prefer `preferencesPayloadCompleteForLoginHydration` / `resolveLastResumeUsedFromUser` paths from `src/services/authService.js` when login bundles **`user`** and **`files`**.

- Always write **`lastResumeUsed`** updates with **camelCase** (`PUT /api/users/{id}` — see §1).
- Update **`lastResumeUsed`** after:
  - manual resume selection
  - successful resume upload
  - successful cover-letter generation that used a resume
- On login, hydrate **both** **`user`** (including **`lastResumeUsed`**) **and** **`files`** from the login payload when returned; avoid an extra **`GET /api/files/list`** when **`files`** is already present.
- If **`lastResumeUsed`** references a **`key`** not found in **`files`** (deleted file), clear local selection and optionally **`PUT`** null.

## Copy/paste snippets

### Save

```ts
await fetch(`${API_BASE}/api/users/${userId}`, {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    preferences: {
      appSettings: {
        lastResumeUsed: resumeKey, // exact camelCase key
      },
    },
  }),
});
```

### Restore (profile GET — legacy / refresh)

```ts
const user = await fetch(`${API_BASE}/api/users/${userId}`).then((r) => r.json());
const lastResumeUsed = user?.preferences?.appSettings?.lastResumeUsed ?? null;
```

Prefer parsing **`loginResponse.user`** and **`loginResponse.files`** from **`POST /api/users/login`** on cold start so **`lastResumeUsed`** and picker options stay in sync without waiting on **`GET /api/files/list`**.

## Common mistakes

- Sending `last_resume_used` instead of `lastResumeUsed`.
- Saving only local state and never calling `PUT /api/users/{id}`.
- Comparing filename only instead of full key (`{user_id}/{filename}`).
- Ignoring login **`files`** when present and unnecessarily calling **`GET /api/files/list`** (adds latency).
