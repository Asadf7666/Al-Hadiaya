# Verification history

## Version 1.0.0 review build — 6 October 2026

107 automated Python checks passed in the Linux workspace, including local staff authentication and permissions, request replay after a lost response, verified portable backups and guarded restoration, backup retention, consent evidence, catalogue publication reviews, account/quality pauses, template categories and outbound pacing. Provider calls use fixtures; no live WhatsApp messages were sent during this v1 work.

Chromium passed first-owner setup and offline login, reloaded bill drafts and retry-safe checkout, staff permissions and mobile navigation, native-order confirmation to a linked POS invoice with case quantities, purchase-order approval and partial goods receipt, and café POS. The café check sold two coffees at the Outlet, produced a walk-in UPI bill and deducted the exact recipe ingredients. No JavaScript exceptions occurred in these checks.

The NSIS installer compiles with the pinned embedded Python runtime. The Windows release workflow runs the test suite and an actual isolated install → first-owner setup → sale → update → login/data preservation → uninstall/data preservation check before publishing. Its result must be checked for the particular release; Linux compilation alone does not establish Windows execution.

Physical printer/scanner checks, code signing, a full shop shift, accountant review of tax treatment, real folder-provider transport, production Meta account/templates/catalogue/webhooks and hardware crash/power-loss validation remain deployment gates. The Windows installer is unsigned. WhatsApp is paused while the account review is pending; see docs/WHATSAPP-POLICY.md. Prior review-host expiry instructions below are historical and have been cancelled; stopping the retained host is distinct from deleting it.

Executed in the Linux build workspace on 5 October 2026.

## Passed

- 33 Python standard-library unittest checks: paise rounding/non-finite input, inclusive GST and cess, CGST/SGST and IGST allocation, tiny-amount rounding, financial-year invoice length, saved snapshot stability, unregistered billing, invoice discount allocation, atomic rollback on overselling, walk-in credit rejection, customer dues and payments, purchase average recorded cost, stock transfer conservation, recipe consumption/reversal, reversal restrictions after payment, SQLite backup integrity/restore, two-independent-database offline exchange and duplicate-import idempotency, location boundaries, unique barcodes, atomic CSV import, MRP limits and wholesale billing, safe zero-stock catalogue templates, warehouse auto-catalogue setup, direct warehouse customer billing, preservation of fields on partial CSV updates, and visible rollback of a conflicting sync transaction.
- JavaScript syntax check with `node --check static/app.js` and Python bytecode compilation.
- Chromium/Playwright smoke test with non-local browser requests blocked: opened all primary modules; edited and saved a barcode; scanned the code into the POS; completed a saved sale; checked the invoice preview and CSV-import form; rendered the dashboard at 1440 px and POS at 1024 px. No JavaScript exceptions were reported.
- Windows installer compiled using NSIS 3.11 without warnings. The builder verifies the embedded Python runtime against its pinned SHA-256 and writes a SHA-256 checksum for the resulting installer.

## Not verified here

Actual execution on Windows 10/11, installer/update/uninstall execution under Windows, Windows security prompts/code signing, printer margins and thermal-paper output, real barcode-scanner devices, bank/payment APIs, cloud-folder transport between real addresses, large-scale data performance, crash/power-loss recovery and a complete live shop shift.

The sync test uses two independent database directories exchanging immutable files through a shared local test folder. That verifies application merge/idempotency logic, not OneDrive or another provider's network transport.

This release is unsigned and remains a pilot. Review README's explicit feature boundaries before live business use.

## Version 0.2 additions

Passed three disconnected counters selling reserved/unallocated stock without overselling; unused allowance release; profile edits preserving credit/history and credit-limit enforcement. Seven additional WhatsApp tests verify number normalisation, daily queue deduplication, internal sending, purchase/transfer alerts, customer/internal opt-out cancellation, missing-token offline retention, and uncertain-send suppression. Delivery calls are mocked: no real WhatsApp messages were sent. Browser testing opened the WhatsApp settings, added an opted-in internal recipient and rendered the queue without JavaScript errors. Actual Meta account/templates/network delivery and Windows DPAPI execution remain unverified.

