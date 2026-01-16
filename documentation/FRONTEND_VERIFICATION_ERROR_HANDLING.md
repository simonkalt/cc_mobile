# Frontend Verification Code Error Handling Guide

This document explains how to handle verification code errors in the frontend, specifically the "verification code already used" scenario.

## Overview

The verification code system allows codes to be **verified multiple times** (e.g., to enable UI buttons) but can only be **used once** for the actual action (password reset, password change, etc.). This design allows users to verify their code before submitting the final form.

---

## Error Scenarios

### 1. Verification Code Already Used

**When it occurs:**
- User successfully verifies a code (e.g., to enable the "Reset Password" button)
- User completes the password reset action
- User tries to use the same code again (either by resubmitting the form or trying a different action)

**Error Response:**
```json
{
  "detail": "Verification code has already been used"
}
```

**HTTP Status:** `400 Bad Request`

---

## API Endpoints

### Email Verification Endpoints

- **Verify Code:** `POST /api/email/verify-code`
- **Reset Password:** `POST /api/email/reset-password`
- **Change Password:** `POST /api/email/change-password`

### SMS Verification Endpoints

- **Verify Code:** `POST /api/sms/verify-code`
- **Reset Password:** `POST /api/sms/reset-password`
- **Change Password:** `POST /api/sms/change-password`

---

## Error Handling Implementation

### Example: Password Reset Flow

```typescript
// Example TypeScript/React implementation

interface ResetPasswordRequest {
  email: string;
  code: string;
  new_password: string;
}

interface ApiError {
  detail: string;
  status?: number;
}

async function resetPassword(data: ResetPasswordRequest): Promise<void> {
  try {
    const response = await fetch('/api/email/reset-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error: ApiError = await response.json();
      
      // Handle "code already used" error
      if (error.detail === 'Verification code has already been used') {
        // Show user-friendly message and prompt for new code
        throw new VerificationCodeUsedError(
          'This verification code has already been used. Please request a new code.',
          'CODE_ALREADY_USED'
        );
      }
      
      // Handle other errors
      if (error.detail === 'Invalid or expired verification code') {
        throw new InvalidCodeError(
          'The verification code is invalid or has expired. Please request a new code.',
          'INVALID_CODE'
        );
      }
      
      // Generic error
      throw new Error(error.detail || 'Failed to reset password');
    }

    const result = await response.json();
    return result;
    
  } catch (error) {
    if (error instanceof VerificationCodeUsedError) {
      // Handle code already used
      handleCodeAlreadyUsed();
    } else {
      // Handle other errors
      handleGenericError(error);
    }
    throw error;
  }
}

// Custom error classes
class VerificationCodeUsedError extends Error {
  constructor(message: string, public code: string) {
    super(message);
    this.name = 'VerificationCodeUsedError';
  }
}

class InvalidCodeError extends Error {
  constructor(message: string, public code: string) {
    super(message);
    this.name = 'InvalidCodeError';
  }
}
```

---

## UI/UX Recommendations

### 1. Code Already Used Error

**Recommended User Experience:**

1. **Show Clear Error Message**
   ```
   "This verification code has already been used. 
   Please request a new verification code to continue."
   ```

2. **Provide Action Buttons**
   - **"Request New Code"** button - triggers a new code to be sent
   - **"Cancel"** button - allows user to cancel the flow

3. **Disable Form Submission**
   - Disable the "Reset Password" or "Change Password" button
   - Clear the code input field
   - Show visual indicator that a new code is needed

4. **Auto-Request New Code (Optional)**
   - Automatically request a new code when this error occurs
   - Show a message: "A new verification code has been sent to your email"

### Example UI Component

