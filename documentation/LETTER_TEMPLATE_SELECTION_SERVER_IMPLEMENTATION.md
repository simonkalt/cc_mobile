# Letter Template Selection: Server Implementation

This document defines what the frontend now sends for template preference state, and what the server should do with it.

## Payload sent by frontend

When Settings are saved, the frontend updates user preferences via:

- `PUT /api/users/{user_id}`
- Body shape:

```json
{
  "preferences": {
    "appSettings": {
      "printProperties": { "...": "..." },
      "selectedModel": "auto",
      "letterTemplateAutoPick": true,
      "letterTemplateSelection": {
        "name": "Formal",
        "index": "2"
      },
      "last_personality_profile_used": "profile-id-or-null"
    }
  }
}
```

### `letterTemplateAutoPick` contract

- Type: `boolean`
- Semantics:
  - `true`: AI chooses the template. Frontend disables manual template cards.
  - `false`: user chooses a specific template from the catalog.
- Default (when missing): treat as `true` for backward compatibility.

### `letterTemplateSelection` contract

- Type: `object | null`
- Object fields:
  - `name` (string): template category display name (for example `Formal`)
  - `index` (string): template file stem without extension (for example `1`, `2`, `10`)
- Nullable:
  - `null` means no manual template is selected.
  - When `letterTemplateAutoPick` is `true`, frontend intentionally sends `letterTemplateSelection: null`.

## Source of truth in frontend

- Template selection is created from the Layout tab modal **Apply** action as `{ name, index }`.
- `index` is always stringified in frontend before save.
- `Let AI Pick` checkbox state is persisted as `saveAsConfig.letterTemplateAutoPick`.
- If `Let AI Pick` is checked, frontend clears any selected template and disables card clicks.
- These values are sent as:
  - `preferences.appSettings.letterTemplateAutoPick`
  - `preferences.appSettings.letterTemplateSelection`

## Server requirements

1. Accept and persist:
   - `preferences.appSettings.letterTemplateAutoPick`
   - `preferences.appSettings.letterTemplateSelection`
2. Allow both:
   - valid object with `name` and `index`
   - `null` selection when no manual template is active
3. Reject malformed values (wrong types or missing keys) with `422`.
4. Preserve existing behavior for other preference fields.
5. Return updated user object including saved preference so frontend round-trips correctly.
6. Recommended consistency rule:
   - if `letterTemplateAutoPick === true`, persist `letterTemplateSelection` as `null`.

## Validation rules (recommended)

- If present and not `null`:
  - `name`: non-empty string after trim.
  - `index`: non-empty string after trim.
- Optional stricter check:
  - verify `{name, index}` exists in `/api/letter-templates` catalog before persisting.
  - if not found, return `422` with a clear message.

## Backward compatibility

- Existing users may have neither field.
- Treat missing `letterTemplateAutoPick` as `true`.
- Treat missing `letterTemplateSelection` as `null`.
- Do not fail reads if field is absent in older stored documents.

## Example update payloads

### Save a selection

```json
{
  "preferences": {
    "appSettings": {
      "letterTemplateAutoPick": false,
      "letterTemplateSelection": {
        "name": "Creative",
        "index": "1"
      }
    }
  }
}
```

### Clear selection

```json
{
  "preferences": {
    "appSettings": {
      "letterTemplateAutoPick": true,
      "letterTemplateSelection": null
    }
  }
}
```

## Next integration step

After server persistence is in place, generation should read:

- `preferences.appSettings.letterTemplateAutoPick`
- `preferences.appSettings.letterTemplateSelection.name`
- `preferences.appSettings.letterTemplateSelection.index`

and apply logic:

- if `letterTemplateAutoPick === true`: use AI/default template selection flow.
- if `letterTemplateAutoPick === false` and selection exists: use selected `{name, index}` template.
