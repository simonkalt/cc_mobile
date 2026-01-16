# Zoho Mail API Setup Checklist

This checklist will guide you through setting up Zoho Mail API integration to replace SMTP2Go for sending verification emails from `no-reply@saimonsoft.com`.

## Prerequisites

- Zoho Mail account with domain `saimonsoft.com` configured
- Admin access to Zoho Developer Console
- Access to your application's environment variables (local `.env` and Render)

---

## Step 1: Create Zoho API Application

1. **Go to Zoho Developer Console**

   - Visit: https://accounts.zoho.com/developerconsole
   - Sign in with your Zoho account

2. **Create a New Application**

   - Click "Add Client" or "Create Client"
   - Select "Server-based Applications" as the client type
   - Fill in the application details:
     - **Client Name**: `SaimonSoft Email Service` (or your preferred name)
     - **Homepage URL**: `https://your-app-domain.com` (or `http://localhost:8000` for development)
     - **Authorized Redirect URIs**:
       - For development: `http://localhost:8000/oauth/callback`
       - For production: `https://your-app-domain.com/oauth/callback`
   - Click "Create"

3. **Save Your Credentials**
   - **Client ID**: Copy this value (you'll need it for `ZOHO_CLIENT_ID`)
   - **Client Secret**: Copy this value (you'll need it for `ZOHO_CLIENT_SECRET`)
   - ⚠️ **Important**: Keep these secure and never commit them to version control

---

## Step 2: Generate Refresh Token

1. **Get Authorization Code**

   - Construct this URL (replace `YOUR_CLIENT_ID` with your actual Client ID):
     ```
     https://accounts.zoho.com/oauth/v2/auth?scope=ZohoMail.messages.CREATE,ZohoMail.accounts.READ&client_id=YOUR_CLIENT_ID&response_type=code&access_type=offline&redirect_uri=http://localhost:8000/oauth/callback
     ```
   - Open this URL in your browser
   - Sign in with your Zoho account
   - Authorize the application
   - You'll be redirected to `http://localhost:8000/oauth/callback?code=AUTHORIZATION_CODE`
   - Copy the `code` parameter from the URL (this is your authorization code)

2. **Exchange Authorization Code for Refresh Token**
   - Use curl or Postman to make this request:
     ```bash
     curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
       -d "grant_type=authorization_code" \
       -d "client_id=YOUR_CLIENT_ID" \
       -d "client_secret=YOUR_CLIENT_SECRET" \
       -d "redirect_uri=http://localhost:8000/oauth/callback" \
       -d "code=AUTHORIZATION_CODE"
     ```
   - The response will contain:
     ```json
     {
       "access_token": "...",
       "refresh_token": "...",
       "expires_in": 3600
     }
     ```
   - **Save the `refresh_token`** (you'll need it for `ZOHO_REFRESH_TOKEN`)
   - ⚠️ **Important**: The refresh token doesn't expire, but keep it secure

---

## Step 3: Get Account ID (ZUID)

1. **Get Your Account ID**

   - First, get a new access token using your refresh token:
     ```bash
     curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
       -d "refresh_token=YOUR_REFRESH_TOKEN" \
       -d "client_id=YOUR_CLIENT_ID" \
       -d "client_secret=YOUR_CLIENT_SECRET" \
       -d "grant_type=refresh_token"
     ```
   - Copy the `access_token` from the response

   - Now get your account information:
     ```bash
     curl -X GET "https://mail.zoho.com/api/accounts" \
       -H "Authorization: Zoho-oauthtoken YOUR_ACCESS_TOKEN"
     ```
   - The response will list your accounts. Find the account for `saimonsoft.com`
   - Look for the `accountId`, `zuid`, or `id` field
   - **Save this value** (you'll need it for `ZOHO_ACCOUNT_ID`)

   **Alternative Method:**

   - Log into Zoho Mail web interface
   - Check the URL or account settings - the account ID may be visible
   - Or use the Zoho Mail API documentation to find your organization ID (ZOID) and user ID (ZUID)
   - The account ID might also be your email address or a numeric ID

---

## Step 4: Configure Environment Variables

### Local Development (.env file)

Add these variables to your `.env` file:

```env
# Zoho Mail API Configuration
ZOHO_CLIENT_ID=your_client_id_here
ZOHO_CLIENT_SECRET=your_client_secret_here
ZOHO_REFRESH_TOKEN=your_refresh_token_here
ZOHO_ACCOUNT_ID=your_account_id_here
FROM_EMAIL=no-reply@saimonsoft.com
```

### Production (Render)

1. **Go to Render Dashboard**

   - Navigate to your service
   - Go to "Environment" tab
   - Add the following environment variables:

   | Variable Name        | Value                     | Description          |
   | -------------------- | ------------------------- | -------------------- |
   | `ZOHO_CLIENT_ID`     | `your_client_id`          | From Step 1          |
   | `ZOHO_CLIENT_SECRET` | `your_client_secret`      | From Step 1          |
   | `ZOHO_REFRESH_TOKEN` | `your_refresh_token`      | From Step 2          |
   | `ZOHO_ACCOUNT_ID`    | `your_account_id`         | From Step 3          |
   | `FROM_EMAIL`         | `no-reply@saimonsoft.com` | Sender email address |

2. **Remove Old SMTP Variables (Optional)**
   - You can remove these if no longer needed:
     - `SMTP_SERVER`
     - `SMTP_PORT`
     - `SMTP_USERNAME`
     - `SMTP_PASSWORD`
     - `SMTP_USE_TLS`
     - `SMTP_USE_SSL`

---

## Step 5: Verify Domain Configuration

1. **Check Domain in Zoho Mail**

   - Ensure `saimonsoft.com` is verified in your Zoho Mail account
   - Verify SPF, DKIM, and DMARC records are properly configured
   - This ensures emails are delivered and not marked as spam

2. **Verify Email Address**
   - Ensure `no-reply@saimonsoft.com` exists in your Zoho Mail account
   - Test that you can send emails from this address via the Zoho Mail web interface

---

## Step 6: Test Email Sending

### Local Testing

1. **Start your application**

   ```bash
   python -m uvicorn app.main:app --reload
   ```

2. **Test the email endpoint**

   ```bash
   curl -X POST "http://localhost:8000/api/email/send-code" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "your-test-email@example.com",
       "purpose": "forgot_password"
     }'
   ```

3. **Check logs**

   - Look for success messages in the application logs
   - Check for any error messages related to Zoho API

4. **Verify email received**
   - Check the recipient's inbox (and spam folder)
   - Email should be from `no-reply@saimonsoft.com`

### Production Testing

1. **Deploy to Render**

   - Push your changes to trigger a deployment
   - Wait for deployment to complete

2. **Test via API**

   - Use your production API endpoint to send a test email
   - Monitor Render logs for any errors

3. **Verify email received**
   - Check the recipient's inbox
   - Verify the email appears to come from `no-reply@saimonsoft.com`

---

## Step 7: Monitor and Troubleshoot

### Common Issues

1. **"Zoho Mail API not configured" error**

   - Check that all environment variables are set correctly
   - Verify variable names match exactly (case-sensitive)
   - Ensure `FROM_EMAIL` is set to `no-reply@saimonsoft.com`

2. **"Failed to obtain Zoho access token" error**

   - Verify `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, and `ZOHO_REFRESH_TOKEN` are correct
   - Check that the refresh token hasn't been revoked
   - Verify the OAuth scopes include `ZohoMail.messages.CREATE` and `ZohoMail.accounts.READ`
   - Try regenerating the refresh token if it's not working

3. **"Zoho Mail API error: 401" error**

   - Access token may have expired (should auto-refresh automatically)
   - Check that the refresh token is still valid
   - Verify account ID is correct
   - Check that OAuth scopes are properly configured

4. **"Zoho Mail API error: 403" error**

   - Check that the account has permission to send emails
   - Verify the `FROM_EMAIL` address exists and is authorized
   - Ensure the OAuth application has the correct scopes
   - Check if there are any IP restrictions on the Zoho account

5. **"Zoho Mail API error: 404" error**

   - The API endpoint might be incorrect
   - Verify the `ZOHO_ACCOUNT_ID` is correct
   - Check Zoho Mail API documentation for the correct endpoint format
   - The endpoint might need to be `/api/accounts/{accountId}/messages/send` instead

6. **"Zoho Mail API error: 400" error**

   - Check the email payload format matches Zoho's requirements
   - Verify `fromAddress` and `toAddress` are valid email addresses
   - Check that required fields are present in the payload

7. **Emails not received**
   - Check spam/junk folder
   - Verify domain SPF/DKIM records are properly configured
   - Check Zoho Mail logs/dashboard for delivery status
   - Verify the recipient email address is valid

### Logging

- Application logs will show:
  - Token refresh attempts
  - Email send attempts
  - API errors with status codes
  - Success confirmations

---

## Step 8: Cleanup (Optional)

Once everything is working:

1. **Remove SMTP2Go credentials** (if no longer needed)
2. **Update documentation** to reflect Zoho Mail usage
3. **Archive old SMTP configuration** in version control

---

## Quick Reference: Required Environment Variables

```env
# Required for Zoho Mail API
ZOHO_CLIENT_ID=                    # From Zoho Developer Console
ZOHO_CLIENT_SECRET=                # From Zoho Developer Console
ZOHO_REFRESH_TOKEN=               # Generated via OAuth flow
ZOHO_ACCOUNT_ID=                   # Your Zoho Mail account ID
FROM_EMAIL=no-reply@saimonsoft.com # Sender email address
```

---

## Support Resources

- **Zoho Mail API Documentation**: https://www.zoho.com/mail/help/api/
- **Zoho OAuth Documentation**: https://www.zoho.com/accounts/protocol/oauth/
- **Zoho Developer Console**: https://accounts.zoho.com/developerconsole

---

## Checklist Summary

- [ ] Created Zoho API application in Developer Console
- [ ] Saved Client ID and Client Secret
- [ ] Generated and saved Refresh Token
- [ ] Obtained Account ID (ZUID)
- [ ] Added all environment variables to local `.env`
- [ ] Added all environment variables to Render
- [ ] Verified `saimonsoft.com` domain in Zoho Mail
- [ ] Verified `no-reply@saimonsoft.com` email exists
- [ ] Tested email sending locally
- [ ] Tested email sending in production
- [ ] Verified emails are received (not in spam)
- [ ] Monitored logs for any errors
- [ ] Removed old SMTP2Go credentials (optional)

---

**Last Updated**: [Current Date]
**Status**: Ready for implementation
