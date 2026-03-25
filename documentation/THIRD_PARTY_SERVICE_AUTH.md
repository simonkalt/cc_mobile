# Third-party integration: service authentication

This document describes how **trusted server-side integrations** authenticate to the Cover Letter API using a **shared secret**, without end-user login or JWTs.

## What you receive

You will be given a single secret value: **`SERVICE_AUTH_KEY`**. Store it only in your backend (environment variable or secrets manager). **Do not** embed it in mobile apps, front-end code, or public repositories.

## How authentication works

Send the secret on every request in this HTTP header:

| Header            | Value                    |
| ----------------- | ------------------------ |
| `X-Service-Auth`  | The full `SERVICE_AUTH_KEY` string (exact match) |

- Use **HTTPS** in production so the header is not sent in clear text.
- The server compares your header to the key configured in its environment; invalid or missing headers receive **401 Unauthorized**.

## Base URL

Use the base URL we provide for your environment, for example:

- Production: `https://<your-api-host>`
- Staging: as agreed

All paths below are relative to that base (e.g. `https://<host>/api/integration/ping`).

## Verify connectivity and credentials

**GET** `/api/integration/ping`

**Request headers**

- `X-Service-Auth`: your `SERVICE_AUTH_KEY`

**Success (200 OK)**

```json
{
  "ok": true,
  "auth": "service"
}
```

**Errors**

| Status | Meaning |
| ------ | ------- |
| **401** | Wrong or missing `X-Service-Auth` |
| **503** | Server has not configured service authentication (operator issue) |

### Example: cURL

```bash
curl -sS -H "X-Service-Auth: YOUR_SERVICE_AUTH_KEY" \
  "https://your-api-host/api/integration/ping"
```

### Example: Node.js (server-side)

```javascript
const res = await fetch("https://your-api-host/api/integration/ping", {
  headers: {
    "X-Service-Auth": process.env.SERVICE_AUTH_KEY,
  },
});
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const body = await res.json();
```

### Example: Python (server-side)

```python
import os, requests

r = requests.get(
    "https://your-api-host/api/integration/ping",
    headers={"X-Service-Auth": os.environ["SERVICE_AUTH_KEY"]},
    timeout=30,
)
r.raise_for_status()
print(r.json())
```

## Which endpoints use this header?

`/api/integration/*` routes require `X-Service-Auth` by router dependency.
Additional routes outside that router are controlled by `integration_auth_endpoints.json`.

**Current examples include:**

- `GET /api/integration/ping`
- `POST /api/files/docx-to-pdf`

Other parts of the API may use end-user JWT (`Authorization: Bearer ...`) or be public.

## Security practices

1. **Rotate** the key if it may have leaked; ask the API operator to issue a new `SERVICE_AUTH_KEY` and retire the old one.
2. **Restrict** outbound calls from your servers to known IP ranges if we provide allowlisting.
3. **Log** authentication failures sparingly and never log the full secret.
4. Prefer **short-lived** integration where possible; treat the key like a password.

## Troubleshooting

| Symptom | What to check |
| ------- | ------------- |
| 401 on `/api/integration/ping` | Header name exactly `X-Service-Auth`; value matches the key with no extra spaces or quotes |
| 503 on ping | Server operator must set `SERVICE_AUTH_KEY` in environment (or `.secrets` file in development) |
| TLS errors | Use the correct HTTPS hostname and certificate |

## Operator reference (internal)

- Key is read from environment variable **`SERVICE_AUTH_KEY`**.
- Local development: optional repo-root **`.secrets`** file (gitignored); see `.secrets.example`.
- Implementation: `app/core/auth.py` (`verify_service_auth`), router `app/api/routers/integration.py`.
