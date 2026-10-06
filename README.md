# Al Hidaya Traders — Shop Manager 0.4.0

An owned Windows and web shop manager for an Indian trading warehouse/retail counter and a takeaway café. Every paired PC has all business functions. Warehouse and Outlet identify transaction locations, not device permissions or separate applications. Internet is not needed for local Windows operations. The browser website requires a connection to its server.

## Install or update Windows

1. Run `AlHidayaTraders-Setup-0.4.0.exe` on 64-bit Windows 10/11, under the same Windows account and installation directory as an existing app. The installer closes the app and creates a verified pre-update backup. It preserves the database, identity and pairing credential. Do not replace sample data or pair again during an upgrade of an already paired node.
2. Open the app from its desktop or Start Menu shortcut. The launcher serves the interface at `127.0.0.1:8765` and must remain open.
3. Choose the default transaction location in the header or Settings. Every node can work with both locations, receive purchases, record payments, manage stock and products, define recipes, issue credit bills and change business/GST details.
4. Confirm real prices, stock, pack quantities, barcodes and tax classifications before live trading. Karnataka defaults to state code 29. The installer is unsigned and remains a pilot; physical printer/scanner testing and the 0.4.0 installer execution on Windows 10/11 have not been verified here.

## Connect a node to the online business

1. As owner in the online app, open Account & staff → Connect a Windows PC. Choose its default location and generate a one-time code. The code expires after ten minutes and binds to one identity; it does not assign a restricted device role or stock quota.
2. On an empty Windows app or one containing only disposable samples, open Settings → Connect to online business. Enter the server HTTPS origin, code and a PC name. The app backs up existing local records, then adopts the server's shared records. This join flow does not merge real historical databases.
3. On an already paired node, upgrade in place and click Sync now. The 0.4.0 sync protocol requires every connected Windows installation to upgrade; older apps retain their local records but must update before exchange.
4. If the same server's IP/domain changes, use Settings → Update server address. This verifies the existing credential and business identity at the new HTTPS origin, and preserves records and pending operations. This does not migrate to a new server/business.
5. Exchange runs every 30 seconds while the launcher is open. Offline changes stay in the local database and upload on reconnection. The online server also relays changes between PCs. Repeated uploads are idempotent.

Device capability restrictions and per-PC stock allocations from 0.3.0 are superseded. Existing stock and invoices are preserved; old allocation metadata no longer limits operations. Customer and supplier ledger changes are validated against their documents/payments; invoice snapshots remain immutable. Any node can reverse a synced invoice if it is unreversed and its payment history permits reversal.

## Offline conflicts and shared data

All nodes see the last stock/ledger state they have received. Two disconnected PCs can therefore sell the same physical stock or collect the same due. This version does not guarantee global stock availability or credit limits while nodes cannot communicate.

Sync rejects an event that would make central stock or a party balance negative, exceed a customer's credit limit, duplicate a reversal, or violate invoice/ledger integrity. The whole event rolls back; its original local record remains, Settings shows the conflict, and subsequent events from that node wait behind it. Downloads continue where they can be applied. Reconcile the actual stock/payment situation before retrying. There is no automatic financial-conflict resolution or self-service void-pending-event screen; unresolved conflicts require assisted reconciliation. Do not delete database rows or sync files to hide a problem.

Product, profile, recipe and business-setting edits use timestamped last-write order. Concurrent edits can overwrite each other without a merge screen; keep node clocks synchronised and coordinate sensitive catalogue/GST changes. Concurrent creation of the same SKU/barcode is rejected instead of silently combining different products. Invoice IDs still include a device-derived prefix and financial-year sequence.

## Serverless folder sync

Before hosting a server, independent PCs can exchange immutable events through the same shared folder (for example an available-offline OneDrive folder or file replication tool). Enter the local path in each PC's Settings; paths may differ. Start with the catalogue and stock on one node, exchange those records before recording the same SKUs elsewhere, then operate from any node. All nodes have the same functions. Last exchange means a folder scan completed, not proof the transport provider has delivered files.

Folder and server sync cannot be enabled together. Never place the live SQLite database in a cloud folder or share it while running. Every PC needs its own database and identity; copying a live paired database to another PC duplicates identity and is not pairing.

## What is implemented

- POS product search and keyboard-input barcode scanning, quantities, case conversion, retail/wholesale pricing, discounts and saved invoices.
- Cash, UPI, card and bank **payment recording**; customer credit and supplier dues with subsequent payments and party ledgers.
- Separate warehouse/outlet stock, stock transfers, purchases, average recorded acquisition cost, low-stock alerts, SKU expiry dates and reasoned wastage/count adjustments.
- Café recipe definitions and automatic ingredient deduction per sale, with available-serving estimates.
- Tax-inclusive prices, configurable GST and percentage cess, CGST/SGST or IGST based on place of supply, HSN/SAC, immutable invoice snapshots and financial-year invoice sequences of at most 16 characters.
- 58 mm, 80 mm and A4 print layouts through the Windows/browser print dialog; save invoices as PDFs there.
- Sales, tax, purchase, estimated contribution and expense reports; CSV stock, sales and GST detail exports.
- Atomic bulk CSV product import, blank manufacturer-barcode fields ready to scan, and 379 editable Indian-market product/size templates.
- Local SQLite database, verified backup snapshots, CLI restore, pre-update backup, and idempotent exchange of saved transaction files between independent PCs.

