# Client Settings API

Public configuration consumed by the mobile/web client at startup. Used for password policy, legal URLs, registration copy, and job share import site rollout.

**Client implementation (mobile):** `cc_mobile_ui` → `src/services/clientSettingsService.js`

## GET /api/config/client-settings

**Authentication:** None (public).

### Response fields

| Field | Type | Description |
|-------|------|-------------|
| `jobShareImportSites` | object | Global toggles for share-to-app job import by site ID |

#### `jobShareImportSites` keys

| Key | Default | Description |
|-----|---------|-------------|
| `linkedin` | `true` | linkedin.com job URLs |
| `indeed` | `false` | indeed.com job URLs |
| `glassdoor` | `false` | glassdoor.com job URLs |
| `ziprecruiter` | `false` | ziprecruiter.com job URLs |
| `generic` | `false` | Other http(s) job URLs |

**Storage:** MongoDB collection `client_settings` (override via `CLIENT_SETTINGS_COLLECTION`), document `_id: "global"`, field `jobShareImportSites`.

---

## PATCH /api/config/client-settings/job-share-sites

**Authentication:** Required — `Authorization: Bearer <JWT>`.

**Authorization:** Caller must have `super_user: true`.

### Request body

Partial update — all keys optional, boolean values only.

### Response (200)

```json
{
  "jobShareImportSites": {
    "linkedin": true,
    "indeed": false,
    "glassdoor": false,
    "ziprecruiter": true,
    "generic": false
  }
}
```

### Errors

| Status | When |
|--------|------|
| **401** | Missing or invalid JWT |
| **403** | Not `super_user` |
| **400** | Invalid body |
| **503** | MongoDB unavailable |
| **500** | Persist failed |
