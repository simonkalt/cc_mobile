# SMS Verification API Documentation

RESTful API endpoints for SMS-based verification codes using Twilio integration. Supports password reset, password change, and registration completion workflows.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Overview

The SMS Verification API provides secure two-factor authentication via SMS codes for:

- **Forgot Password**: Reset password when user forgets their password
- **Change Password**: Change password with SMS verification
- **Finish Registration**: Complete user registration with SMS verification

### Key Features

- 6-digit verification codes
- 10-minute expiration window
- Purpose-based verification (prevents code reuse across different flows)
- Automatic code cleanup after successful verification
- Phone number normalization (E.164 format)

---

## Endpoints

### 1. Send Verification Code

**POST** `/api/sms/send-code`

Send a 6-digit verification code via SMS to the user's registered phone number.

**Request Body:**

```json
{
  "email": "user@example.com", // Required if phone not provided
  "phone": "+1234567890", // Required if email not provided
  "purpose": "forgot_password" // Required: "forgot_password" | "change_password" | "finish_registration"
}
```

**Field Descriptions:**

- `email` (string, optional): User's email address. Either `email` or `phone` must be provided.
- `phone` (string, optional): User's phone number. Either `email` or `phone` must be provided.
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

- `400 Bad Request`: Invalid purpose or missing email/phone
- `404 Not Found`: User not found (except for forgot_password which returns success for security)
- `400 Bad Request`: User does not have a phone number registered
- `500 Internal Server Error`: Failed to send SMS
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/sms/send-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "purpose": "forgot_password"
  }'
```

---

### 2. Verify Code

**POST** `/api/sms/verify-code`

Verify a 6-digit code that was sent via SMS. This endpoint checks if the code is valid, not expired, and matches the purpose.

**Request Body:**

```json
{
  "email": "user@example.com", // Required if phone not provided
  "phone": "+1234567890", // Required if email not provided
  "code": "123456", // Required: 6-digit code
  "purpose": "forgot_password" // Required: Must match purpose used in send-code
}
```

**Field Descriptions:**

- `email` (string, optional): User's email address. Either `email` or `phone` must be provided.
- `phone` (string, optional): User's phone number. Either `email` or `phone` must be provided.
- `code` (string, required): 6-digit verification code received via SMS.
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

- `400 Bad Request`: Missing email/phone or invalid request
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

**Example cURL:**

```bash
curl -X POST http://localhost:8000/api/sms/verify-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "123456",
    "purpose": "forgot_password"
  }'
```

---

### 3. Reset Password (Forgot Password Flow)

**POST** `/api/sms/reset-password`

Reset user's password using a verified code. This is used in the "forgot password" flow.

**Request Body:**

```json
{
  "email": "user@example.com", // Required
  "code": "123456", // Required: Verification code
  "new_password": "newSecurePass123" // Required: New password
}
```

**Field Descriptions:**

- `email` (string, required): User's email address.
- `code` (string, required): 6-digit verification code that was sent and verified.
- `new_password` (string, required): New password for the account.

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
curl -X POST http://localhost:8000/api/sms/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "123456",
    "new_password": "newSecurePass123"
  }'
```

---

### 4. Change Password

**POST** `/api/sms/change-password`

Change user's password using a verified code. This is used when a logged-in user wants to change their password.

**Request Body:**

```json
{
  "user_id": "507f1f77bcf86cd799439011", // Required: User's MongoDB ObjectId
  "code": "123456", // Required: Verification code
  "new_password": "newSecurePass123" // Required: New password
}
```

**Field Descriptions:**

- `user_id` (string, required): User's MongoDB ObjectId.
- `code` (string, required): 6-digit verification code that was sent and verified.
- `new_password` (string, required): New password for the account.

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
curl -X POST http://localhost:8000/api/sms/change-password \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "507f1f77bcf86cd799439011",
    "code": "123456",
    "new_password": "newSecurePass123"
  }'
