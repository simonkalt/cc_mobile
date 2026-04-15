"""Structured HTTP error bodies shared with mobile/web clients (FastAPI `detail` field)."""

# Login + bearer-auth 403 when self-service deletion was requested.
HTTP_DETAIL_PENDING_ACCOUNT_DELETION = {
    "code": "PENDING_ACCOUNT_DELETION",
    "message": (
        "This account has a pending deletion request. Contact support if you need help."
    ),
}
