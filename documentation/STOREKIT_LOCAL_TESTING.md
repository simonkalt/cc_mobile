# Local StoreKit testing (Xcode)

This repo’s iOS billing UI requests these **subscription product IDs** (see `APPLE_SUBSCRIPTION_PRODUCT_IDS` in [`src/utils/constants.js`](../src/utils/constants.js)):

| `productID`   | Renewal (ISO 8601) |
|---------------|-------------------|
| `MONTHLY001`  | `P1M`             |
| `SIXMONTH001` | `P6M`             |
| `ANNUAL001`   | `P1Y` ($149)      |

A matching Xcode configuration file lives here: **[`LocalStoreKitConfiguration.storekit`](./LocalStoreKitConfiguration.storekit)** (`ANNUAL001` uses **`149.00`** display price for local testing).

---

## Wire the file into Xcode

1. Generate or open the **native iOS project** (Expo: `npx expo prebuild --platform ios`, or open the existing `ios/` workspace from EAS local builds).
2. **File → Add Files to “&lt;App&gt;”…** and add `documentation/LocalStoreKitConfiguration.storekit` (copy into `ios/` first if you prefer keeping it next to the Xcode project).
3. Select the **scheme** for your app → **Edit Scheme…** → **Run** → **Options**.
4. Under **StoreKit Configuration**, choose **LocalStoreKitConfiguration.storekit**.
5. Run the app from **Xcode** on the Simulator or a device.

Purchases use **local StoreKit data**; you should **not** see the full sandbox “Sign in to Apple Account” sheet for these products when the configuration is active (Apple’s local testing path).

---

## Keep IDs in sync

- If you change products in **App Store Connect**, update **both** `LocalStoreKitConfiguration.storekit` and `EXPO_PUBLIC_APPLE_SUBSCRIPTION_IDS` (if you override defaults) so `productID` values match exactly.
- **Display prices** in the `.storekit` file are **for testing only** (what the Simulator / local sheet shows). Production prices come from Apple; align `displayPrice` with your real tiers when possible to avoid confusion.

---

## Backend verification note

The app posts the signed transaction to **`POST /api/subscriptions/apple/verify`**. JWS from **Xcode StoreKit testing** is not the same as production App Store receipts. Your server must validate using **Apple’s sandbox / StoreKit test environment** (App Store Server API with the appropriate environment), or local purchase verification will fail even when the Simulator purchase succeeds.

Apple documents that [verifying legacy receipts](https://developer.apple.com/documentation/appstorereceipts/verifyreceipt) against the test environment is limited; prefer **transaction JWS** validation paths your backend already uses for sandbox.

---

## Useful Xcode menus while testing

- **Editor → Subscription Renewal Rate** — speed up renewals (e.g. every 30 seconds) to test expiry and upgrades.
- **Debug → StoreKit → Manage Transactions** — delete or resolve test transactions to reset state.

---

## Related in-app copy

Simulator limitations when **not** using a StoreKit configuration file are summarized in [`IosBillingPlanPicker.ios.js`](../src/components/billing/IosBillingPlanPicker.ios.js) (orange hint when `!Constants.isDevice`).