```

---

### 5. Complete Registration

**POST** `/api/sms/complete-registration`

Complete user registration by verifying the SMS code. This marks the user's email as verified and completes the registration process.

**Request Body:**

```json
{
  "email": "user@example.com", // Required
  "code": "123456" // Required: Verification code
}
```

**Field Descriptions:**

- `email` (string, required): User's email address.
- `code` (string, required): 6-digit verification code that was sent.

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
curl -X POST http://localhost:8000/api/sms/complete-registration \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "123456"
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
      const response = await axios.post(`${API_BASE_URL}/api/sms/send-code`, {
        email: email,
        purpose: "forgot_password",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your phone. Please check your SMS."
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
      const response = await axios.post(`${API_BASE_URL}/api/sms/verify-code`, {
        email: email,
        code: code,
        purpose: "forgot_password",
      });

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
        `${API_BASE_URL}/api/sms/reset-password`,
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
          <p>Enter the 6-digit code sent to your phone:</p>
          <input
            type="text"
            placeholder="123456"
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

      const response = await axios.post(`${API_BASE_URL}/api/sms/send-code`, {
        email: email,
        purpose: "change_password",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your phone. Please check your SMS."
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
        `${API_BASE_URL}/api/sms/change-password`,
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
          <p>Click the button below to receive a verification code via SMS.</p>
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
      const response = await axios.post(`${API_BASE_URL}/api/sms/send-code`, {
        email: email,
        purpose: "finish_registration",
      });

      if (response.data.success) {
        setMessage(
          "Verification code sent to your phone. Please check your SMS."
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
        `${API_BASE_URL}/api/sms/complete-registration`,
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
          <p>Please verify your phone number to complete registration.</p>
          <button onClick={handleRequestCode} disabled={loading}>
            {loading ? "Sending..." : "Send Verification Code"}
          </button>
        </div>
      )}

      {step === "verify" && (
        <form onSubmit={handleCompleteRegistration}>
          <p>Enter the 6-digit code sent to your phone:</p>
          <input
            type="text"
            placeholder="123456"
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
1. User enters email → POST /api/sms/send-code
   ↓
2. System sends SMS code → User receives code
   ↓
3. User enters code → POST /api/sms/verify-code (optional, can skip to step 4)
   ↓
4. User enters new password + code → POST /api/sms/reset-password
   ↓
5. Password reset → Redirect to login
```

### Change Password Flow

```
1. User clicks "Change Password" → POST /api/sms/send-code
   ↓
2. System sends SMS code → User receives code
   ↓
3. User enters code + new password → POST /api/sms/change-password
   ↓
4. Password changed → Success message
```

### Complete Registration Flow

```
1. User registers → POST /api/users/register
   ↓
2. User clicks "Complete Registration" → POST /api/sms/send-code
   ↓
3. System sends SMS code → User receives code
   ↓
4. User enters code → POST /api/sms/complete-registration
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

- Limit code requests to 3 per hour per email/phone
- Implement exponential backoff for failed attempts
- Show appropriate error messages for rate limit violations

### Phone Number Format

- Phone numbers are automatically normalized to E.164 format
- Accepts various formats: `+1234567890`, `(123) 456-7890`, `123-456-7890`
- US numbers without country code default to `+1`

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
| 500         | Internal Server Error | Twilio API error, SMS sending failed          |
| 503         | Service Unavailable   | Database connection unavailable               |

---

## Testing

### Test Scenarios

1. **Valid Flow Test**

   ```bash
   # 1. Send code
   curl -X POST http://localhost:8000/api/sms/send-code \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "purpose": "forgot_password"}'

   # 2. Verify code (use code from SMS)
   curl -X POST http://localhost:8000/api/sms/verify-code \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "code": "123456", "purpose": "forgot_password"}'

   # 3. Reset password
   curl -X POST http://localhost:8000/api/sms/reset-password \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "code": "123456", "new_password": "newPass123"}'
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

## Environment Variables

Ensure these are set in your `.env` file:

```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

---

## Notes

- **Phone Number Requirement**: Users must have a phone number registered in their profile to use SMS verification
- **Code Format**: All codes are 6-digit numeric strings (e.g., "123456")
- **Purpose Matching**: The `purpose` field must match between `send-code` and `verify-code`/action endpoints
- **Database Storage**: Verification codes are stored in the user document with expiration timestamps
- **Automatic Cleanup**: Codes are automatically removed after successful verification or expiration

---

## Support

For issues or questions:

1. Check the error response `detail` field for specific error messages
2. Verify Twilio credentials are correctly configured
3. Ensure user has a phone number in their profile
4. Check server logs for detailed error information
