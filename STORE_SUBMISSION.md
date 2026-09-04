# TonYoga — App Store & Play Store Submission Checklist

Replace `https://YOUR-DOMAIN` with your live production domain (your Hostinger VPS URL,
e.g. `https://www.tonyoga.com`). All pages below are public and work without login.

## Required public URLs (paste these into the store consoles)
| Purpose | URL |
|---|---|
| Privacy Policy | `https://YOUR-DOMAIN/privacy` |
| Terms of Service | `https://YOUR-DOMAIN/terms` |
| Account & Data Deletion | `https://YOUR-DOMAIN/account-deletion` |
| Support / Contact | `https://YOUR-DOMAIN/support` |

## Google Play
1. **App content → Privacy policy**: paste the `/privacy` URL.
2. **App content → Data deletion**:
   - "Users can request that some or all of their data is deleted" → **In-app + Web**.
   - Web deletion URL: `https://YOUR-DOMAIN/account-deletion`.
3. **Data safety form**: declare what you collect (email, name, purchase history, app activity),
   that it's encrypted in transit, and that users can request deletion. (See Privacy Policy §1 for the list.)
4. **Account deletion is in-app**: Profile → Delete account (password-confirmed, 30-day grace).

## Apple App Store
1. **App Privacy** (App Store Connect → your app → App Privacy): declare data types
   (Contact Info: name/email; Purchases; Usage Data; User Content for AI assistant messages).
2. **Account deletion (Guideline 5.1.1(v))**: the app offers in-app deletion at
   Profile → Delete account. Point the reviewer there in the review notes.
3. **Support URL**: `https://YOUR-DOMAIN/support`. **Privacy Policy URL**: `https://YOUR-DOMAIN/privacy`.
4. **Review notes**: mention the 30-day grace period (account is deactivated immediately and
   permanently deleted after 30 days; user can cancel by signing back in).

## How account deletion works (for your reference)
- **In-app**: Profile → "Delete my account" → confirm with password → account deactivated now,
  `deletion_scheduled_at = now + 30 days`. Banner shows the date + a "Cancel deletion" button.
- **Grace period**: user can still sign in during the 30 days and cancel to restore everything.
- **Public (can't sign in)**: `/account-deletion` form emails the request; team processes within 30 days.
- **Purge**: a background job permanently deletes the user + personal data after 30 days;
  financial records (orders/payments) are anonymised and retained for tax/legal reasons only.

## Mobile packaging
- **PWA** (fastest): the site is installable ("Add to Home Screen") — no build needed.
- **Native build**: use the existing `frontend/capacitor.config.json` + `/app/MOBILE_BUILD.md`.
  Before building, ensure `frontend/.env` `REACT_APP_BACKEND_URL` points to your **live HTTPS VPS URL**.

## Store listing assets you'll still need to create
- App icon (1024×1024), feature graphic (Play), screenshots per device size, short + full description.
