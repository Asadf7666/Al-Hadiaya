# Al Hadiya Traders 1.2.1

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
