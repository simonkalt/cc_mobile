# Frontend Contract: Last Used Resume

Use this as the single source of truth for persisting and restoring the default resume.

## Canonical field (must match exactly)

- JSON path: `preferences.appSettings.lastResumeUsed`
- Type: `string | null`
- Example value: `"693326c07fcdaab8e81cdd2f/my_resume.pdf"`

Do not send snake_case variants such as `last_resume_used` or `last_resume`.

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

### 2) Restore on login/app bootstrap

**GET** `/api/users/{user_id}`

Read:

- `user.preferences?.appSettings?.lastResumeUsed`

Then match against `/api/files/list` keys and select that file in UI.

## Frontend implementation checklist

- Always write **only** `lastResumeUsed` (camelCase).
- Update `lastResumeUsed` after:
  - manual resume selection
  - successful resume upload
  - successful cover-letter generation that used a resume
- On login, fetch user settings first, then hydrate selected resume from `lastResumeUsed`.
- If referenced key no longer exists in `/api/files/list`, clear local selection and optionally `PUT` null.

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

### Restore

```ts
const user = await fetch(`${API_BASE}/api/users/${userId}`).then((r) => r.json());
const lastResumeUsed = user?.preferences?.appSettings?.lastResumeUsed ?? null;
```

## Common mistakes

- Sending `last_resume_used` instead of `lastResumeUsed`.
- Saving only local state and never calling `PUT /api/users/{id}`.
- Restoring before user settings are fetched.
- Comparing filename only instead of full key (`{user_id}/{filename}`).
