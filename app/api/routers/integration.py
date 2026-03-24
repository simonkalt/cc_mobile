"""
Endpoints authenticated with SERVICE_AUTH_KEY (X-Service-Auth), for third-party integrations.
"""
from fastapi import APIRouter, Depends

from app.core.auth import verify_service_auth

router = APIRouter(
    prefix="/api/integration",
    tags=["integration"],
    dependencies=[Depends(verify_service_auth)],
)


@router.get("/ping")
async def integration_ping():
    """Verify that the service key is accepted. Use for connectivity and auth checks."""
    return {"ok": True, "auth": "service"}
