# Subscription status API – cURL examples

## Get subscription status

**Endpoint:** `GET /api/subscriptions/{user_id}`  
**Auth:** Bearer token (JWT) required.

Replace `YOUR_JWT_TOKEN` with a valid access token and `USER_ID` with the user’s ID (e.g. MongoDB ObjectId).

```bash
curl -s -X GET "http://localhost:8000/api/subscriptions/USER_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Example with real values:**

```bash
curl -s -X GET "http://localhost:8000/api/subscriptions/693326c07fcdaab8e81cdd2f" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json"
```

**Pretty-print JSON (with jq):**

```bash
curl -s -X GET "http://localhost:8000/api/subscriptions/USER_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" | jq .
```

---

## Get a token (login)

If you don’t have a JWT, get one via login:

```bash
curl -s -X POST "http://localhost:8000/api/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}'
```

Copy the `access_token` from the response and use it in the subscription request above.

**One-liner: use login token for subscription (bash):**

```bash
# Set these
EMAIL="your@email.com"
PASSWORD="yourpassword"
USER_ID="693326c07fcdaab8e81cdd2f"
BASE="http://localhost:8000"

# Get token and call subscription endpoint
TOKEN=$(curl -s -X POST "$BASE/api/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')
curl -s -X GET "$BASE/api/subscriptions/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
```

---

## Expected response (200)

```json
{
  "subscriptionId": "sub_xxx",
  "subscriptionStatus": "active",
  "subscriptionPlan": "price_xxx",
  "productId": "prod_xxx",
  "subscriptionCurrentPeriodEnd": "2025-03-01T00:00:00",
  "lastPaymentDate": "2025-02-01",
  "stripeCustomerId": "cus_xxx"
}
```

For a user with no subscription, status is typically `"free"` and other fields may be null.

## Error responses

- **401 Unauthorized** – Missing or invalid/expired token. Log in again to get a new token.
- **403 Forbidden** – Authenticated user is not allowed to view this subscription (e.g. wrong user_id).
- **404 Not Found** – User not found.