The starter catalogue is a collection of **templates**, not a complete or verified current list of Indian manufacturers' SKUs. Pack availability differs by region and changes over time. Names, size examples and packaging are editable. Prices and stock are zero; actual GTIN/EAN/UPC barcodes are deliberately blank; HSN/rates are unconfirmed. A product cannot be sold without a selling price. GST-enabled transactions require the product's tax confirmation and HSN/SAC. A tax rate of zero must be an intentional verified classification, not an assumption from a template.

## Customer profiles and WhatsApp

Profiles retain mobile, email, address, GSTIN, notes, retail/wholesale preference, credit limit, opt-in and ledger history. Café walk-in profiles are optional; mobile lookup is available. Supplier profiles, credit sales and payments work on every node, including offline.

WhatsApp configuration and queue controls are available on each node. Automation starts disabled and requires the official Meta Cloud API sender ID, supported Graph API version, token, approved language/templates and recipient opt-in. The WhatsApp Business mobile app subscription alone does not provide the API token. Templates use three body parameters: invoice = customer/name, invoice number, amount; payment = name, amount, note; internal = business, update type, summary. Internal updates cover low stock, purchases, transfers and daily summaries. Group sending, PDF attachment delivery and delivery/read webhooks are not implemented.

Configure one active notification sender for the business to avoid separate nodes sending duplicate summaries. Sender tokens, recipient configuration and outboxes are local and do not replicate. Windows DPAPI protects tokens for the current account; tokens are excluded from database backups and sync. Internet is needed to send. API accepted is not delivered/read. Interrupted/lost responses become uncertain and are not automatically retried. No actual WhatsApp messages have been sent during testing.

## Backups, closing and updates

The live database lives at `%LOCALAPPDATA%\AlHidayaTraders\shop.sqlite3` for the Windows account using the app. Local verified backups go into its `backups` folder. An optional additional backup folder can be configured for an external drive or cloud-folder backup.

Backups run every 15 minutes while the app is open and on a clean close. **Back up now** or **Download backup** creates a SQLite snapshot safe to copy. Automatic backup failure does not stop billing; check the last successful backup in Settings. In this pilot, backup files are retained until you archive/delete them yourself; monitor disk space.

To quit, use **Settings → Close app safely**. Closing only the browser tab leaves the local app process running to perform scheduled sync/backup.

To update, run a newer trusted `AlHidayaTraders-Setup-…exe` under the same Windows account and use the same installation directory. The installer closes the local app, verifies a local database backup, then replaces application files. If shutdown/backup fails, the installer aborts before changing those files. The database lives outside the app directory and is preserved. Uninstall also preserves the shop database and backups. No automatic remote update feed is configured; distributing and rerunning the versioned installer is the current update process.

To restore, close the app, keep a copy of current data, then use Command Prompt:

```bat
"%LOCALAPPDATA%\Programs\AlHidayaTraders\runtime\python.exe" "%LOCALAPPDATA%\Programs\AlHidayaTraders\app.py" --restore "D:\Backups\AlHidaya-backup.sqlite3"
```

Restore validates the backup and makes a local snapshot before replacement. When devices have already exchanged transactions, restore is an administrator recovery action: reconcile with the other PC before resuming trading. A restored earlier snapshot may need newer immutable events from the shared folder; test that recovery process with a copy first.

## Hardware

- Scanners that emulate a keyboard work through the barcode search field (press F3, scan, scanner sends Enter). SKU codes also work. Dedicated scanner drivers and barcode-label generation are not included.
- Use Windows-installed printers; select the correct paper size in the print dialog. A4 and 58/80 mm layouts are supplied, but output depends on the actual driver, paper margins and device. No universal device compatibility is claimed.
- UPI/card/bank selections record an externally completed payment. They do not initiate or verify payment-terminal or bank transactions.
- Cash drawers, weighing scales, silent raw ESC/POS printing and kitchen hardware integrations require specific device testing/adapters.

## Staff permissions and pilot boundaries

Node capabilities are equal. The online app still has owner/manager/cashier/viewer permissions for staff accounts, as requested; those apply to people rather than making a warehouse or café PC special. Windows currently relies on the Windows account and local-file access, with no individual local staff login. Protect its files and do not expose its local HTTP listener publicly.

- Expiry is per SKU, not batch/FEFO. Separate batch SKUs are needed.
- Full internal reversals require refund reconciliation and do not generate statutory GST credit notes. Partial returns are not implemented.
- Basic regular-registration GST and percentage cess are present; composition billing, specific cess, IRN/e-way bills, portal filing and accountant-certified books are not provided.
- Contribution is a management estimate using recorded acquisition/recipe costs, not statutory profit/valuation.
- Orders, challans, split payments, cash shifts, loyalty, Tally integration and production recovery/scaling remain future work.
- The hosted review uses central SQLite behind Caddy HTTPS with hashed passwords, sessions, CSRF protection and staff roles. It is a review deployment. Its previously scheduled expiry/deletion was cancelled at the user's request. There is no newly scheduled expiry.

## Source and verification

Python 3.12+ with the standard library runs the app; no runtime pip dependencies are needed:

```sh
python app.py
python -m unittest discover -s tests -v
```

For disposable exploration use `python app.py --data-dir ./sample-data --port 8766` and Explore sample shop. Packaging uses NSIS and the pinned official Python 3.14.8 embedded runtime with SHA-256 verification. Build tooling is not needed on shop PCs. See `packaging/build.py`, `TESTING.md` and `RESEARCH.md`.
