# WhatsApp rollout — version 0.5.0

## Verified so far

Meta app: **Al Hadiya Trading**, ID `1415233420794737`.
WhatsApp Business Account ID: `1393794192441777`.
Test Phone Number ID: `1381844731677244`.
Graph API version used successfully: `v26.0`.
One authorized `hello_world` test to the owner's verified recipient was accepted by Meta and the owner confirmed delivery. The token was saved in the hosted app's credential file; it is not stored in source or included in this document.

Four templates were submitted to Meta on 6 October 2026 and returned PENDING:

| Template | Category | Body parameters | Meta template ID |
|---|---|---|---|
| al_hidaya_invoice | UTILITY | customer, invoice number, amount | 1729695168106564 |
| al_hidaya_payment | UTILITY | customer, amount, payment note | 1438739818210278 |
| al_hidaya_internal | UTILITY | business, update type, summary | 2611658522613679 |
| al_hidaya_offer | MARKETING | customer, business, offer | 1322560409837976 |

Submission is not approval. Review the final status/category in WhatsApp Manager. Meta can reject or recategorize a template. The template definitions and examples are in `templates.json`.

## Install and deploy first

Update the hosted app and every Windows node to 0.5.0 before sync. Protocol 3 protects the new shared marketing-consent fields from older clients. Upgrades preserve existing business data and pairing. Offline billing remains available while an older node waits to update, but it cannot sync with the new hub.

The existing review VM has no scheduled expiry. Deployment preserved its database, credentials and pairing. Version 0.5.0 was deployed successfully on 6 October 2026 after a pre-upgrade SQLite backup. The hosted UI, public policy pages, installer/source downloads and their checksums were verified. The current review address is https://alhidaya.3.110.148.105.sslip.io/app.

## Sender settings

Open **WhatsApp updates → Configure sender**. Use the test IDs above while testing; set language `en_US`, timezone `Asia/Kolkata`, and the invoice/payment/internal template names from the table. Enter the Business Account ID. A blank token preserves the saved token. Configure staff recipients with their permission; only verified Meta recipients work with the test sender.

Enable automation only after the relevant templates are APPROVED and recipients are ready. Keep the hosted sender active for shared alerts and webhook tracking. Leave automatic sending disabled on other nodes; this is a sender configuration choice, not a restriction on business functions. Offline-PC transactions generate alerts on the hub once synced. Choose daily summary time and the alert switches you want.

## Delivery webhook

Open **Configure delivery webhook** and enter:

- Meta app secret from the app's Basic Settings, directly into its password field.
- A random verification token of at least 16 characters; keep it private.

In Meta's WhatsApp configuration, enter the hosted HTTPS address followed by `/webhooks/whatsapp` and the same verification token. Verify the callback, then subscribe the **messages** field. The callback must be public and reachable. Public policy URLs use `/privacy` and `/data-deletion`; review their text and provide accurate shop contact information before production.

Signature validation rejects forged events. STOP replies disable both receipt and marketing consent, cancel pending messages for the number and produce a sync event. Already-sending messages cannot be recalled. Delivery records arriving before the send response are retained and reconciled when the provider message ID is saved.

## First campaign

Refresh templates from Meta. Record separate promotional consent in each customer profile; consent to receipts is insufficient. Create a campaign, choose retail/wholesale/all opted-in customers and enter the offer. Review the actual template body and audience, then approve. Scheduling is optional, but still requires approval. Monitor the queue and delivery status. Do not upload a bought contact list or treat every existing customer as opted in.

## Production

Register the intended business WhatsApp number using a Meta-supported onboarding process. If keeping the existing mobile app number, check whether Meta offers coexistence for that account/provider; do not remove it from the mobile app without confirming the onboarding path. Complete business/account prerequisites, payment settings and permissions required by Meta. Replace the test Phone Number ID and token with production credentials. A temporary dashboard token is unsuitable for unattended operation; use an appropriately scoped system-user credential where Meta makes it available, and rotate/revoke the token previously shared in chat.

The standard Cloud API integration does not create or post to WhatsApp Channels or mobile-app broadcast lists. Campaigns send individual approved template messages; recipients do not see one another. General group messaging is not part of this release.

## Expanded live test findings

All 12 application-generated invoice/payment/internal-update cases were attempted against the owner-authorized verified recipient. Meta rejected the custom templates with error 132001 while their status was PENDING. This is not a successful custom-template delivery test. The customer-campaign approval guard also rejected the unapproved marketing template before sending. Financial records and stock used for these tests were kept in a temporary shop database; the hosted shop received only clearly marked test notification logs.

The test WABA reports account_review_status APPROVED but business_verification_status pending_submission. Marketing-message onboarding reports NOT_STARTED. No product catalogue is linked. Listing the business's owned catalogues returned error 200 requiring business_management permission; the temporary messaging token does not have that catalogue-management access.

Catalogue setup requires suitable business_management/catalog_management authorization, an owned Commerce catalogue, accurate product prices/photos and a link to WhatsApp. The app's starter inventory does not automatically become a Meta Commerce catalogue. Standard Cloud API integration does not create WhatsApp Channels or app broadcast lists.

See `LIVE-TEST-RESULTS.md` for the 16 accepted approved-sample tests, actual errors and remaining live checks.