## AWS Windows/Linux checks

37 automated tests passed on Windows Server 2022 with the pinned Python 3.14.8 embedded runtime and on the temporary Amazon Linux host. Windows DPAPI encryption/decryption roundtrip passed. Testing exposed and fixed delayed SQLite connection closure causing Windows file locks; restore and backup now close their handles. The web server also accepts bounded chunked bodies from an HTTPS reverse proxy. These are server OS checks; physical Windows 10/11 devices and installer execution remain unverified.

The HTTPS hosted browser review passed owner login, primary screens, a saved demo invoice, backup download, rejected requests without CSRF verification, blocked unauthenticated state access, and mobile account/location controls at 390px. No JavaScript errors were reported. The temporary Windows VM and upload bucket were deleted; a three-hour host shutdown with EC2 terminate-on-shutdown plus a follow-up cleanup automation was configured for the review VM.

0.3.0 adds real local HTTP tests with separate server/till databases: backup/sample replacement, private credential storage, offline save/reconnect, duplicate-upload retry after a lost response, two offline tills plus online stock exhaustion, customer relay, reversal, allowance release, disabled credentials, café ingredients and rejected catalogue forgery. These tests do not claim the new Windows installer has been executed on Windows.

Hosted 0.3.0 validation also passed against the actual AWS HTTPS origin: owner-generated code via the browser UI, Windows-app UI join using a local desktop HTTP server, verified sample backup, online stock grant, deliberately disconnected local sale, repeated reconnect without duplicate invoices, customer profiles in both directions, reversal and release of all test allowance. The test PC was disabled afterward. No JavaScript errors were reported. The hosted installer and source archive were downloaded and checked against their SHA-256 manifest. The desktop UI test ran on Linux; the 0.3.0 Windows installer itself was not executed on Windows.

## Version 0.4.0 — equal node capabilities

53 automated tests pass in the Linux workspace. New coverage verifies full business operations from an Outlet-labelled node: supplier creation, offline purchases, supplier payments, catalogue/recipe edits, transfers, wastage, business settings, customer credit and receipts. Independent nodes converge through real local HTTP transport. Any node can reverse another node's invoice; concurrent duplicate reversals are rejected atomically. Competing stock and payment events remain locally retained and visible for review, with later events held behind the conflict. Existing paired nodes can verify/change their HTTPS origin without replacing records. This supersedes the prior device-restriction/stock-quota tests. Prior Windows runtime/DPAPI results do not establish execution of the new 0.4.0 installer on Windows.

Actual hosted 0.4.0 browser validation passed against AWS HTTPS: a node labelled Outlet saved products, supplier purchase/payment, Warehouse-to-Outlet transfer, customer credit sale/receipt, recipe/café sale, expense and business settings while its sync transport was deliberately unavailable. Reconnection imported all events without duplicates. The online node reversed the peer's invoice, and a verified address change preserved identity/data. The test node was disabled and test stock zeroed afterward. No JavaScript errors occurred. The upgrade test also preserves an old paired identity, credential and unsent invoice containing legacy allocation metadata. The published installer and source downloads were verified against their SHA-256 manifest. The 0.4.0 installer has not been executed on Windows.

## Version 0.5.0 WhatsApp campaigns and webhooks

- 62 automated tests cover separate promotional consent, duplicate phone suppression, draft/approval behavior, one-time queuing, scheduled sends, cancellation, opt-out before send, owner-only online campaign access, consent sync, hub notification generation for an offline sale, signed delivery status ordering, STOP replay handling and public webhook challenge/signature routes.
- A headless Chromium browser check created a campaign draft, reviewed its message/audience, verified no message was queued before approval and queued exactly one after approval; no JavaScript errors. Fake credentials and a temporary database were used; no outreach was sent.
- Existing inventory, invoice, permission, sync and notification tests remain passing.
- NSIS compiled the 0.5.0 installer with the pinned Python 3.14.8 embedded runtime. The 0.5.0 installer has not been executed on Windows 10/11.
- Live Meta testing: one explicitly authorized hello_world message was accepted, and the owner confirmed receipt. Four template creation requests returned PENDING; no approval is assumed.
- Hosted deployment completed on 6 October 2026 after a database backup. The hosted WhatsApp UI, masked credential inputs, public policy pages, and full installer/source download checksums passed. Live signed delivery webhooks and STOP replies remain pending app-secret/verification-token configuration and Meta callback subscription.
- Twelve app-generated receipt/internal-alert cases were attempted live; custom-template sends were rejected with Meta error 132001 while the four business templates were PENDING. No successful delivery of those custom templates is claimed. Approved Meta sample-format results are recorded in whatsapp/LIVE-TEST-RESULTS.md.

