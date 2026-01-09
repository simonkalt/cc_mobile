# Stripe Connection Diagnostic Guide

## Problem: "No subscription plans available at this time. Please try again later."

This error message appears when the `/api/subscriptions/plans` endpoint returns an empty plans array. This can happen for several reasons:

1. **Stripe library not installed** - The `stripe` Python package is missing
2. **Network connectivity issues** - Render cannot reach Stripe's API servers
3. **Authentication failure** - Invalid or missing Stripe API key
4. **No active products** - Stripe account has no active products with recurring prices
5. **Exception being caught** - An error occurs but is silently caught and returns empty array

## Diagnostic Steps

### Step 1: Check Stripe Connectivity Endpoint

Call the comprehensive diagnostic endpoint:

```bash
# On Render, replace with your Render URL
curl https://your-app.onrender.com/api/subscriptions/test-connectivity
```

Or visit in browser:
```
https://your-app.onrender.com/api/subscriptions/test-connectivity
```

This endpoint will test:
- ✅ Stripe library availability
- ✅ Environment variables (API keys, webhook secrets, etc.)
- ✅ Actual Stripe API connection
- ✅ Account retrieval
- ✅ Product listing
- ✅ Price ID validation

### Step 2: Check Stripe Debug Endpoint

```bash
curl https://your-app.onrender.com/api/subscriptions/debug/stripe
```

This shows:
- Python environment details
- Stripe module location and version
- API key configuration status

### Step 3: Check Application Logs on Render

Look for these log messages in Render's logs:

**Good signs:**
- `✅ Successfully fetched X plans from Stripe`
- `Stripe API key configured (test/production mode)`
- `Found X active products in Stripe`

**Bad signs:**
- `⚠️ Stripe fetch succeeded but returned 0 plans`
- `❌ Error fetching plans from Stripe: ...`
- `⚠️ This appears to be a network/connection error`
- `⚠️ This appears to be an authentication error`
- `Stripe library not available`

### Step 4: Verify Environment Variables on Render

In Render Dashboard → Your Service → Environment:

**Required:**
- `STRIPE_TEST_API_KEY` OR `STRIPE_API_KEY` (at least one must be set)

**Optional but recommended:**
- `STRIPE_PRICE_ID_MONTHLY` (fallback, currently disabled)
- `STRIPE_PRICE_ID_ANNUAL` (fallback, currently disabled)
- `STRIPE_PRODUCT_CAMPAIGN` (if filtering products by metadata)
- `STRIPE_WEBHOOK_SECRET` (for webhook handling)

**Check:**
1. Variable names are **exactly** as shown (case-sensitive)
2. No extra spaces or quotes around values
3. API keys start with `sk_test_` (test) or `sk_live_` (production)

### Step 5: Test Plans Endpoint Directly

```bash
# Test with cache
curl https://your-app.onrender.com/api/subscriptions/plans

# Force refresh (bypass cache)
curl https://your-app.onrender.com/api/subscriptions/plans?force_refresh=true
```

Expected response:
```json
{
  "plans": [
    {
      "id": "...",
      "name": "...",
      "priceId": "...",
      ...
    }
  ]
}
```

If you get `{"plans": []}`, check the logs for errors.

## Common Issues and Solutions

### Issue 1: Stripe Library Not Installed

**Symptoms:**
- Logs show: `Stripe library not available`
- Diagnostic endpoint shows: `"stripe_library": {"available": false}`

**Solution:**
Add `stripe>=7.0.0` to your `requirements.txt` and redeploy.

### Issue 2: Network/Connection Error

**Symptoms:**
- Logs show: `⚠️ This appears to be a network/connection error`
- Error type: `APIConnectionError` or `Timeout`

**Possible causes:**
- Render's network cannot reach Stripe API
- Firewall blocking outbound connections
- Stripe API temporarily unavailable

**Solution:**
1. Check Render's network status
2. Verify Stripe API status: https://status.stripe.com
3. Try again after a few minutes
4. Contact Render support if persistent

### Issue 3: Authentication Error

**Symptoms:**
- Logs show: `⚠️ This appears to be an authentication error`
- Error type: `AuthenticationError`
- Diagnostic endpoint shows: `"status": "authentication_failed"`

**Possible causes:**
- API key is incorrect or expired
- API key has wrong prefix (test vs live)
- API key doesn't have required permissions

**Solution:**
1. Verify API key in Stripe Dashboard → Developers → API keys
2. Ensure key matches environment (test key for test mode, live for production)
3. Regenerate key if needed
4. Check that key has "Read" permissions for Products and Prices

### Issue 4: No Active Products

**Symptoms:**
- Logs show: `No active products found in Stripe`
- Diagnostic endpoint shows products count as 0

**Solution:**
1. Go to Stripe Dashboard → Products
2. Ensure at least one product is marked as "Active"
3. Ensure product has at least one "Active" recurring price
4. Check product metadata if `STRIPE_PRODUCT_CAMPAIGN` is set

### Issue 5: Products Filtered Out

**Symptoms:**
- Logs show: `Campaign filter active: '...'`
- Products exist but none match filter

**Solution:**
1. Check `STRIPE_PRODUCT_CAMPAIGN` environment variable
2. Ensure products have matching metadata in Stripe Dashboard
3. Remove or adjust the campaign filter if not needed

## Enhanced Error Logging

The code now includes enhanced error logging that will help identify issues:

- **Network errors** are specifically identified
- **Authentication errors** are specifically identified
- **Stripe error codes** are logged
- **API key configuration** is logged
- **Product fetch attempts** are logged

Check Render logs for these detailed messages when troubleshooting.

## Quick Diagnostic Checklist

- [ ] Stripe library installed (`stripe>=7.0.0` in requirements.txt)
- [ ] `STRIPE_TEST_API_KEY` or `STRIPE_API_KEY` set in Render environment
- [ ] API key is correct and active in Stripe Dashboard
- [ ] API key matches environment (test vs production)
- [ ] At least one product is active in Stripe Dashboard
- [ ] Active product has at least one active recurring price
- [ ] No campaign filter excluding all products (if `STRIPE_PRODUCT_CAMPAIGN` is set)
- [ ] Render can reach Stripe API (check network/firewall)
- [ ] Check diagnostic endpoint: `/api/subscriptions/test-connectivity`
- [ ] Check application logs for detailed error messages

## Next Steps

1. **Run the diagnostic endpoint** on Render to get detailed information
2. **Check Render logs** for the enhanced error messages
3. **Verify environment variables** in Render Dashboard
4. **Test Stripe connection** from Render's environment
5. **Contact support** if issue persists with diagnostic information

## Related Endpoints

- `GET /api/subscriptions/test-connectivity` - Comprehensive Stripe connectivity test
- `GET /api/subscriptions/debug/stripe` - Stripe configuration debug info
- `GET /api/subscriptions/plans` - Get subscription plans (the endpoint that's failing)
- `GET /api/health/stripe` - Basic Stripe health check

