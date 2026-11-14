# Al Hadiya Traders 2.0.0

- Returns with numbered credit notes (sales) and debit notes (purchases), partial by item, restocking the original lots.
- Split payment on one bill, optional round-off to the rupee, and a UPI QR for the exact amount on the checkout screen and printed bill.
- Cash drawer shifts with opening float, counted close and a printable day-end report.
- Stock count that posts only the differences.
- Reports net of returns, credit ageing by 30/60/90 days, credit and debit note list, and an HSN summary export.
- Bill of supply heading for composition dealers and FSSAI licence number on bills.
- The app opens in its own window when Edge or Chrome is installed.
- Includes everything in 1.3.0 and 1.4.0: offline licensing, lots with expiry, and the native compiled Windows program.

Updating keeps all data, accounts, pairing and the licence. Have your accountant confirm tax settings and document layouts before live GST use.

## 1.4.0

- Lots and expiry: one product can hold several lots, each with its own lot number and expiry. Purchases, opening stock and found stock record them; sales and café recipes use the earliest-expiring lot first and never an expired one.
- Inventory shows each product's lots with days left, flags lots inside 30 days and expired lots, and lets transfers and wastage name a lot. Reversals return stock to the same lots, and lots sync between PCs.
- A single product expiry from an earlier release becomes a lot over the stock on hand at the first start after updating.
- Native Windows program: the app is compiled with Nuitka. No Python runtime, source or bytecode is installed, and updating removes those left by earlier releases. Data, accounts, pairing and licence are preserved.
- Owner password recovery is now `app\AlHidayaTraders.exe --reset-owner USERNAME`.

## 1.3.0

- Offline licensing: a 60-day trial, then one signed licence file per PC. The Licence screen, under Settings, shows the Installation ID, status and days remaining, and installs a `.lic` file without internet.
- Expiry gives a 14-day reminder and 7 days of grace before the app becomes read-only. Records stay viewable, printable, exportable and backed up in every state.
- The installer now ships compiled bytecode instead of Python source, and removes source left by earlier releases during an in-place update. Data, accounts and pairing are preserved.
- Existing installations begin their 60-day trial on the first start after updating.

## 1.2.1

Repeated scans previously rebuilt the whole POS and its catalogue. Basket changes now update only the affected rows/totals, retaining the scan field and product controls. Product, stock and barcode lookups are indexed. Results are paginated: 60 POS products or 100 inventory/profile/history records, with the complete catalogue and history still searchable.

- F2 focuses scanning; F5 chooses a customer; F6 edits quantity; F7 edits discount; F8 checks out. Ctrl+Up/Down moves between basket quantities.
- Checkout Alt+C/U/D/B selects Cash/UPI/Card/Bank and the received amount. F10 prints a saved receipt; F2 returns to the next bill, keeping the café filter/location and resetting customer/discount/tier.
- Enter advances through validated single-line fields, Shift+Enter goes back and Ctrl+Enter saves explicitly. Tab reaches ordinary controls. Staff permissions, focus trapping and dialog restoration still apply.
- Purchase/PO rows support barcode/name search rather than repeatedly rendering thousands of select options. Enter moves through product, quantity and cost to the next item; Alt+C sets one case and Alt+P focuses amount paid. Unknown, ambiguous or unselected codes are blocked; a blank trailing row is ignored.
- Highlighted purchase suggestions stay selected when a pending search refresh completes.
- Inventory and customer profiles have search, paging and arrow navigation between record actions. F9 on Purchases searches the full purchase history.
- Draft quantity/customer/discount restore, unavailable-stock rejection, row removal, held-key suppression and pending-save guards are checked alongside exact stock, dues and invoice values.
- The release workflow checks 10,000 SKUs and 100 consecutive keyboard scans, keyboard-only desktop/web operation, café billing, 109 business/policy tests and actual Windows installation/update/data retention before publishing.

On the local isolated Chromium test with 10,000 SKUs, basket addition fell from roughly 1.3–2.2 seconds with the old full redraw to sub-millisecond median after the change. These are test-machine measurements, not a timing guarantee for every PC. Windows runs repeat the sustained-entry test with performance limits before release.

Upgrade in place under the same Windows account and installation path. The installer preserves existing accounts, data, identity and pending changes, and makes a pre-update backup. See [keyboard guide](docs/KEYBOARD.md) and [handover](docs/HANDOVER.md).

The temporary AWS review server remains deleted. Windows operates offline; shared-folder exchange requires an available transport and reconciled baseline. WhatsApp sending remains paused during the Meta review; restoration, rotated credentials, approved templates, signed webhooks, catalogue linkage and bounded opted-in delivery/cart checks remain necessary. The installer is unsigned; validate actual shop scanners and printers. Statutory GST credit notes, partial returns, IRN/e-way bills and filing require external handling.
