# Password Policy (Frontend + Backend)

This backend supports an environment flag to enforce strong passwords:

- `ENFORCE_STRONG_PASSWORDS`
  - `false` (default): backend accepts current behavior (no strength checks).
  - `true`: backend enforces strong password rules.

## Strong password rules (when enabled)

Passwords must include all of the following:

1. At least 8 characters
2. At least 1 uppercase letter
3. At least 1 lowercase letter
4. At least 1 number
5. At least 1 special character (non-alphanumeric)

## Affected API flows

When `ENFORCE_STRONG_PASSWORDS=true`, these endpoints enforce the rules:

- `POST /api/users/register`
- `POST /api/email/reset-password`
- `POST /api/email/change-password`
- `POST /api/sms/reset-password`
- `POST /api/sms/change-password`
- `POST /api/email/send-code` (only for `purpose=finish_registration`, validating `registration_data.password`)

## Error behavior for frontend

On violation, backend returns:

- HTTP `400`
- `detail` string with a specific message, for example:
  - `Password must be at least 8 characters long.`
  - `Password must include at least one uppercase letter.`
  - `Password must include at least one lowercase letter.`
  - `Password must include at least one number.`
  - `Password must include at least one special character.`

Frontend should surface `detail` directly to users and ideally pre-validate with the same rules.

## Existing users migration (frontend implementation)

When `ENFORCE_STRONG_PASSWORDS=true`, existing users with weak legacy passwords can still log in unless frontend forces an upgrade flow.

Use this frontend rollout:

1. Detect policy enabled (from your frontend env/config for this deployment).
2. After successful login, check a client marker:
   - key: `strongPasswordCompliant:<userId>`
   - value: `true` only after successful password change/reset
3. If marker is missing and policy is enabled:
   - block normal app navigation
   - show **"Password update required"** screen
   - send user through change-password/reset flow
4. On successful password update response, set marker to `true` and continue to app.

### Required frontend behavior

- Pre-validate new password with the same backend rules before submit.
- Keep backend error handling (`400` + `detail`) as source of truth.
- Do not allow skipping this screen while policy is enabled.

### Recommended API flow for forced update

- `POST /api/email/send-code` with `purpose=change_password`
- `POST /api/email/change-password` with `user_id`, `code`, `new_password`

(Use SMS variants if your UX is SMS-based.)

### Important limitation

This frontend marker is device/browser-local. A user on a different device may still need to upgrade again.  
For strict global enforcement, add a backend field like `requiresPasswordUpgrade` (or `passwordPolicyVersion`) and return it in login/user payloads.

