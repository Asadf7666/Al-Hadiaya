# Al Hadiya Traders — Business Manager 1.0.0

An owned Windows and web shop manager for an Indian trading warehouse/retail counter and a takeaway café. Every paired PC has all business functions. Warehouse and Outlet identify transaction locations, not device permissions or separate applications. Internet is not needed for local Windows operations. The browser website requires a connection to its server.

## Install or update Windows

1. Run `AlHidayaTraders-Setup-1.0.0.exe` on 64-bit Windows 10/11, under the same Windows account and installation directory as an existing app. The installer closes the app and creates a verified pre-update backup. It preserves the database, identity and pairing credential. Do not replace sample data or pair again during an upgrade of an already paired node.
2. Open the app from its desktop or Start Menu shortcut. The launcher serves the interface at `127.0.0.1:8765` and must remain open.
3. Choose the default transaction location in the header or Settings. Every node can work with both locations, receive purchases, record payments, manage stock and products, define recipes, issue credit bills and change business/GST details.
4. Confirm real prices, stock, pack quantities, barcodes and tax classifications before live trading. Karnataka defaults to state code 29. The installer is unsigned. Physical printer/scanner acceptance is required; the Windows release workflow executes installation/update checks before publishing a download.

## Connect a node to the online business

1. As owner in the online app, open Account & staff → Connect a Windows PC. Choose its default location and generate a one-time code. The code expires after ten minutes and binds to one identity; it does not assign a restricted device role or stock quota.
2. On an empty Windows app or one containing only disposable samples, open Settings → Connect to online business. Enter the server HTTPS origin, code and a PC name. The app backs up existing local records, then adopts the server's shared records. This join flow does not merge real historical databases.
3. On an already paired node, upgrade in place and click Sync now. Version 1.0 uses sync protocol 5 for shared WhatsApp orders and SKU mappings. Upgrade every paired Windows PC before exchange. Existing data, identity, pairing and unsent events are preserved. Folder sync writes version 3 files; update all nodes sharing that folder.
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

WhatsApp setup, recipients, outbox controls and owner-approved customer campaigns are available on every node. Use one active sender for the business, preferably the hosted app. The hub now queues receipts and internal updates from transactions that arrive from offline PCs after sync. A working Meta sender, API token, Business Account ID and approved templates are required. Configure the sender in WhatsApp updates. Windows DPAPI protects secrets for the current Windows account; Linux stores them in files with mode 0600. Secrets are excluded from sync, database exports and database backups.

Customer receipts and promotional offers have separate opt-in fields in the customer profile. Promotional consent and its recorded date sync with customer profiles. Owners can draft a retail/wholesale/all opted-in customer campaign, preview the message and audience, and approve or schedule it. Every campaign requires approval; a draft sends nothing. Sending checks consent again and deduplicates normalized phone numbers within the campaign. Campaign cancellation stops messages that have not started sending. Scheduling requires the active sender to be running and online; the hosted worker checks every ten seconds, desktop every thirty seconds. Meta template status must be refreshed before approving a campaign if its cached check is over 24 hours old.

Internal alert options cover low stock, purchases, transfers, sales, payments, expenses, invoice reversals and daily sales summaries. Notification scheduling defaults to Asia/Kolkata, independently of the server timezone. Template JSON for invoice, payment, internal and offer messages is in `whatsapp/templates.json`. All four use three body text parameters. Meta must approve them. The mobile WhatsApp Business app subscription does not provide Cloud API access.

The hosted `/webhooks/whatsapp` endpoint verifies subscription challenges and Meta's SHA-256 signature using protected webhook credentials. It records sent/delivered/read/failed statuses and processes STOP, UNSUBSCRIBE, CANCEL and OPT OUT replies without sending a response. Opt-outs sync to the PCs. Set up the app secret and verification token through WhatsApp updates, then subscribe the messages field in Meta. The app includes public `/privacy` and `/data-deletion` pages; review and complete business contact details before production use. See `whatsapp/SETUP.md` for remaining Meta steps.

