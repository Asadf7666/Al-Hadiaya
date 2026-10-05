# Al Hidaya Traders — Shop Manager 0.2.0

A functional **pilot**, built for an Indian trading warehouse that also serves retail customers, plus a separate takeaway café/shop outlet. Works locally without internet; English UI with Al Hidaya black-and-gold branding. This is an owned local application, with no app account, subscription, telemetry or hosted application service.

## Install on Windows

1. Download `AlHidayaTraders-Setup-0.2.0.exe` from `dist/`.
2. Run it on **64-bit Windows 10 or Windows 11**. It installs for the current Windows account; administrator rights and a separate Python installation are not required.
3. Open **Al Hidaya Traders** from the desktop or Start Menu. Its interface opens in your default browser, backed by a local process on `127.0.0.1:8765`. Internet is not required to open or use it.
4. Open **Settings & sync**. Select **First/main warehouse PC** on exactly one PC, and **Join the existing business** on all additional PCs. Choose **Warehouse** on the warehouse PC and **Outlet** on the outlet PC. Warehouse setup automatically adds 379 product templates. The outlet receives the same catalogue through sync.
5. Enter the business address and phone. Karnataka defaults to state code **29**. Enable GST only with your actual regular GST registration; otherwise the app issues sales receipts without collecting GST.
6. Set actual product prices, MRP, costs, HSN/SAC, verified tax rates, pack quantities and manufacturer barcodes. Add opening stock through product creation, CSV import of new SKUs, or a stock adjustment for an existing template. Receive supplier purchases thereafter.
7. The warehouse PC also bills customers directly against warehouse stock, at retail or wholesale prices. Transfer physical goods from warehouse to outlet before selling them at the outlet. Set café ingredient units and recipes before café billing.

The installer includes the official Python 3.14.8 embedded Windows runtime and its licence. It is currently **unsigned**. Its build was verified on Linux; actual Windows install, update, uninstall and physical printer/scanner testing have not been performed in this workspace.

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

## Sync between separate addresses

Use one **main warehouse PC** for stock administration; additional trading/café tills use assigned stock allowances.

1. Set up the same shared folder using your existing cloud-folder/replication software, for example a shared OneDrive folder or a self-managed file replication tool.
2. Make the folder available offline on **both PCs**. Give access only to trusted business operators; the transaction files contain business records and are not encrypted by this app.
3. In each app's Settings, enter the **local path to that shared folder**. Paths may differ across PCs.
4. Each device creates immutable JSON transaction files inside `AlHidayaSync-v1`. The app exports/imports every 30 seconds while open; **Sync now** runs an exchange immediately. Your folder software transports the files when online.
5. For first setup, assign Warehouse, configure its catalogue and stock, sync it, wait for the folder to upload/download, and then sync the Outlet. Do **not** independently enter the same products on both devices.
6. A transfer is available to the receiving PC only after the transfer transaction reaches it. During outages, additional tills bill only against their remaining stock allowance. The main PC sells unallocated stock. Location restrictions prevent one PC from editing the other site's sale/stock operations.
7. Failed imports remain unapplied and appear under **Sync needs attention**. The transaction remains in the shared folder and can retry after missing earlier records arrive. Never delete/edit transaction files to hide a conflict.

`Last exchange` means a local folder scan completed, **not confirmation of upload or receipt by the other PC**. This does not implement a hosted sync service. Keep both Windows clocks automatically synchronised: master-record conflicts use timestamped last-write order. Product and recipe administration belongs to the warehouse PC. Customer credit and payments are managed on the main PC. Additional tills require fully paid bills in the serverless phase.

Never share the live SQLite database using a cloud folder, network drive or manual copying while it is in use. Each PC must have its own database and device identity. Restoring one PC's backup onto the second PC as an independent install duplicates its device identity and is not a pairing procedure.

## Stock allowances for additional PCs

Pair each additional PC by selecting **Join the existing business**, its location and sync folder. Sync its registration to the main PC. In **Inventory → PC stock allowances**, grant quantities to the target till, then sync both PCs before billing. Transfer goods to Outlet before granting outlet stock. For café recipes, grant the ingredients consumed by each recipe.

A grant reserves existing stock; it does not add or transfer physical goods. The main PC cannot sell quantities reserved for other tills. Each disconnected till can sell only its grant, avoiding overselling by several offline PCs. A till releases unused allowances itself; sync that release before reallocating. The owner cannot safely reclaim a grant while its till may still be selling offline.