```tsx
// React component example

import React, { useState } from 'react';

interface ResetPasswordFormProps {
  email: string;
}

export function ResetPasswordForm({ email }: ResetPasswordFormProps) {
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<'CODE_USED' | 'INVALID_CODE' | 'OTHER' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [codeVerified, setCodeVerified] = useState(false);

  const handleVerifyCode = async () => {
    try {
      const response = await fetch('/api/email/verify-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          code,
          purpose: 'forgot_password',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        setError(error.detail || 'Invalid verification code');
        setErrorType('INVALID_CODE');
        setCodeVerified(false);
        return;
      }

      setCodeVerified(true);
      setError(null);
      setErrorType(null);
    } catch (err) {
      setError('Failed to verify code. Please try again.');
      setErrorType('OTHER');
      setCodeVerified(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setErrorType(null);

    try {
      const response = await fetch('/api/email/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          code,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        
        if (error.detail === 'Verification code has already been used') {
          setErrorType('CODE_USED');
          setError(
            'This verification code has already been used. Please request a new code.'
          );
          setCodeVerified(false);
          setCode(''); // Clear the code
          return;
        }
        
        if (error.detail === 'Invalid or expired verification code') {
          setErrorType('INVALID_CODE');
          setError('The verification code is invalid or has expired.');
          setCodeVerified(false);
          return;
        }
        
        setErrorType('OTHER');
        setError(error.detail || 'Failed to reset password');
        return;
      }

      // Success - redirect or show success message
      alert('Password reset successfully!');
      // Redirect to login page
      window.location.href = '/login';
      
    } catch (err) {
      setErrorType('OTHER');
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRequestNewCode = async () => {
    try {
      const response = await fetch('/api/email/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          purpose: 'forgot_password',
        }),
      });

      if (response.ok) {
        setError(null);
        setErrorType(null);
        setCode('');
        setCodeVerified(false);
        alert('A new verification code has been sent to your email.');
      }
    } catch (err) {
      setError('Failed to request new code. Please try again.');
    }
  };

  return (
    <form onSubmit={handleResetPassword}>
      <div>
        <label>Verification Code</label>
        <input
          type="text"
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            setCodeVerified(false);
            setError(null);
          }}
          placeholder="Enter 6-digit code"
          maxLength={6}
        />
        <button
          type="button"
          onClick={handleVerifyCode}
          disabled={code.length !== 6}
        >
          Verify Code
        </button>
        {codeVerified && (
          <span className="success">✓ Code verified</span>
        )}
      </div>

      <div>
        <label>New Password</label>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="Enter new password"
        />
      </div>

      {error && (
        <div className={`error ${errorType}`}>
          <p>{error}</p>
          {errorType === 'CODE_USED' && (
            <button
              type="button"
              onClick={handleRequestNewCode}
              className="btn-primary"
            >
              Request New Code
            </button>
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={!codeVerified || !newPassword || isLoading}
      >
        {isLoading ? 'Resetting...' : 'Reset Password'}
      </button>
    </form>
  );
}
```

---

## Error Response Format

All error responses follow this format:

```typescript
interface ErrorResponse {
  detail: string;  // Human-readable error message
  status?: number; // HTTP status code (optional)
}
```

### Common Error Messages

| Error Message | HTTP Status | Meaning | Action Required |
|--------------|-------------|---------|----------------|
| `"Verification code has already been used"` | 400 | Code was used for an action | Request new code |
| `"Invalid or expired verification code"` | 400 | Code is wrong or expired | Request new code |
| `"User not found"` | 404 | Email/phone not in system | Check input |
| `"Database connection unavailable"` | 503 | Server issue | Retry later |

---

## Best Practices

### 1. Code Verification Flow

**Recommended Flow:**
1. User enters code
2. User clicks "Verify Code" button (optional - can auto-verify on blur)
3. Code is verified via `/api/email/verify-code` or `/api/sms/verify-code`
4. If valid, enable the "Reset Password" / "Change Password" button
5. User enters new password
6. User submits form
7. Code is verified again in the reset/change endpoint (as a security measure)
8. If code was already used, show error and prompt for new code

### 2. Error State Management

- **Clear error state** when user modifies the code input
- **Show inline validation** for code format (6 digits)
- **Disable submit button** until code is verified
- **Show loading state** during API calls

### 3. User Feedback

- **Success:** Show checkmark or success message when code is verified
- **Error:** Show clear error message with actionable next steps
- **Loading:** Show spinner or loading text during API calls

### 4. Security Considerations

