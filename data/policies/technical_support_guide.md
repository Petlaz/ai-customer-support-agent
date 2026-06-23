# Technical Support Guide

**Nexus Software — Internal Support Reference**

---

## 1. Login & Authentication Issues

### Cannot Log In
- Verify the customer is using the correct email address associated with their account.
- Ask if they are using SSO — if so, they must log in via their identity provider (Okta, Azure AD, etc.), not the standard login form.
- If account is locked (5 failed attempts), wait 15 minutes or use the password reset flow.
- Check if the account is suspended due to failed payment — verify billing status.

### Password Reset Not Working
- Confirm the reset email is being sent to the correct address.
- Ask customer to check their spam/junk folder.
- Reset links expire after 1 hour — if expired, generate a new one.
- If the customer has a corporate email with strict filtering, the reset email may be blocked — suggest whitelisting support@nexussoftware.com.
- As a last resort, support agents can trigger a manual reset from the admin console.

### Two-Factor Authentication (2FA) Issues
- If the customer loses access to their 2FA device, they can use a backup code (provided during 2FA setup).
- If backup codes are also unavailable, identity verification is required before bypassing 2FA. Collect: account email, billing last 4 digits, date of account creation.
- Do not bypass 2FA without completing identity verification.

---

## 2. Performance & Stability Issues

### App Slow or Unresponsive
1. Ask customer to check status.nexussoftware.com for any ongoing incidents.
2. Ask them to clear browser cache (Ctrl+Shift+Delete / Cmd+Shift+Delete) and reload.
3. Test in an incognito/private window to rule out browser extension interference.
4. Try a different browser (Chrome, Firefox, Safari, Edge — all supported).
5. Check internet connection speed — app requires a minimum of 5 Mbps.
6. If the issue is isolated to a specific feature, collect the URL and steps to reproduce.

### App Crashes or Freezes
- Ask for: browser + version, OS, any error messages or console errors (F12 → Console tab).
- Check if the issue occurs on multiple devices.
- For desktop app crashes: ask for the crash log from **Help → Send Diagnostics**.
- Escalate to engineering if the crash is reproducible and not related to a known issue.

### File Upload Failures
- Maximum file size: 100 MB per file.
- Supported formats: PDF, DOCX, XLSX, CSV, PNG, JPG.
- Ask customer to verify file size and format.
- Large files may time out on slow connections — suggest a wired connection for uploads over 50 MB.
- If the file is within limits and the error persists, collect the exact error message and escalate.

---

## 3. API Integration Issues

### 401 Unauthorized
- Customer's API key may be invalid, revoked, or copied incorrectly.
- Direct them to **Settings → API → API Keys** to verify or generate a new key.
- Confirm the key is being sent in the correct header: `Authorization: Bearer <api_key>`.

### 429 Rate Limit Exceeded
- Rate limits: 1,000 requests/minute (Pro), 5,000/minute (Business/Enterprise).
- Suggest implementing exponential backoff in their integration code.
- If legitimate use requires higher limits, they should upgrade their plan or contact sales for Enterprise.

### 400 / 422 Validation Errors
- Refer customer to the API documentation at docs.nexussoftware.com/api.
- Ask them to share the full request payload (with sensitive data redacted) and the full error response.
- Common issues: missing required fields, wrong data types, invalid enum values.

### Webhooks Not Firing
- Check that the webhook URL is publicly accessible (not localhost).
- Verify the endpoint returns a 200 status within 5 seconds — timeouts are treated as failures.
- Check the webhook event log in **Settings → Integrations → Webhooks → Event Log**.
- Nexus Software retries failed webhooks up to 3 times with exponential backoff.

---

## 4. Mobile App Issues

### App Not Loading on Mobile
- Minimum requirements: iOS 15+ or Android 10+.
- Ask customer to force-close the app and reopen.
- Check for pending app updates in the App Store / Google Play.
- Uninstall and reinstall as a last resort (data is not lost — all data is stored in the cloud).

### Push Notifications Not Working
- Ensure notifications are enabled in device settings for the Nexus app.
- Check in-app notification settings under **Profile → Notifications**.
- For iOS: ensure Background App Refresh is enabled.

---

## 5. Data & Integrations

### Data Export Issues
- Exports are processed in the background for large datasets.
- Estimated time: up to 15 minutes for exports over 10,000 records.
- The download link is emailed to the account email when ready.
- If the email is not received within 30 minutes, customer can trigger a new export — previous exports are discarded.

### Salesforce Integration Issues
- Available on Business and Enterprise plans only.
- Re-authenticate the Salesforce connection from **Settings → Integrations → Salesforce → Reconnect**.
- Common issue: Salesforce Connected App permissions have been modified — customer's Salesforce admin needs to re-authorize.
- For sync errors, check the integration error log in **Settings → Integrations → Salesforce → Sync Log**.

### SSO Configuration Issues
- SSO is available on Business and Enterprise plans.
- Supported identity providers: Okta, Azure AD, Google Workspace, OneLogin.
- Common issues: incorrect ACS URL, missing attribute mappings, certificate expired.
- Direct customer to the SSO Setup Guide in the Help Center or escalate to the technical onboarding team for Enterprise customers.
