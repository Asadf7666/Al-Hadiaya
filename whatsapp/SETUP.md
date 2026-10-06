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


## Photo campaigns and shop catalogue in 0.6

Update the hosted app and Windows installations with the 0.6 installer. Protocol 3 remains compatible with 0.5 nodes. In WhatsApp updates, refresh Meta templates, upload the campaign image, choose a supported marketing template and save a draft. Review the image and exact wording before approval. Pending templates can be drafted but cannot send. IMAGE-header templates accept an image; body templates accept zero or three text variables. Fixed-body templates do not use the offer field in their message.

The corrected provider names are `al_hadiya_invoice`, `al_hadiya_payment`, `al_hadiya_internal`, `al_hadiya_offer`, and `al_hadiya_offer_image`. All five returned PENDING on submission. Use the supplied text definitions for the four body templates. For the image template, choose IMAGE as header in Meta and upload the Al Hadiya campaign artwork as its review sample; body: `Hello {{1}}, welcome to {{2}}.\n{{3}}\nReply STOP to stop promotional messages.` Example values: Customer, Al Hadiya Traders, Fresh drinks at our takeaway counter.

Use Photo catalogue & order requests to select a product, upload a photo, write its description and publish it after confirming its retail price. Enable the public catalogue in Catalogue settings. Customers browse `/catalogue`; staff review requests and prepare a POS bill before taking payment. This independent web catalogue works without a Meta Commerce catalogue; native WhatsApp product messages still require Commerce setup. Media/publication/order-request data remain local to the installation. Folder backups include the `.media` sidecar; retain it with the database.


## Native in-WhatsApp ordering in 0.7

1. In Commerce Manager (`https://business.facebook.com/commerce/`), create/select an owned trading catalogue. Add real product photos/prices or import the feed CSV exported from the hosted app. After linking and enabling, configure Commerce Manager to fetch `https://<your-app-host>/commerce-feed.csv` hourly; it supplies current prices and Warehouse availability automatically.
2. In WhatsApp Manager → Catalogue, connect that catalogue to your business WhatsApp account. In the app’s WhatsApp orders → Connect Meta catalogue, save its ID, click Check connection & enable Meta cart, then enable native catalogue automation. The check will reject an unlinked catalogue. A messaging-only token cannot create/manage owned Commerce catalogues; use Meta UI or properly scoped business_management/catalog_management credentials, entered securely.
3. In WhatsApp updates → Configure delivery webhook, enter your Meta app secret and chosen verification token directly in the protected fields. In Meta app WhatsApp configuration, verify the callback and subscribe messages. Enter no secret in chat or source.
4. Add internal recipients with their agreement, choose transaction alert switches, and enable sender notifications. Ask each staff recipient to message the business number first if testing direct internal alerts. After the 24-hour window, approved templates are required. `al_hadiya_order_update` uses business name, order number and current status/details as its three body parameters.
5. Map each native retailer ID to stock, pack size and price tier. Send MENU from the customer number, open the native catalogue, add items and send a cart. Review the new order in the app, confirm, pack, invoice and complete. Verify customer/staff replies and delivery receipts.
6. Upgrade all Windows installations to 0.7 before sync; protocol 4 includes shared orders. The test sender works only with verified test recipients and does not prove that an owned Commerce catalogue can be connected to it. Production onboarding may require your real business number; confirm that path in Meta.

Native browsing/ordering cannot be demonstrated until Meta catalogue linkage and signed inbound webhook setup are complete. The web catalogue remains available while those prerequisites are completed.


## v1 account review and policy controls

Keep automated sending disabled while the current Meta review is pending. Rotate the App Secret and tokens exposed in chat and enter replacements directly in the app. App credentials do not override account restrictions. The sender validates account review/number quality and approved template purpose/freshness before sending. Record new customer consent evidence, respect opt-outs and publish only reviewed genuine catalogue products. Read [policy mapping](../docs/WHATSAPP-POLICY.md) and [handover](../docs/HANDOVER.md). Production activation still needs account restoration, approved branded templates, signed messages webhook, owned Commerce catalogue linkage and one bounded genuine cart/delivery/STOP test.
