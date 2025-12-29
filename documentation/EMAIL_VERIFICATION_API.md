# Email Verification API Documentation

RESTful API endpoints for email-based verification codes. Supports password reset, password change, and registration completion workflows. Currently uses stub implementations for email sending (logs requests) until SMTP provider is configured.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Overview

The Email Verification API provides secure two-factor authentication via email codes for:

- **Forgot Password**: Reset password when user forgets their password
- **Change Password**: Change password with email verification
- **Finish Registration**: Complete user registration with email verification

### Key Features

- 6-digit verification codes (currently hardcoded to "000000" for testing)
- 10-minute expiration window
- Purpose-based verification (prevents code reuse across different flows)
- Automatic code cleanup after successful verification
- Email stub implementation (logs requests until SMTP is configured)

### Current Implementation Status

⚠️ **Note**: Email sending is currently implemented as a stub. All email send requests are logged but no actual emails are sent. This allows testing the verification flow without an SMTP provider. The verification code is hardcoded to `"000000"` for testing purposes.

---

## Endpoints

### 1. Send Verification Code

**POST** `/api/email/send-code`

Send a 6-digit verification code via email to the user's registered email address.

**Request Body:**

```json
{
  "email": "user@example.com",
  "purpose": "forgot_password"
}
```

**Field Descriptions:**

- `email` (string, required): User's email address
- `purpose` (string, required): Purpose of verification. Must be one of:
  - `"forgot_password"`: For password reset flow
  - `"change_password"`: For changing password
  - `"finish_registration"`: For completing registration

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Verification code sent successfully",
  "expires_in_minutes": 10
}
```

**Error Responses:**

- `400 Bad Request`: Invalid purpose or missing email
- `404 Not Found`: User not found (except for forgot_password which returns success for security)
- `500 Internal Server Error`: Failed to send email (currently unlikely due to stub)
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/email/send-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "purpose": "forgot_password"
  }'
```

**Note**: Currently, this endpoint will log the email request but not send an actual email. Use code `"000000"` for verification.

---

### 2. Verify Code

**POST** `/api/email/verify-code`

Verify a 6-digit code that was sent via email. This endpoint checks if the code is valid, not expired, and matches the purpose.

**Request Body:**

```json
{
  "email": "user@example.com",
  "code": "000000",
  "purpose": "forgot_password"
}
```

**Field Descriptions:**

- `email` (string, required): User's email address
- `code` (string, required): 6-digit verification code received via email (currently `"000000"`)
- `purpose` (string, required): Purpose of verification. Must match the purpose used when sending the code.

**Response (200 OK) - Valid Code:**

```json
{
  "success": true,
  "message": "Code verified successfully",
  "verified": true
}
```

**Response (200 OK) - Invalid Code:**

```json
{
  "success": false,
  "message": "Invalid or expired code",
  "verified": false
}
```

**Error Responses:**

- `400 Bad Request`: Missing email or invalid request
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/email/verify-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "000000",
    "purpose": "forgot_password"
  }'
```

---

### 3. Reset Password (Forgot Password Flow)

**POST** `/api/email/reset-password`

Reset user's password using a verified code. This is used in the "forgot password" flow.

**Request Body:**

```json
{
  "email": "user@example.com",
  "code": "000000",
  "new_password": "newSecurePass123"
}
```

**Field Descriptions:**

- `email` (string, required): User's email address
- `code` (string, required): 6-digit verification code that was sent and verified (currently `"000000"`)
- `new_password` (string, required): New password for the account

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Password reset successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid or expired verification code
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/email/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "000000",
    "new_password": "newSecurePass123"
  }'
```

---

### 4. Change Password

**POST** `/api/email/change-password`

Change user's password using a verified code. This is used when a logged-in user wants to change their password.

**Request Body:**

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "code": "000000",
  "new_password": "newSecurePass123"
}
```

**Field Descriptions:**

- `user_id` (string, required): User's MongoDB ObjectId
- `code` (string, required): 6-digit verification code that was sent and verified (currently `"000000"`)
- `new_password` (string, required): New password for the account

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid or expired verification code
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/email/change-password \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "507f1f77bcf86cd799439011",
    "code": "000000",
    "new_password": "newSecurePass123"
  }'
```

