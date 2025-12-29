# Registration with Redis Temporary Storage

## Why Redis?

Redis is an excellent choice for storing temporary registration data because:

1. **Automatic Expiration**: Redis supports TTL (Time To Live) natively, so registration data automatically expires after a set time (e.g., 10 minutes), preventing data buildup
2. **Fast Access**: Redis is an in-memory data store, providing extremely fast read/write operations
3. **Atomic Operations**: Redis operations are atomic, preventing race conditions during verification
4. **No Database Pollution**: Temporary registration data never touches your main database, keeping it clean
5. **Scalable**: Redis can handle high volumes of temporary data efficiently
6. **Simple Cleanup**: No need for background jobs to clean up expired data - Redis handles it automatically

## Architecture Overview

```
1. User fills registration form → Frontend sends registration data + send-code request
2. Backend stores registration data in Redis (10min TTL) → Sends verification code
3. User enters code → Backend verifies code
4. Backend retrieves registration data from Redis → Creates user in database
5. Redis entry automatically expires (or is deleted after successful registration)
```

## Backend Implementation

### 1. Modified Send Code Endpoint

**POST** `/api/email/send-code` or `/api/sms/send-code`

**Request Body for Registration:**

```json
{
  "email": "user@example.com",
  "phone": "123-456-7890",  // Optional, required for SMS
  "purpose": "finish_registration",
  "registration_data": {  // NEW: Include registration data
    "name": "John Doe",
    "email": "user@example.com",
    "phone": "123-456-7890",
    "password": "hashed_password_here"  // Hash before storing in Redis
  },
  "delivery_method": "sms"  // or "email"
}
```

**Backend Python/FastAPI Implementation:**

```python
import redis
import json
import hashlib
from datetime import timedelta

# Initialize Redis client
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)

async def send_verification_code(
    email: str,
    phone: Optional[str] = None,
    purpose: str = "forgot_password",
    registration_data: Optional[dict] = None,
    delivery_method: str = "email"
):
    """
    Send verification code and optionally store registration data in Redis.
    """
    # Generate verification code
    code = generate_verification_code()  # Returns "000000" for testing
    
    # Create unique key for this verification session
    session_key = f"verification:{purpose}:{email}:{code}"
    
    # Store verification data in Redis
    verification_data = {
        "email": email,
        "phone": phone,
        "code": code,
        "purpose": purpose,
        "delivery_method": delivery_method,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # If this is registration, also store registration data
    if purpose == "finish_registration" and registration_data:
        # Hash password before storing (even in Redis)
        if "password" in registration_data:
            registration_data["password"] = hash_password(registration_data["password"])
        
        # Store registration data with a separate key for easy retrieval
        registration_key = f"registration:{email}:{code}"
        redis_client.setex(
            registration_key,
            timedelta(minutes=10),  # 10 minute expiration
            json.dumps(registration_data)
        )
        
        # Link registration key to verification session
        verification_data["registration_key"] = registration_key
    
    # Store verification session in Redis (10 minute TTL)
    redis_client.setex(
        session_key,
        timedelta(minutes=10),
        json.dumps(verification_data)
    )
    
    # Send code via SMS or Email
    if delivery_method == "sms":
        await send_sms_code(phone, code)
    else:
        await send_email_code(email, code)
    
    return {
        "success": True,
        "message": "Verification code sent successfully",
        "expires_in_minutes": 10
    }
```

### 2. Modified Complete Registration Endpoint

**POST** `/api/email/complete-registration` or `/api/sms/complete-registration`

**Backend Implementation:**

