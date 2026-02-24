# MongoDB `sms` collection schema

Collection used to store Telnyx webhook payloads (inbound/outbound SMS/MMS and delivery events). Documents are inserted by the Telnyx webhook endpoint `POST /api/sms/webhook/telnyx`.

## Collection name

- **Database:** same as app (`MONGODB_DB_NAME`, default `CoverLetter`)
- **Collection:** `sms`

## Document shape

| Field          | Type     | Description |
|----------------|----------|-------------|
| `event_type`   | string   | Telnyx event: `message.received`, `message.sent`, `message.finalized` |
| `event_id`     | string   | Telnyx event UUID (`data.id`) |
| `occurred_at`  | string   | ISO 8601 timestamp when the event occurred (`data.occurred_at`) |
| `message_id`   | string   | Telnyx message UUID (`payload.id`) |
| `direction`    | string   | `inbound` or `outbound` |
| `from_phone`   | string   | Sender number, e.g. `+13125550001` (from `payload.from.phone_number`) |
| `to`           | array    | List of `{ phone_number, status?, carrier?, line_type? }` (recipients) |
| `text`         | string   | Message body |
| `message_type` | string   | `SMS` or `MMS` |
| `media`        | array    | For MMS: `[{ url, content_type, sha256?, size? }]` (media URLs expire after 30 days) |
| `errors`       | array    | Telnyx error objects if present (e.g. delivery failure details) |
| `payload`      | object   | Full Telnyx `data.payload` for reference |
| `meta`         | object   | Telnyx `meta` (e.g. `attempt`, `delivered_to`) |
| `created_at`   | date     | Server time when the document was stored (UTC) |

- **`_id`**: MongoDB ObjectId (auto-generated).

## Creating the collection in MongoDB

You do **not** need to create the collection beforehand: MongoDB creates it on first insert. If you want to create it explicitly and optionally add indexes:

### 1. Create collection (optional)

In MongoDB Shell (mongosh) or Compass:

```javascript
use CoverLetter   // or your MONGODB_DB_NAME
db.createCollection("sms")
```

### 2. Recommended indexes

```javascript
// Query by event type and time
db.sms.createIndex({ "event_type": 1, "occurred_at": -1 })

// Query by direction and time
db.sms.createIndex({ "direction": 1, "occurred_at": -1 })

// Find by Telnyx event id (idempotency / dedup)
db.sms.createIndex({ "event_id": 1 }, { unique: true })

// Find by message id
db.sms.createIndex({ "message_id": 1 })

// Find by phone number (inbound or outbound)
db.sms.createIndex({ "from_phone": 1, "created_at": -1 })
```

### 3. Example document (after one webhook)

```json
{
  "_id": ObjectId("..."),
  "event_type": "message.received",
  "event_id": "b301ed3f-1490-491f-995f-6e64e69674d4",
  "occurred_at": "2024-01-15T20:16:07.588+00:00",
  "message_id": "84cca175-9755-4859-b67f-4730d7f58aa3",
  "direction": "inbound",
  "from_phone": "+13125550001",
  "to": [
    {
      "carrier": "Telnyx",
      "line_type": "Wireless",
      "phone_number": "+17735550002",
      "status": "webhook_delivered"
    }
  ],
  "text": "Hello from Telnyx!",
  "message_type": "SMS",
  "media": [],
  "errors": [],
  "payload": { /* full Telnyx payload */ },
  "meta": { "attempt": 1, "delivered_to": "https://example.com/webhooks" },
  "created_at": ISODate("2024-01-15T20:16:08.123Z")
}
```

## Webhook URL for Telnyx

Configure your Telnyx messaging profile (or per-message) webhook URL to:

- **URL:** `https://<your-domain>/api/sms/webhook/telnyx`
- **Method:** POST (JSON body)

Return 2xx within ~2 seconds so Telnyx does not retry.
