# Letter templates API (frontend)

Lists cover letter **file templates** shipped with the API under the `templates/` directory (e.g. `templates/formal/1.template`). Use this to populate a picker; **using the selected template during generation** will be wired after user preferences store the choice.

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

## Next step (not implemented yet)

The app will persist a user preference (e.g. under `preferences.appSettings`) for the chosen template (**`name` + `index`**). Generation will then load that template instead of only mapping personality profile → category + random file.

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