```python
async def complete_registration(
    email: str,
    code: str,
    delivery_method: str = "email"
):
    """
    Complete registration by verifying code and creating user from Redis data.
    """
    # Verify the code first
    session_key = f"verification:finish_registration:{email}:{code}"
    verification_data_json = redis_client.get(session_key)
    
    if not verification_data_json:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code"
        )
    
    verification_data = json.loads(verification_data_json)
    
    # Retrieve registration data from Redis
    registration_key = verification_data.get("registration_key")
    if not registration_key:
        raise HTTPException(
            status_code=400,
            detail="Registration data not found"
        )
    
    registration_data_json = redis_client.get(registration_key)
    if not registration_data_json:
        raise HTTPException(
            status_code=400,
            detail="Registration data expired. Please register again."
        )
    
    registration_data = json.loads(registration_data_json)
    
    # Create user in database
    try:
        user = await create_user(
            name=registration_data["name"],
            email=registration_data["email"],
            phone=registration_data.get("phone"),
            password=registration_data["password"],  # Already hashed
            is_email_verified=True  # Mark as verified since they completed verification
        )
        
        # Clean up Redis entries
        redis_client.delete(session_key)
        redis_client.delete(registration_key)
        
        return {
            "success": True,
            "message": "Registration completed successfully",
            "user": user
        }
        
    except Exception as e:
        # If user creation fails, Redis entries will expire automatically
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to complete registration"
        )
```

### 3. Alternative: Single Redis Key Approach

Instead of two keys, you could use a single key:

```python
# Store everything in one key
registration_key = f"registration:{email}:{code}"

registration_data = {
    "name": "John Doe",
    "email": "user@example.com",
    "phone": "123-456-7890",
    "password": "hashed_password",
    "code": code,
    "purpose": "finish_registration",
    "delivery_method": "sms",
    "created_at": datetime.utcnow().isoformat()
}

redis_client.setex(
    registration_key,
    timedelta(minutes=10),
    json.dumps(registration_data)
)
```

## Frontend Implementation

### Updated API Service

```javascript
// In src/services/api.js

async sendVerificationCodeForRegistration(email, phone, registrationData, deliveryMethod) {
  const data = {
    email,
    purpose: "finish_registration",
    delivery_method: deliveryMethod, // "sms" or "email"
    registration_data: {
      name: registrationData.name,
      email: registrationData.email,
      phone: registrationData.phone,
      password: registrationData.password, // Backend should hash this
    }
  };
  
  if (deliveryMethod === "sms") {
    data.phone = phone;
    return this.post("/api/sms/send-code", data);
  } else {
    return this.post("/api/email/send-code", data);
  }
}
```

### Updated Registration Flow

1. **Registration Form** → User fills out form (name, email, phone, password)
2. **Send Code** → Call `sendVerificationCodeForRegistration()` with registration data
3. **Verify Code** → User enters code
4. **Complete Registration** → Backend creates user from Redis data

## Redis Key Structure

```
verification:finish_registration:{email}:{code}  → Verification session data
registration:{email}:{code}  → Registration data (name, email, phone, hashed password)
```

Both keys expire after 10 minutes automatically.

## Security Considerations

1. **Password Hashing**: Always hash passwords before storing in Redis (even though Redis is temporary)
2. **Code Uniqueness**: Use email + code combination to prevent collisions
3. **TTL**: Set appropriate expiration (10 minutes recommended)
4. **Redis Security**: 
   - Use password authentication for Redis
   - Use SSL/TLS for Redis connections in production
   - Restrict Redis access to backend servers only

## Environment Variables

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # Optional but recommended
REDIS_DB=0
REDIS_SSL=false  # Set to true in production
```

## Error Handling

- **Expired Data**: If user takes >10 minutes, registration data expires → User must restart registration
- **Invalid Code**: Code doesn't match → User can request new code (new Redis entry created)
- **Redis Down**: Fallback to database storage or return error (depending on requirements)

## Benefits Over Database Storage

1. **No Database Pollution**: Unverified registrations never touch your main database
2. **Automatic Cleanup**: Redis TTL handles expiration automatically
3. **Performance**: Faster than database queries for temporary data
4. **Scalability**: Redis can handle millions of temporary entries efficiently
5. **Simplicity**: No need for background cleanup jobs

## Migration Path

If you're currently using database storage:
1. Deploy Redis infrastructure
2. Update send-code endpoint to use Redis
3. Update complete-registration endpoint to read from Redis
4. Keep database registration endpoint for backward compatibility (deprecated)
5. Monitor Redis usage and performance