- **Don't store codes** in localStorage or sessionStorage
- **Clear code input** after successful password reset
- **Rate limit** code verification requests on the frontend
- **Show generic errors** for security (don't reveal if email exists)

---

## Example Error Handling Utility

```typescript
// utils/verificationErrors.ts

export enum VerificationErrorType {
  CODE_ALREADY_USED = 'CODE_ALREADY_USED',
  INVALID_CODE = 'INVALID_CODE',
  EXPIRED_CODE = 'EXPIRED_CODE',
  USER_NOT_FOUND = 'USER_NOT_FOUND',
  NETWORK_ERROR = 'NETWORK_ERROR',
  UNKNOWN = 'UNKNOWN',
}

export interface VerificationError {
  type: VerificationErrorType;
  message: string;
  userMessage: string;
  actionRequired: 'REQUEST_NEW_CODE' | 'RETRY' | 'CONTACT_SUPPORT' | 'NONE';
}

export function parseVerificationError(
  errorResponse: { detail: string },
  statusCode?: number
): VerificationError {
  const detail = errorResponse.detail.toLowerCase();

  if (detail.includes('already been used') || detail.includes('already used')) {
    return {
      type: VerificationErrorType.CODE_ALREADY_USED,
      message: errorResponse.detail,
      userMessage: 'This verification code has already been used. Please request a new code.',
      actionRequired: 'REQUEST_NEW_CODE',
    };
  }

  if (detail.includes('invalid') || detail.includes('expired')) {
    return {
      type: detail.includes('expired')
        ? VerificationErrorType.EXPIRED_CODE
        : VerificationErrorType.INVALID_CODE,
      message: errorResponse.detail,
      userMessage: 'The verification code is invalid or has expired. Please request a new code.',
      actionRequired: 'REQUEST_NEW_CODE',
    };
  }

  if (detail.includes('not found') || statusCode === 404) {
    return {
      type: VerificationErrorType.USER_NOT_FOUND,
      message: errorResponse.detail,
      userMessage: 'We could not find an account with that email address.',
      actionRequired: 'NONE',
    };
  }

  if (statusCode === 503 || detail.includes('unavailable')) {
    return {
      type: VerificationErrorType.NETWORK_ERROR,
      message: errorResponse.detail,
      userMessage: 'Service temporarily unavailable. Please try again in a moment.',
      actionRequired: 'RETRY',
    };
  }

  return {
    type: VerificationErrorType.UNKNOWN,
    message: errorResponse.detail,
    userMessage: 'An unexpected error occurred. Please try again.',
    actionRequired: 'RETRY',
  };
}

// Usage example
try {
  const response = await fetch('/api/email/reset-password', { ... });
  if (!response.ok) {
    const error = await response.json();
    const parsedError = parseVerificationError(error, response.status);
    
    // Show parsedError.userMessage to user
    // Handle parsedError.actionRequired
    if (parsedError.actionRequired === 'REQUEST_NEW_CODE') {
      // Trigger request new code flow
    }
  }
} catch (err) {
  // Handle network errors
}
```

---

## Testing Checklist

When implementing verification code error handling, test these scenarios:

- [ ] User verifies code, then resets password successfully
- [ ] User tries to reset password with already-used code
- [ ] User enters invalid code
- [ ] User enters expired code
- [ ] User requests new code after error
- [ ] Network error during verification
- [ ] Network error during password reset
- [ ] User modifies code after verification
- [ ] Form validation (code length, password requirements)
- [ ] Loading states during API calls
- [ ] Error messages clear when user modifies input

---

## Summary

**Key Points:**
1. Codes can be **verified multiple times** but **used only once**
2. The "code already used" error occurs when trying to use a code that was already consumed
3. Always provide a **"Request New Code"** option when this error occurs
4. **Clear the code input** and reset verification state when this error happens
5. Use **clear, actionable error messages** to guide users

**Recommended Error Flow:**
```
Error: "Code already used"
  ↓
Show error message
  ↓
Disable form submission
  ↓
Clear code input
  ↓
Show "Request New Code" button
  ↓
User clicks button → New code sent
  ↓
User enters new code → Process continues
```