---

### 5. Complete Registration

**POST** `/api/email/complete-registration`

Complete user registration by verifying the email code. This marks the user's email as verified and completes the registration process.

**Request Body:**

```json
{
  "email": "user@example.com",
  "code": "000000"
}
```

**Field Descriptions:**

- `email` (string, required): User's email address
- `code` (string, required): 6-digit verification code that was sent (currently `"000000"`)

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Registration completed successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid or expired verification code
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/email/complete-registration \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "000000"
  }'
```

---

## Frontend Integration Examples

### React/JavaScript Example - Forgot Password Flow

```javascript
// ForgotPassword.jsx
import React, { useState } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [step, setStep] = useState("request"); // 'request' | 'verify' | 'reset'
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Step 1: Request verification code
  const handleRequestCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(`${API_BASE_URL}/api/email/send-code`, {
        email: email,
        purpose: "forgot_password",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your email. Please check your inbox. " +
            "(Note: Currently using stub - use code '000000' for testing)"
        );
        setStep("verify");
      }
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to send verification code"
      );
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Verify code
  const handleVerifyCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/email/verify-code`,
        {
          email: email,
          code: code,
          purpose: "forgot_password",
        }
      );

      if (response.data.verified) {
        setMessage("Code verified! Please enter your new password.");
        setStep("reset");
      } else {
        setError("Invalid or expired code. Please try again.");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to verify code");
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Reset password
  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/email/reset-password`,
        {
          email: email,
          code: code,
          new_password: newPassword,
        }
      );

      if (response.data.success) {
        setMessage("Password reset successfully! You can now login.");
        // Redirect to login page
        setTimeout(() => {
          window.location.href = "/login";
        }, 2000);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-password">
      <h2>Reset Password</h2>

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      {step === "request" && (
        <form onSubmit={handleRequestCode}>
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? "Sending..." : "Send Verification Code"}
          </button>
        </form>
      )}

      {step === "verify" && (
        <form onSubmit={handleVerifyCode}>
          <p>Enter the 6-digit code sent to your email:</p>
          <input
            type="text"
            placeholder="000000"
            value={code}
            onChange={(e) =>
              setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            maxLength={6}
            required
          />
          <button type="submit" disabled={loading || code.length !== 6}>
            {loading ? "Verifying..." : "Verify Code"}
          </button>
          <button type="button" onClick={() => setStep("request")}>
            Resend Code
          </button>
        </form>
      )}

      {step === "reset" && (
        <form onSubmit={handleResetPassword}>
          <input
            type="password"
            placeholder="New Password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Resetting..." : "Reset Password"}
          </button>
        </form>
      )}
    </div>
  );
}

export default ForgotPassword;
```

---

### React/JavaScript Example - Change Password Flow

```javascript
// ChangePassword.jsx
import React, { useState } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

