# ENV Upgrade Checklist

- Baseline: `HEAD` compared to `origin/MS-Word-Integration`
- Keys still missing from code-parity scan: `0`
- `Present in .env` checks key names only (not values).

## Missing Keys

| Key | Feature/Vendor | Priority | Present in `.env` | Used In |
|---|---|---|---|---|

## Recommended Next Step

- Add any `No` keys you plan to use into `.env` (with real values) or set safe defaults for feature flags.
- If you do not plan to use a feature (LinkedIn/Telnyx/Redis/Zoho), leave the keys unset.
