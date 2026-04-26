# Backend: `preferences.formDefaults` (address, phone, tone)

**Source of truth:** Treat this file as the **canonical specification** for:

- Paths and meaning of **`preferences.formDefaults`** (including letter vs account `address` / `phone`).
- What **`PUT /api/users/{user_id}`** does and does not persist under `preferences` (including `formDefaults`).
- How **`address`** and **`phone_number`** on cover-letter generation requests relate to stored defaults and to the LLM prompt.

If another document disagrees with this one, **update the other document** (or the code) so they match; do not duplicate long behavioral descriptions elsewhere—link here instead.

[`USER_API_DOCUMENTATION.md`](./USER_API_DOCUMENTATION.md) remains the overview of user endpoints and the full `UserResponse` field list; it defers to this file for `formDefaults` semantics and persistence.

**Audience:** User service and cover-letter generation maintainers.

---

## 1. User model — where the data lives

| Path | Type | Meaning |
|------|------|--------|
| `preferences.formDefaults.address` | `string` | Free-text mailing address for the **letter** (e.g. city/state/ZIP or full multiline street). |
| `preferences.formDefaults.phoneNumber` | `string` | Applicant phone for the **letter** (any format the user typed). |
| `preferences.formDefaults.tone` | `string` | Human-readable tone / personality label for the form (often matches a `personalityProfiles[].name`). |

These sit alongside other keys created at registration (`companyName`, `hiringManager`, `jobDescription`, `resume`, etc.). Endpoint-level summaries live in [`USER_API_DOCUMENTATION.md`](./USER_API_DOCUMENTATION.md); field behavior and persistence rules are defined **in this file**.

**Important:** Do not conflate with:

- **`user.address`** — structured account/contact address (settings / Places, etc.).
- **`user.phone`** — top-level account phone when set.

**Backend-only update to `tone`:** After a successful cover-letter generation, `increment_llm_usage_count` may set `preferences.appSettings.last_personality_profile_used` and, when a display name is available, `preferences.formDefaults.tone` (`app/services/user_service.py`). That path does **not** update `address` or `phoneNumber`.

---

## 2. `PUT /api/users/{user_id}` — persistence

The client may send partial preferences, for example:

```json
{
  "preferences": {
    "formDefaults": {
      "companyName": "...",
      "tone": "...",
      "address": "123 Main St, Springfield, IL 62701",
      "phoneNumber": "+1 555-123-4567"
    }
  }
}
```

### Implemented behavior (`update_user` in `app/services/user_service.py`)

1. **`preferences.formDefaults` (partial update):** When `preferences` is a **dict** and includes **`formDefaults`**, each key in the incoming `formDefaults` object is written with a MongoDB dotted path `preferences.formDefaults.<key>` in the same `$set` as other updates. Keys **not** listed in the request are left unchanged in the database (**merge semantics**, no full replacement of `formDefaults`).

2. **Key names:** Only simple identifiers are accepted: `[_a-zA-Z][_a-zA-Z0-9]*` (rejects `.`, `$`, etc. in keys).

3. **`address` and `phoneNumber`:** Must be **string or JSON null** (null is stored as empty string `""`). Leading/trailing whitespace is **stripped** on write. Max lengths enforced: **2048** for `address`, **64** for `phoneNumber` — longer values produce **400 Bad Request**.

4. **Other `formDefaults` keys** (e.g. `companyName`, `tone`, `resume`): **string**, **number**, **boolean**, or **null** are stored; **object/array** values are skipped with a warning log. Strings are **not** auto-trimmed except for `address` / `phoneNumber`.

5. **Compatibility with `increment_llm_usage_count`:** That code also uses a dotted `$set` for `preferences.formDefaults.tone`; partial `formDefaults` updates use the same pattern so sibling keys are not clobbered.

6. **Other `preferences` keys on `PUT`:** Unchanged: nested **`preferences.appSettings.*`**, plus **`newsletterOptIn`** and **`theme`**. Replacing the entire **`preferences`** object still occurs only when the incoming `preferences` value is **not** a `dict` (avoid in clients).

7. **Read path:** `user_doc_to_response` (`app/utils/user_helpers.py`) returns the stored `preferences` document (with `appSettings` normalization and `docxServiceBaseUrl` injection). **`formDefaults` is not stripped** — whatever is in MongoDB is returned on GET user, login, register, and PUT response.

---

## 3. Cover letter generation — `POST /api/job-info` and pasted-resume route

Optional request fields are defined on the Pydantic models in **`app/models/cover_letter.py`**:

| JSON field | Type | Model(s) |
|------------|------|-----------|
| `address` | `string` | `JobInfoRequest`, `CoverLetterWithTextResumeRequest` (default `""`) |
| `phone_number` | `string` | Same (default `""`) |

**Endpoints:**

- **`POST /api/job-info`** — file path, S3 key, or base64 resume in `resume`.
- **`POST /api/cover-letter/generate-with-text-resume`** — pasted resume in `resume_text`.

Both call `get_job_info` in `app/services/cover_letter_service.py`, which passes non-empty `address` / `phone_number` into the JSON payload sent to the LLM (`message_data`).

### Generation behavior (prompt contract)

1. **Accept** `address` and `phone_number` on both routes above (and on job-info-shaped **`POST /api/chat`** bodies when routed to the same pipeline).
2. When values are non-empty after trim, they are included in the model input JSON. **Layout rules depend on template mode:** when a file template is injected into the prompt, instructions tell the model **not** to add sender phone, email, or address lines unless the template defines matching `<<placeholders>>` on their own lines — so address/phone are available to the model but must not create extra header lines beyond the template. See `cover_letter_service.py` (“LAYOUT OVERRIDES” / TEMPLATE STRUCTURE block).
3. When both are empty, behavior follows the existing prompt (resume/job data only).

---

## 4. Consistency checklist (this repo)

| Item | Status |
|------|--------|
| User responses include `preferences.formDefaults.*` when present in MongoDB | Yes (`user_doc_to_response`) |
| `PUT` user persists `formDefaults` (merge, no wipe of sibling keys) | Yes (`_apply_form_defaults_partial_update` in `user_service.py`) |
| Generation handlers accept `address` and `phone_number` | Yes (`JobInfoRequest`, `CoverLetterWithTextResumeRequest`, routers in `app/api/routers/cover_letter.py`) |
| Pydantic allows optional `address` / `phone_number` on generation requests | Yes |
| `UserUpdateRequest.preferences` | `Optional[dict]` — `formDefaults` keys are applied by the writer as above |

---

## 5. Reference docs and code

- [`documentation/USER_API_DOCUMENTATION.md`](./USER_API_DOCUMENTATION.md) — User endpoints and `UserResponse` overview (links here for `formDefaults`).
- [`documentation/FRONTEND_API_GUIDE.md`](./FRONTEND_API_GUIDE.md) — Example user fetch; defers here for letter form defaults.
- [`app/models/cover_letter.py`](../app/models/cover_letter.py) — `JobInfoRequest`, `CoverLetterWithTextResumeRequest`.
- [`app/services/user_service.py`](../app/services/user_service.py) — `update_user`, `register_user` defaults, `increment_llm_usage_count`, `_apply_form_defaults_partial_update`.
- [`app/utils/user_helpers.py`](../app/utils/user_helpers.py) — `user_doc_to_response`.

When code or product behavior changes, **edit this file first**, then adjust cross-links and consumer docs.