function ChangePassword({ userId }) {
  const [step, setStep] = useState("request"); // 'request' | 'verify' | 'change'
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Step 1: Request verification code
  const handleRequestCode = async () => {
    setLoading(true);
    setError("");

    try {
      // First, get user's email from user data
      const userResponse = await axios.get(
        `${API_BASE_URL}/api/users/${userId}`
      );
      const email = userResponse.data.email;

      const response = await axios.post(`${API_BASE_URL}/api/email/send-code`, {
        email: email,
        purpose: "change_password",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your email. Please check your inbox. " +
            "(Note: Currently using stub - use code '000000' for testing)"
        );
        setStep("verify");
      }
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to send verification code"
      );
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Change password
  const handleChangePassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/email/change-password`,
        {
          user_id: userId,
          code: code,
          new_password: newPassword,
        }
      );

      if (response.data.success) {
        setMessage("Password changed successfully!");
        // Clear form
        setCode("");
        setNewPassword("");
        setStep("request");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="change-password">
      <h2>Change Password</h2>

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      {step === "request" && (
        <div>
          <p>
            Click the button below to receive a verification code via email.
          </p>
          <button onClick={handleRequestCode} disabled={loading}>
            {loading ? "Sending..." : "Send Verification Code"}
          </button>
        </div>
      )}

      {step === "verify" && (
        <form onSubmit={handleChangePassword}>
          <input
            type="text"
            placeholder="Enter 6-digit code"
            value={code}
            onChange={(e) =>
              setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            maxLength={6}
            required
          />
          <input
            type="password"
            placeholder="New Password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
          />
          <button type="submit" disabled={loading || code.length !== 6}>
            {loading ? "Changing..." : "Change Password"}
          </button>
          <button type="button" onClick={() => setStep("request")}>
            Resend Code
          </button>
        </form>
      )}
    </div>
  );
}

export default ChangePassword;
```

---

### React/JavaScript Example - Complete Registration Flow

```javascript
// CompleteRegistration.jsx
import React, { useState } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

function CompleteRegistration({ email }) {
  const [step, setStep] = useState("request"); // 'request' | 'verify'
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Step 1: Request verification code
  const handleRequestCode = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(`${API_BASE_URL}/api/email/send-code`, {
        email: email,
        purpose: "finish_registration",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your email. Please check your inbox. " +
            "(Note: Currently using stub - use code '000000' for testing)"
        );
        setStep("verify");
      }
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to send verification code"
      );
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Complete registration
  const handleCompleteRegistration = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/email/complete-registration`,
        {
          email: email,
          code: code,
        }
      );

      if (response.data.success) {
        setMessage(
          "Registration completed successfully! Redirecting to login..."
        );
        // Redirect to login page
        setTimeout(() => {
          window.location.href = "/login";
        }, 2000);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to complete registration");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="complete-registration">
      <h2>Complete Registration</h2>

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      {step === "request" && (
        <div>
          <p>Please verify your email address to complete registration.</p>
          <button onClick={handleRequestCode} disabled={loading}>
            {loading ? "Sending..." : "Send Verification Code"}
          </button>
        </div>
      )}

      {step === "verify" && (
        <form onSubmit={handleCompleteRegistration}>
          <p>Enter the 6-digit code sent to your email:</p>
          <input
            type="text"
            placeholder="000000"
            value={code}
            onChange={(e) =>
              setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            maxLength={6}
            required
          />
          <button type="submit" disabled={loading || code.length !== 6}>
            {loading ? "Verifying..." : "Complete Registration"}
          </button>
          <button type="button" onClick={() => setStep("request")}>
            Resend Code
          </button>
        </form>
      )}
    </div>
  );
}

export default CompleteRegistration;
```

---

## Workflow Diagrams

### Forgot Password Flow

```
1. User enters email → POST /api/email/send-code
   ↓
2. System logs email request → User uses code "000000" (stub mode)
   ↓
3. User enters code → POST /api/email/verify-code (optional, can skip to step 4)
   ↓
4. User enters new password + code → POST /api/email/reset-password
   ↓
5. Password reset → Redirect to login
```

### Change Password Flow

```
1. User clicks "Change Password" → POST /api/email/send-code
   ↓
2. System logs email request → User uses code "000000" (stub mode)
   ↓
3. User enters code + new password → POST /api/email/change-password
   ↓
4. Password changed → Success message
```

### Complete Registration Flow

```
1. User registers → POST /api/users/register
   ↓
2. User clicks "Complete Registration" → POST /api/email/send-code
   ↓
3. System logs email request → User uses code "000000" (stub mode)
   ↓
4. User enters code → POST /api/email/complete-registration
   ↓
5. Registration complete → Email verified → Redirect to login
```

---

## Security Considerations

### Code Expiration

- Verification codes expire after **10 minutes**
- Expired codes cannot be used
- Users must request a new code if expired

### Code Reuse Prevention

- Each code can only be used **once**
- After successful verification, the code is cleared from the database
- Codes are purpose-specific (cannot use forgot_password code for change_password)

### Rate Limiting Recommendations

While not implemented in the API, consider implementing rate limiting on the frontend:

- Limit code requests to 3 per hour per email
- Implement exponential backoff for failed attempts
- Show appropriate error messages for rate limit violations

### Error Handling Best Practices

- **Forgot Password**: Always returns success even if user doesn't exist (prevents email enumeration)
- **Other Flows**: Return specific error messages for debugging
- Log all verification attempts for security auditing

---

## Error Codes Reference

| Status Code | Meaning               | Common Causes                                 |
| ----------- | --------------------- | --------------------------------------------- |
| 200         | Success               | Request completed successfully                |
| 400         | Bad Request           | Invalid purpose, missing fields, invalid code |
| 404         | Not Found             | User not found (except forgot_password)       |
| 500         | Internal Server Error | Email sending failed (unlikely with stub)     |
| 503         | Service Unavailable   | Database connection unavailable               |

---

## Testing

### Test Scenarios

1. **Valid Flow Test**

   ```bash
   # 1. Send code
   curl -X POST http://localhost:8000/api/email/send-code \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "purpose": "forgot_password"}'

   # 2. Verify code (use "000000" in stub mode)
   curl -X POST http://localhost:8000/api/email/verify-code \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "code": "000000", "purpose": "forgot_password"}'

   # 3. Reset password
   curl -X POST http://localhost:8000/api/email/reset-password \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "code": "000000", "new_password": "newPass123"}'
   ```

2. **Expired Code Test**

   - Wait 10+ minutes after sending code
   - Attempt to verify → Should return `verified: false`

3. **Invalid Code Test**

   - Send code
   - Attempt to verify with wrong code → Should return `verified: false`

4. **Wrong Purpose Test**
   - Send code with `purpose: "forgot_password"`
   - Attempt to verify with `purpose: "change_password"` → Should fail

---

## SMTP Provider Integration (Future)

When ready to integrate an SMTP provider, update the following:

### 1. Update `app/utils/email_utils.py`

Replace the `send_email()` function stub with actual SMTP implementation:

```python
def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email message via SMTP provider
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    try:
        # Configure SMTP settings from environment variables
        smtp_server = settings.SMTP_SERVER
        smtp_port = settings.SMTP_PORT
        smtp_username = settings.SMTP_USERNAME
        smtp_password = settings.SMTP_PASSWORD
        from_email = settings.FROM_EMAIL

        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {str(e)}")
        return False
```

### 2. Update `app/utils/sms_utils.py`

Change `generate_verification_code()` to return random codes:

```python
def generate_verification_code() -> str:
    """
    Generate a random 6-digit verification code
    """
    return str(random.randint(100000, 999999))
```

### 3. Add Environment Variables

Add to your `.env` file:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@yourdomain.com
```

---

## Current Implementation Notes

### Stub Mode

- **Email Sending**: All email send requests are logged but no actual emails are sent
- **Verification Code**: Hardcoded to `"000000"` for testing
- **Logging**: Check server logs for email send attempts (look for `[EMAIL STUB]` messages)

### Code Generation

- Currently uses the same `generate_verification_code()` function as SMS
- Returns `"000000"` until SMTP provider is configured
- Once SMTP is integrated, codes will be randomly generated

### Database Storage

- Verification codes are stored in the user document with expiration timestamps
- Codes include both `email` and `phone_number` fields (depending on method used)
- Codes are automatically removed after successful verification or expiration

---

## Support

For issues or questions:

1. Check the error response `detail` field for specific error messages
2. Verify user exists and has an email address
3. Check server logs for detailed error information and email stub messages
4. Remember to use code `"000000"` when testing in stub mode

---

## Related Documentation

- [SMS Verification API](./SMS_VERIFICATION_API.md) - SMS-based verification endpoints
- [User API Documentation](./USER_API_DOCUMENTATION.md) - User registration and management
- [User Schema Guide](./USER_SCHEMA_GUIDE.md) - Complete user schema documentation
