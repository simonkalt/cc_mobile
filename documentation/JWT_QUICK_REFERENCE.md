# JWT Authentication - Quick Reference Guide

This is a quick reference guide for developers implementing JWT authentication in the API.

## Protecting Routes

### Basic Protection

To protect a route, add the `get_current_user` dependency:

```python
from fastapi import Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse

@router.get("/protected-endpoint")
async def protected_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """This endpoint requires authentication"""
    return {"message": f"Hello {current_user.name}", "user_id": current_user.id}
```

### Example: Protecting Subscription Endpoints

```python
from fastapi import Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse

@router.get("/subscriptions/my-subscription", response_model=SubscriptionResponse)
def get_my_subscription(current_user: UserResponse = Depends(get_current_user)):
    """Get current user's subscription (protected)"""
    subscription = get_user_subscription(current_user.id)
    return subscription
```

### Optional Authentication

For endpoints that work with or without authentication:

```python
from typing import Optional
from app.core.auth import get_optional_user

@router.get("/public-or-protected")
async def flexible_endpoint(user: Optional[UserResponse] = Depends(get_optional_user)):
    if user:
        return {"message": f"Hello authenticated user {user.name}"}
    return {"message": "Hello anonymous user"}
```

## Token Generation

Tokens are automatically generated in the login endpoint. To manually create tokens:

```python
from app.utils.jwt import create_access_token, create_refresh_token

# Create access token
token_data = {"sub": user_id, "email": user_email}
access_token = create_access_token(data=token_data)

# Create refresh token
refresh_token = create_refresh_token(data=token_data)
```

## Token Verification

To verify a token manually:

```python
from app.utils.jwt import verify_token

try:
    payload = verify_token(token_string, token_type="access")
    user_id = payload.get("sub")
except HTTPException:
    # Token invalid or expired
    pass
```

## Environment Variables

Required environment variables (add to `.env`):

```env
JWT_SECRET_KEY=your-very-secure-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

## Testing Protected Endpoints

### Using curl

```bash
# Login and get token
TOKEN=$(curl -X POST http://localhost:8000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# Use token in protected endpoint
curl -X GET http://localhost:8000/api/users/me \
  -H "Authorization: Bearer $TOKEN"
```

### Using Python requests

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/users/login",
    json={"email": "user@example.com", "password": "password"}
)
token = response.json()["access_token"]

# Use token
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/users/me",
    headers=headers
)
```

## Common Patterns

### Get Current User ID in Protected Route

```python
@router.get("/my-data")
async def get_my_data(current_user: UserResponse = Depends(get_current_user)):
    user_id = current_user.id
    # Use user_id for your logic
    return {"user_id": user_id}
```

### Check User Roles (if implemented)

```python
@router.get("/admin-only")
async def admin_endpoint(current_user: UserResponse = Depends(get_current_user)):
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"message": "Admin data"}
```

## Error Responses

- `401 Unauthorized`: Missing, invalid, or expired token
- `403 Forbidden`: User account is inactive or lacks permissions

## Files Created/Modified

### New Files
- `app/utils/jwt.py` - JWT token utilities
- `app/core/auth.py` - FastAPI authentication dependencies
- `documentation/JWT_AUTHENTICATION.md` - Main API documentation
- `documentation/JWT_FRONTEND_IMPLEMENTATION.md` - Frontend guide
- `documentation/JWT_POSTMAN_IMPLEMENTATION.md` - Postman guide
- `documentation/JWT_QUICK_REFERENCE.md` - This file

### Modified Files
- `app/core/config.py` - Added JWT configuration
- `app/models/user.py` - Added token response models
- `app/services/user_service.py` - Updated login to return tokens
- `app/api/routers/users.py` - Added refresh token and /me endpoints
- `requirements.txt` - Added python-jose and passlib

## Next Steps

1. **Set JWT_SECRET_KEY**: Update `.env` with a strong secret key
2. **Protect Routes**: Add `Depends(get_current_user)` to routes that need authentication
3. **Test**: Use Postman or the frontend implementation guide to test authentication
4. **Update Frontend**: Follow the frontend implementation guide to integrate JWT

## Security Reminders

⚠️ **Important Security Notes:**

1. **Never commit JWT_SECRET_KEY** to version control
2. **Use HTTPS** in production
3. **Set strong JWT_SECRET_KEY** (at least 32 random characters)
4. **Consider token rotation** for enhanced security
5. **Implement logout** to clear tokens on client side