Outboxes, campaigns, internal recipient lists and sender credentials are local to their sender; they do not replicate. Use the hosted sender to track webhook delivery for the messages it sends. Do not enable multiple independent senders for the same alerts. API accepted is distinct from delivered/read. Uncertain requests are never automatically retried. This implementation does not create or post to WhatsApp Channels or app broadcast lists; outreach sends individual template messages. Test-number access is limited to Meta-verified recipients, and production requires your business number and credentials. The owner confirmed an initial Hello World delivery. Expanded live tests returned 16 accepted Meta sample messages; delivery of that batch awaits recipient confirmation. Actual Al Hadiya templates remain pending and the catalogue test is blocked. Automated campaign tests use mocks. See `whatsapp/LIVE-TEST-RESULTS.md` for the exact limits.


## Backups, closing and updates

The live database lives at `%LOCALAPPDATA%\AlHidayaTraders\shop.sqlite3` for the Windows account using the app. Local verified backups go into its `backups` folder. An optional additional backup folder can be configured for an external drive or cloud-folder backup.

Backups run every 15 minutes while the app is open and on a clean close. **Back up now** or **Download backup** creates a SQLite snapshot safe to copy. Automatic backup failure does not stop billing; check the last successful backup in Settings. Manual/update/recovery snapshots are retained until you archive them. Periodic snapshots retain the latest eight plus one per latest seven recorded days. Monitor disk space and keep an external copy.

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

## Staff permissions and release scope

Node capabilities are equal. The online app still has owner/manager/cashier/viewer permissions for staff accounts, as requested; those apply to people rather than making a warehouse or café PC special. Windows has offline owner setup and individual local staff sign-in with the same roles. Accounts/passwords stay on their installation, while business records sync. Protect its files and do not expose its local HTTP listener publicly.

- Expiry is per SKU, not batch/FEFO. Separate batch SKUs are needed.
- Full internal reversals require refund reconciliation and do not generate statutory GST credit notes. Partial returns are not implemented.
- Basic regular-registration GST and percentage cess are present; composition billing, specific cess, IRN/e-way bills, portal filing and accountant-certified books are not provided.
- Contribution is a management estimate using recorded acquisition/recipe costs, not statutory profit/valuation.
- Native WhatsApp trading orders and procurement orders are implemented. Challans, split payments, cash shifts, loyalty and Tally integration remain outside this release.
- The hosted review uses central SQLite behind Caddy HTTPS with hashed passwords, sessions, CSRF protection and staff roles. It is a review deployment. Its previously scheduled expiry/deletion was cancelled at the user's request. There is no newly scheduled expiry.

## Source and verification

Python 3.12+ with the standard library runs the app; no runtime pip dependencies are needed:

```sh
python app.py
python -m unittest discover -s tests -v
```

For disposable exploration use `python app.py --data-dir ./sample-data --port 8766` and Explore sample shop. Packaging uses NSIS and the pinned official Python 3.14.8 embedded runtime with SHA-256 verification. Build tooling is not needed on shop PCs. See `packaging/build.py`, `TESTING.md` and `RESEARCH.md`.


## Photo campaigns and customer catalogue (0.6)

Owners can upload JPEG/PNG images up to 5 MB, use IMAGE-header marketing templates, and preview the photograph with the exact message before approving. Templates may have zero or three body variables; unsupported dynamic buttons, flows and carousels remain unavailable for app campaigns. Pending templates can be drafted but cannot be approved for sending.

In WhatsApp updates, publish selected sellable products with a photograph, positive retail price and description, then enable the hosted customer catalogue at `/catalogue`. Ingredient records and unpublished items stay private. Customers can browse, search, build a basket and submit an order request with contact consent. The server recalculates prices and suppresses duplicate submission IDs. Requests do not reserve stock, collect money, create invoices or enrol customers for marketing. An owner can review a request, change its status and prepare a normal POS bill for final checkout.