For an upgrade from 0.1.0: stop billing on all PCs, exchange all outstanding events, back up every PC, upgrade all installations, establish one main PC, then register and allocate each additional till. Do not mix old and new builds during trading.

## Customer profiles and WhatsApp automation

Customer profiles keep phone, email, address, GSTIN, notes, preferred retail/wholesale pricing, credit limit and ledger history. Café walk-in billing remains available without a profile; optional mobile lookup finds existing customers. Main-PC credit limits are enforced before credit billing.

**WhatsApp updates** configures individual internal recipients and a local message queue. Internal updates cover low stock (once per product/day/recipient), purchases, warehouse-to-café transfers, and an optional daily summary. Customer notifications cover invoice summaries and later payment receipts. These send text summaries, not invoice PDFs. Main-PC queueing also handles sales received through sync. Daily summaries report only records received by the latest exchange and run while the main app is open, after its configured local time.

Automation starts disabled. Configure your official Meta WhatsApp Business sender ID, supported Graph API version, token, language, and approved templates. Each template must have exactly three body text parameters and no required header/button parameters: invoice = customer/name, invoice number, total; payment = customer/name, amount, note; internal = business, update type, summary. Obtain recipient opt-in before enabling their notifications. Use individual mobile recipients; group sending is not implemented. Meta messaging charges may apply.

The main PC sends while the app is open and internet is available; SQLite retains queued messages across outages. Temporary API errors retry with backoff. Lost responses and interrupted sends become **uncertain**, with no automatic resend. **Accepted** means accepted by Meta, not delivered/read. Delivery webhooks, manual resolution/resend controls, and the AWS online platform are not implemented in this release. Do not expose the local app publicly.

The token is excluded from the database, sync, exports, and database backups. Windows protects it using your Windows account (DPAPI); source runs on other operating systems use a private local file. Reconfigure it after moving/restoring to another account or PC. Internal recipients, WhatsApp configuration, and the outbox belong to the main PC and do not replicate to tills.

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

## Pilot boundaries before live use

- Main-PC/till restrictions control normal app workflows; they are not staff authentication. The application uses Windows-account/local-file access rather than individual staff logins. Local records and sync files are not encrypted by the app. Do not expose its HTTP listener to a LAN or internet.
- Expiry is per SKU, not per batch or FEFO allocation. Use separate SKUs for separate batches for now.
- Internal full-document reversals restore stock/credit and require external refund reconciliation. They are **not statutory GST credit notes**, and partial item returns are not implemented. Avoid using this reversal flow for GST returns; add accountant-reviewed credit/debit-note handling before that workflow goes live.
- Regular-registration basic GST calculation is present. Composition scheme billing, automatic HSN/rate lookup, specific/non-percentage cess, e-invoice IRN/QR, e-way bill generation, GST return filing, ITC eligibility, accountant-certified books and automated regulatory updates are not provided.
- Contribution reports use sales excluding output tax minus recorded acquisition/recipe costs and expenses. Acquisition costs include supplier tax. This is a management estimate, not a statutory profit-and-loss statement or stock valuation method for filing.
- Purchase/sales orders, batch stock, delivery challans, partial returns, staff management, split payments, shift cash closing, loyalty and Tally integration remain future work.
- Sync is eventual and folder-based. The local queue and conflict handling are tested; live cloud-provider transport, power failures, large-volume performance and a full trading shift still need a supervised pilot.

## Run from source / rebuild

Python 3.12+ with the standard library is enough to run the app; there are no runtime pip dependencies:

```sh
python app.py
python -m unittest discover -s tests -v
```

For a disposable exploration database:

```sh
python app.py --data-dir ./sample-data --port 8766
```

Choose **Explore sample shop** while the database is empty and unassigned. Sample invoices are never inserted automatically. Always use a separate clean data directory for live trading.

See `packaging/build.py` for reproducible bundled-runtime installer builds (NSIS required). `packaging/build-windows.bat` runs it on a Windows build machine with Python and NSIS; those tools are **not needed on shop PCs**. The builder verifies the pinned embedded runtime SHA-256 before packaging.

Research and the choices behind this pilot are documented in `RESEARCH.md`.
