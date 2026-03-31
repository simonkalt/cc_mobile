# Letter templates API (frontend)

Lists cover letter **file templates** shipped with the API under the `templates/` directory (e.g. `templates/formal/1.template`). Use this to populate a picker. During generation, a saved **`letterTemplateSelection`** (`name` + `index`) is honored whenever the user is not explicitly on AI template pick (`letterTemplateAutoPick` not `true`), including when `letterTemplateAutoPick` is missing but a selection exists. That injects the file into the LLM prompt even if `USE_TEMPLATE_IN_PROMPT` is false. With AI pick on (`letterTemplateAutoPick: true`), the server uses profile→category→random template choice (and `USE_TEMPLATE_IN_PROMPT` must be true for any file template in the prompt).

## Endpoint

**GET** `/api/letter-templates`

- **Auth:** none (public catalog).
- **Success:** `200` with JSON body below.
- **Errors:**
  - **503** — templates directory missing or no `.template` files found.

## Response shape

```json
{
  "templates": [
    {
      "name": "Formal",
      "template": "Dear Hiring Manager,\n\n...",
      "index": "1"
    },
    {
      "name": "Formal",
      "template": "Hello,\n\n...",
      "index": "2"
    },
    {
      "name": "Informal",
      "template": "...",
      "index": "1"
    }
  ]
}
```

| Field       | Type   | Description |
| ----------- | ------ | ----------- |
| `templates` | array  | All templates from every category subfolder. |
| `name`      | string | **Display name** for the parent folder: segment is title-cased (`informal` → `Informal`; `my_style` → `My Style`). |
| `template`  | string | **Full file contents** of the `.template` file, UTF-8, **newlines preserved**. |
| `index`     | string | File name **without** the `.template` extension (e.g. `1`, `2`). |

### Uniqueness

The same `index` can appear under different `name` values (e.g. both `Formal` and `Creative` may have `index` `"1"`). For a stable selection key in preferences, store **both** `name` and `index` (and/or the relative path `category/index` once generation supports it).

### Ordering

Templates are grouped by **category folder name** (alphabetically), and within each folder by **natural sort** on the file stem (`1`, `2`, `10`, …).

## Example: fetch (JavaScript)

```javascript
const base = "https://your-api.example.com";
const res = await fetch(`${base}/api/letter-templates`);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const { templates } = await res.json();

templates.forEach((t) => {
  console.log(t.name, t.index, t.template.length);
});
```

## Example: cURL

```bash
curl -sS "http://localhost:8000/api/letter-templates" | jq '.templates | length'
```

## Generation behavior

Persist **`letterTemplateAutoPick`** and **`letterTemplateSelection`** (`name` + `index`) via `PUT /api/users/{id}` (see `documentation/LETTER_TEMPLATE_SELECTION_SERVER_IMPLEMENTATION.md`). Cover letter generation reads them in `resolve_cover_letter_template_for_generation` (`app/utils/template_loader.py`).

### Per-request override (recommended for clients)

So generation always matches the picker even if DB prefs lag, include on **`POST /api/job-info`** (or text-resume variant) any of:

| JSON field (camelCase) | Type | Effect |
| ---------------------- | ---- | ------ |
| `letterTemplateName` | string | Catalog `name` (e.g. `Informal`) |
| `letterTemplateIndex` | string or number | File stem (e.g. `1`) |
| `letterTemplateAutoPick` | boolean | `true` = ignore manual file for this request |

If both `letterTemplateName` and `letterTemplateIndex` are set, that file is used for **this** generation (and `letterTemplateAutoPick` is forced off for the merge). Snake_case field names are also accepted on the model.

**Note:** Very strong `additional_instructions` (e.g. “FINAL OVERRIDE”) can still override layout in the model output; avoid shipping contact-block mandates when using a minimal template.

### Debug prompt file

`tmp/llm_prompt_sent.txt` reflects the template block actually sent. If you see a different layout than expected, check the log line **`Letter template prefs for this request:`** for `letterTemplateSelection` and `manual_active`.

## Server layout (reference)

```
templates/
  formal/
    1.template
    2.template
  informal/
    1.template
  creative/
    1.template
```

Implementation: `app/api/routers/letter_templates.py`, `app/services/letter_template_catalog.py`.