This web catalogue is independent of Meta Commerce; it does not create a native WhatsApp Shop. Native product messages still require a linked Meta catalogue and appropriate permissions. Uploaded images, web catalogue publication and web order requests belong to the installation where they are created; they are not part of business-record sync. Configure the public catalogue on the hosted app. Folder backups include a matching `.media` sidecar directory; retain it alongside the database when restoring. Database-only downloads do not contain photographs or sender secrets.


## Native WhatsApp trading orders (0.7)

WhatsApp orders are a separate shared workspace. Link an owned Meta Commerce catalogue to your WABA in Meta, save its numeric ID, check connection/cart visibility, subscribe the signed `messages` webhook, and enable catalogue automation. Customers send MENU/CATALOGUE/SHOP, browse the native WhatsApp catalogue and send their cart inside WhatsApp. Incoming signed `order` messages become trading orders with source-message deduplication, base-unit/case conversion and current Warehouse price/stock checks. An acknowledgement is queued automatically. STATUS/ORDERS replies show the latest order for that sender only; CANCEL WA-… cancels an unbilled, unprocessed order. STOP disables service contact and queued notifications without enrolling anyone in marketing. START reopens the conversation but does not restore promotional consent.

Map retailer IDs to packaged trading products and units per catalogue item (single bottle or case). Publish actual photos and confirmed prices first, then download the Meta feed CSV from the hosted order workspace and upload it to Commerce Manager. For automatic catalogue updates, configure Commerce Manager to fetch the hosted `/commerce-feed.csv` URL on its hourly schedule after linking/enabling the catalogue. Each fetch reflects current synced prices and Warehouse availability. Initial imports can use the downloaded CSV. Updates follow Meta’s feed schedule and processing time; orders are rechecked before acceptance and invoicing.

Staff review new/needs-review orders, confirm, pack, mark ready, create a linked normal POS invoice and complete. Price mismatches require explicit customer agreement to revised prices; unknown items, non-INR currency and insufficient stock remain blocked. Stock is deducted by the normal invoice, not reserved on acknowledgement. Orders/mappings sync to all compatible nodes, including offline operation once received. Independent offline duplicate invoices produce a sync conflict for staff reconciliation; the server does not silently keep both. Optional customer profiles and credit use the existing POS controls. Invoiced orders cannot be cancelled through the order status switch; normal accounting reversal controls apply.

Internal alerts cover incoming orders and order updates, sales, purchases, customer/supplier payments, expenses, transfers, reversals, low stock and daily summaries according to sender settings. Add opted-in staff recipients. A genuine inbound message opens that sender's 24-hour service window for direct staff/customer service replies; otherwise approved templates are required. Pending/rejected templates are visibly blocked and checked again, rather than treated as delivered. Only one sender should be active for shared automation. Hosted delivery needs Internet; offline stock/billing/order management still works, and alerts are generated after sync.

The Meta catalogue, callback/app-secret subscription and approved production templates are external prerequisites. The current test account has no linked catalogue, no webhook credentials and pending branded templates; local tests do not establish live native cart delivery. WhatsApp does not take or verify payment in this release.

## Planning, procurement and stock alerts (0.8)

Every updated node has Planning & procurement. Set preferred supplier, lead time, coverage days and safety stock per product/location. Recommendations use actual unreversed sales movements over 30 days, including café ingredient consumption, and subtract outstanding approved/sent purchase orders. Quantities round up to pack sizes; without history, only safety stock is used. Outlet suggestions show available Warehouse transfers. These are staff-reviewed recommendations, not automatic supplier commitments.

Purchase orders progress from draft to approved/sent and partial/full receipt, with cancellation of remaining quantities. Drafting/approving does not change stock or supplier dues. Receive goods opens the existing purchase invoice form with remaining quantities and estimated costs; enter actual supplier invoice reference, quantity, costs and payment. Saving atomically increases stock, supplier dues and received PO quantities. Invoice reversal adjusts the linked PO. Concurrent offline receipt/status changes produce an explicit sync conflict instead of silently overwriting quantities. Sync before receiving shared orders and reconcile conflicting invoices with an accountant.

