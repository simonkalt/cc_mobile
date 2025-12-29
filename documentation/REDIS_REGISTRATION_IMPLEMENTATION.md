# Redis-Based Registration Implementation

## Overview

This document describes the implementation of Redis-based user registration, which stores temporary registration data in Redis instead of the main database until verification is complete.

## Architecture

### Flow Diagram

```
1. User fills registration form → Frontend sends registration data + send-code request
2. Backend stores registration data in Redis (10min TTL) → Sends verification code
3. User enters code → Backend verifies code from Redis
4. Backend retrieves registration data from Redis → Creates user in MongoDB
5. Redis entries automatically expire or are deleted after successful registration
```

### Key Components

1. **Redis Utilities** (`app/utils/redis_utils.py`)
   - Redis connection management
   - Functions for storing/retrieving registration data
   - Functions for storing/retrieving verification sessions

2. **Updated Models** (`app/models/email.py`, `app/models/sms.py`)
   - Added `registration_data` field to `SendVerificationCodeRequest`
   - Added `delivery_method` field to support both email and SMS

3. **Verification Service** (`app/services/verification_service.py`)
   - Updated to use Redis for registration flow
   - Falls back to MongoDB for existing user flows (forgot_password, change_password)

4. **User Service** (`app/services/user_service.py`)
   - Added `create_user_from_registration_data()` function
   - Creates users from Redis data with default personality profile

5. **API Routers** (`app/api/routers/email.py`, `app/api/routers/sms.py`)
   - Updated to handle registration flow with Redis
   - Complete registration endpoint creates user from Redis data

## Redis Key Structure

### Registration Data Key
```
registration:{email}:{code}
```
Stores:
- `name`: User's name
- `email`: User's email
- `phone`: User's phone (optional)
- `password`: Hashed password
- `preferences`: User preferences (optional)
- `address`: User address (optional)

### Verification Session Key
```
verification:{purpose}:{email}:{code}
```
Stores:
- `email`: User's email
- `code`: Verification code
- `purpose`: Purpose of verification
- `delivery_method`: "email" or "sms"
- `registration_key`: Link to registration data (for registration flow)

Both keys expire after 10 minutes automatically.

## API Endpoints

### Send Verification Code (Registration)

**POST** `/api/email/send-code` or `/api/sms/send-code`

**Request Body:**
```json
{
  "email": "user@example.com",
  "purpose": "finish_registration",
  "registration_data": {
    "name": "John Doe",
    "email": "user@example.com",
    "phone": "123-456-7890",
    "password": "plaintext_password",  // Backend hashes before storing
    "preferences": { ... }  // Optional
  },
  "delivery_method": "email"  // or "sms"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Verification code sent successfully",
  "expires_in_minutes": 10
}
```

### Complete Registration

**POST** `/api/email/complete-registration` or `/api/sms/complete-registration`

**Request Body:**
```json
{
  "email": "user@example.com",
  "code": "000000"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Registration completed successfully"
}
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
REDIS_HOST=redis-19455.c285.us-west-2-2.ec2.cloud.redislabs.com
REDIS_PORT=19455
REDIS_USERNAME=cc_user
REDIS_PASSWORD=8182702WasMyJourney$
REDIS_DB=0
REDIS_SSL=false  # Set to true if using SSL
REDIS_API_KEY=S5xau602m83665te8bpb67ccvu2xfevafxynqmopbo3cjjtnv23
```

### Dependencies

Add `redis` to `requirements.txt`:
```
redis
```

## Security Considerations

1. **Password Hashing**: Passwords are hashed before storing in Redis (even though Redis is temporary)
2. **TTL**: All Redis entries expire after 10 minutes automatically
3. **Code Uniqueness**: Uses email + code combination to prevent collisions
4. **Cleanup**: Redis entries are deleted after successful registration
5. **Redis Security**: Uses username/password authentication

## Error Handling

- **Expired Data**: If user takes >10 minutes, registration data expires → User must restart registration
- **Invalid Code**: Code doesn't match → User can request new code (new Redis entry created)
- **Redis Down**: Returns 503 Service Unavailable error
- **User Already Exists**: Returns 409 Conflict error

## Benefits

1. **No Database Pollution**: Unverified registrations never touch MongoDB
2. **Automatic Cleanup**: Redis TTL handles expiration automatically
3. **Performance**: Faster than database queries for temporary data
4. **Scalability**: Redis can handle millions of temporary entries efficiently
5. **Simplicity**: No need for background cleanup jobs

## Testing

### Test Registration Flow

```bash
# 1. Send verification code with registration data
curl -X POST http://localhost:8000/api/email/send-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "purpose": "finish_registration",
    "registration_data": {
      "name": "Test User",
      "email": "test@example.com",
      "phone": "123-456-7890",
      "password": "testpassword123"
    },
    "delivery_method": "email"
  }'

# 2. Complete registration (use code "000000" in stub mode)
curl -X POST http://localhost:8000/api/email/complete-registration \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "code": "000000"
  }'
```

## Migration Notes

- Existing user flows (forgot_password, change_password) continue to use MongoDB
- Only `finish_registration` flow uses Redis
- Backward compatible with existing endpoints

## Related Documentation

- [Registration with Redis](./REGISTRATION_WITH_REDIS.md) - Original design document
- [Email Verification API](./EMAIL_VERIFICATION_API.md) - Email verification endpoints
- [SMS Verification API](./SMS_VERIFICATION_API.md) - SMS verification endpoints