- Expanded live provider tests: all 16 approved Meta sample messages returned message IDs (4 format checks and 12 TEST ONLY business-case parameter checks). Delivery/read is not inferred from API acceptance. The catalogue-message attempt returned error 131009; the owned-catalogue listing requires business_management permission. Media sample tests do not establish media campaign support in the app UI.


## Version 0.6 image campaigns and photo catalogue

Added checks for image validation, private/public image access, positive-price publication, server-side repricing, idempotent and concurrent order submissions, unchanged stock/customer/payment ledgers, image headers in provider payloads and media backup restoration. Native Meta Commerce remains permission blocked. Direct branded-image delivery and custom-template approval are reported separately from automated tests. Windows installer execution and physical hardware remain unverified.

Validation: 69 automated tests passed. Chromium exercised actual image upload and campaign-photo preview, a customer basket/order request, and a second basket after submission without JavaScript errors. The image-template test used fake credentials and sent no external outreach.

Hosted 0.6 deployment passed: database backup and migration, branded image upload via HTTPS, campaign form and image library, public banner and mobile catalogue rendering, installer/source SHA-256 checks. NSIS compiled the 0.6 installer with the pinned runtime; Windows execution remains unverified. Meta accepted the direct branded image, and the five correctly spelled business templates returned PENDING. See the live test report for distinctions between acceptance, delivery and template approval.


## Version 0.7 native WhatsApp carts and internal automation

Tests cover signed cart intake and duplicate suppression, case conversions, unchanged ledgers on intake, unknown items/currency/price guards, explicit revised-price confirmation, live stock recheck, native catalogue reply payloads, number-private status replies, STOP, internal service-window delivery and blocked pending templates, shared orders billed from a peer, atomic invoice linkage and concurrent offline duplicate-invoice conflict rollback, protocol-3 rejection, real-link checks and Meta feed price/photo/availability. Chromium completed staff confirmation → linked POS invoice with stock checks, and checked catalogue configuration and sender diagnostics without JavaScript errors. Fake credentials and an isolated test database were used for workflow tests; no real native catalogue cart has been received.

Validation: 82 automated tests passed; NSIS compiled the 0.7 installer. Windows execution remains unverified. Hosted/live provider results are recorded separately after deployment.

The public scheduled Commerce feed is gated by native catalogue activation and public product-photo publication. It exposes only the selected retail feed fields and allows Meta scheduled fetches to reflect current synced prices/availability. Meta scheduling/linking itself remains untested until the external catalogue exists.

0.8 validation covers PO drafts without financial effects, approval and partial/full goods receipt, excessive receipt rollback, reversal, concurrent offline PO conflicts, demand/pack/incoming planning, stock-alert episode deduplication and itemised daily summaries. Browser checks cover draft → approval → partial receipt, stock/remaining quantity and JavaScript errors. Expiry remains SKU-level; no batch ledger is claimed.

0.8 final checks: **89 automated tests passed**. Local Chromium completed purchase-order draft → approval → partial receipt and the existing WhatsApp-order confirmation → linked POS invoice. Hosted Chromium verified the planning workspace, catalogue setup, internal recipient diagnostics and photo catalogue with no JavaScript errors. NSIS compiled both local and hosted installers; execution on Windows is still unverified. The hosted update backed up the existing database/media and preserved credentials/pairing. All nodes must update to protocol 5 before online sync.