Internal notifications now itemise invoice products, quantities, price/tax/payment, stock additions/deductions and resulting location balances; profile, catalogue, recipe and adjustment alerts are configurable. Scheduled daily summaries include sales, purchases, payments, expenses, ledger dues, items sold, stock movements, outstanding replenishment and open POs. Long summaries split into bounded messages. Summaries reflect data available when queued; unsynced transactions cannot be included.

Stock alerts cover location-specific low stock, stockouts, lead-time reorder needs, and recorded SKU expiry within seven days. Each condition sends once per active episode; replenishment clears it and a later recurrence can alert again. Alerts remain visible in the workspace and daily summary. Expiry is per SKU: use separate SKUs for separate batches. One configured online sender should handle WhatsApp delivery; other nodes sync business events. Delivery still requires the authenticated Meta service window or an approved template, sender availability and recipient opt-in.

Upgrade every Windows PC to 1.0.0 before syncing with the updated server (protocol 5 / file-sync format 3). Existing databases, pairing and customer records are preserved by the update. Check the Windows release workflow result and validate actual shop hardware before trading.


## v1 access, reliability and policy upgrade

Download the versioned installer from [GitHub Releases](https://github.com/Asadf7666/Al-Hadiaya/releases) after the Windows workflow passes. On the first desktop v1 launch, create an owner account (12–256 character password); sign-in works offline. Existing online passwords remain. Staff & access creates accounts, disables/enables staff and resets passwords; disabling/resetting revokes sessions. For local owner recovery, run the installed `tools/reset_owner.py --username owner` with the included Python console runtime under the Windows account owning the data.

Financial retry keys commit with stock and ledger changes. Retrying the same interrupted request does not save a second bill. Unfinished POS baskets survive a tab reload; review current stock/prices before checkout. Café & recipes → Open café POS selects Outlet and the Café menu filter; walk-in customers are optional and saving bills consumes configured recipe ingredients. Pack-entry helpers, mobile navigation and role-aware screens reduce routine entry. Background backup, sync and WhatsApp tasks run independently and show status.

Settings → Download backup with photos creates a portable ZIP containing private records/photos but no staff/password/session/pairing verification rows or secret files. Restore validates archives/integrity, makes a safety backup, preserves current local accounts/device identity and clears sessions; failures restore previous records/photos. Paired/folder-synced recovery requires reconciliation. Raw database/automatic snapshots can contain local password hashes and account metadata; protect every backup.

Finish sync & disconnect server is for permanent retirement after all nodes stop trading and reconcile. It verifies a final exchange and backup before switching this node to local operation. Configure the same shared folder on reconciled nodes afterward. For a temporary VM shutdown, keep pairing and simply resume exchange when the server returns. A retained credential can resume the same business using Update server address.

WhatsApp sends require an approved account, acceptable sender quality, supported/fresh approved templates for their purpose, consent and genuine service windows. New consent/changed mobiles require evidence notes. Restrictions/expired credentials pause sending. Batches and recipients are paced; promotional offers have a one-per-recipient/day app cap. Human-support commands route to the shop. Catalogue publication needs an owner review and is invalidated by changed product details. Regulated goods are excluded from this shop catalogue.

As of 6 October 2026 the business account review is pending and hosted sending is off. Live production validation is blocked until account restoration, credential rotation, approved branded templates, signed webhook subscription, owned catalogue linking and a genuine cart/delivery/STOP check. Read [policy mapping](docs/WHATSAPP-POLICY.md), [handover](docs/HANDOVER.md) and [release notes](RELEASE-NOTES.md). Guardrails reduce risk; they do not guarantee that Meta will never restrict an account.

Periodic snapshot retention keeps the latest eight plus one per latest seven recorded days. Manual/update/recovery snapshots remain until the owner archives them. Photos are included; keep an external copy and monitor storage.
