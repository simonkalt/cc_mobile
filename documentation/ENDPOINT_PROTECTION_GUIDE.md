# Endpoint Protection Guide

This guide explains which endpoints should be protected with JWT authentication and how to protect them.

## Overview

By default, **all endpoints are public** unless explicitly protected. To protect an endpoint, you must add the `get_current_user` dependency.

## Public Endpoints (Should Remain Public)

These endpoints should **NOT** be protected as they are needed for authentication and public access:

- `POST /api/users/register` - User registration
- `POST /api/users/login` - User login (returns JWT tokens)
- `POST /api/users/refresh-token` - Token refresh
- `GET /api/health` - Health check (for monitoring)
- `GET /` - Root endpoint (API info)
- `POST /api/email/send-code` - Email verification (public)
- `POST /api/email/verify-code` - Email verification (public)
- `POST /api/sms/send-code` - SMS verification (public)
- `POST /api/sms/verify-code` - SMS verification (public)

## Protected Endpoints (Should Require Authentication)

These endpoints should be **protected** as they access user-specific data or perform authenticated actions:

### User Management

- ✅ `GET /api/users/me` - Already protected
- ❌ `GET /api/users/{user_id}` - Should be protected (or verify user owns the ID)
- ❌ `PUT /api/users/{user_id}` - Should be protected (verify user owns the ID)
- ❌ `DELETE /api/users/{user_id}` - Should be protected (verify user owns the ID)

### LLM Configuration

- ✅ `GET /api/llms` - **Now protected**

### Subscriptions

- ❌ `GET /api/subscriptions/{user_id}` - Should be protected (verify user owns the ID)
- ❌ `POST /api/subscriptions/create-payment-intent` - Should be protected
- ❌ `POST /api/subscriptions/subscribe` - Should be protected
- ❌ `PUT /api/subscriptions/upgrade` - Should be protected
- ❌ `POST /api/subscriptions/cancel` - Should be protected
- ❌ `GET /api/subscriptions/payment-intent/{payment_intent_id}` - Should be protected

### Cover Letters

- ❌ `POST /api/cover-letters/generate` - Should be protected
- ❌ `GET /api/cover-letters` - Should be protected (user-specific)
- ❌ `GET /api/cover-letters/{id}` - Should be protected (verify ownership)

### Files

- ❌ `GET /api/files` - Should be protected (user-specific)
- ❌ `POST /api/files/upload` - Should be protected
- ❌ `DELETE /api/files/{file_id}` - Should be protected (verify ownership)

### PDF Generation

- ❌ `POST /api/files/generate-pdf` - Should be protected

### Job Analysis

- ❌ `POST /api/job-url/analyze` - Should be protected

### Personality Profiles

- ❌ `GET /api/personality-profiles` - Should be protected (user-specific)

### Configuration

- ❓ `GET /api/config/google-places-key` - Consider protecting (may be public for frontend)
- ❓ `GET /api/config/system-prompt` - Consider protecting

## How to Protect an Endpoint

### Basic Protection

Add the `get_current_user` dependency:

```python
from fastapi import Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse

@router.get("/protected-endpoint")
async def protected_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """This endpoint requires authentication"""
    return {"message": f"Hello {current_user.name}", "user_id": current_user.id}
```

### Verify User Ownership

For endpoints that take a `user_id` parameter, verify the user owns that ID:

```python
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user by ID - only if it's the current user"""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data"
        )
    return get_user_by_id(user_id)
```

### Optional Authentication

For endpoints that work with or without authentication:

```python
from typing import Optional
from app.core.auth import get_optional_user

@router.get("/public-or-protected")
async def flexible_endpoint(
    user: Optional[UserResponse] = Depends(get_optional_user)
):
    if user:
        return {"message": f"Hello authenticated user {user.name}"}
    return {"message": "Hello anonymous user"}
```

## Protection Strategy

### Option 1: Protect All by Default (Recommended)

Create a middleware or router-level dependency that protects all routes in a router:

```python
from fastapi import Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse

# Apply to entire router
router = APIRouter(
    prefix="/api/protected",
    tags=["protected"],
    dependencies=[Depends(get_current_user)]  # All routes require auth
)
```

### Option 2: Protect Individual Endpoints

Add protection to each endpoint that needs it (current approach).

### Option 3: Whitelist Public Endpoints

Protect all endpoints by default, then explicitly mark public ones:

```python
from fastapi import Depends
from app.core.auth import get_optional_user

# Public endpoint
@router.get("/public", dependencies=[])
async def public_endpoint():
    return {"message": "Public data"}
```

## Current Protection Status

### ✅ Protected

- `GET /api/users/me`
- `GET /api/llms`

### ❌ Not Protected (Should Be)

- Most subscription endpoints
- Most cover letter endpoints
- Most file endpoints
- User CRUD endpoints (except /me)
- PDF generation
- Job analysis

## Testing Protection

### Test with Postman

1. **Without Token**: Should return `401 Unauthorized`

   ```
   GET /api/llms
   Authorization: (none)
   ```

2. **With Valid Token**: Should return `200 OK`

   ```
   GET /api/llms
   Authorization: Bearer <your_access_token>
   ```

3. **With Invalid Token**: Should return `401 Unauthorized`
   ```
   GET /api/llms
   Authorization: Bearer invalid_token
   ```

## Migration Plan

1. **Phase 1**: Protect critical endpoints (subscriptions, payments)
2. **Phase 2**: Protect user data endpoints
3. **Phase 3**: Protect resource endpoints (cover letters, files)
4. **Phase 4**: Review and protect remaining endpoints

## Best Practices

1. **Always verify ownership**: If an endpoint takes a `user_id`, verify the current user owns that ID
2. **Use `/me` endpoint**: Instead of `/users/{user_id}`, use `/users/me` when possible
3. **Protect by default**: When in doubt, protect the endpoint
4. **Document public endpoints**: Clearly document which endpoints are intentionally public
5. **Test thoroughly**: Test both authenticated and unauthenticated access

## Quick Reference

```python
# Protected endpoint
@router.get("/endpoint")
async def endpoint(current_user: UserResponse = Depends(get_current_user)):
    pass

# Public endpoint (no dependency)
@router.get("/public")
async def public_endpoint():
    pass

# Optional auth
@router.get("/flexible")
async def flexible(user: Optional[UserResponse] = Depends(get_optional_user)):
    pass
```
