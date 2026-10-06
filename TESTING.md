# Verification history and current pilot 0.4.0

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
- Hosted deployment and real signed webhook delivery remain pending AWS reauthentication and Meta callback setup.
