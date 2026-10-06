# v1 handover and pause

Validated Windows installer: [AlHidayaTraders-Setup-1.2.1.exe](https://github.com/Asadf7666/Al-Hadiaya/releases/download/v1.2.1/AlHidayaTraders-Setup-1.2.1.exe). [Release and checksum](https://github.com/Asadf7666/Al-Hadiaya/releases/tag/v1.2.1). SHA-256: `2295a3e47dc47ebf8cb361871360e7a14c9cf730f78fd6388467961a1b98997f`. [Windows checks](https://github.com/Asadf7666/Al-Hadiaya/actions/runs/37513878464) passed for source commit `253d35d58d03cd48a08f2077bb22da9f606ad70f`: 109 business/policy tests, keyboard-only desktop/hosted workflows, sustained entry with 10,000 SKUs and 100 consecutive scans, café billing, and actual installation/update/data retention. The downloaded installer matches the build/release checksum. Workflow artifacts are a fallback. Keep a local copy and validate actual shop hardware before trading.

Café POS sells menu items such as coffee and mojitos. Ingredients per serving are internal stock instructions, not a product sold to the customer. A customer sees the drink name, quantity and price on their bill. Packaged items use their normal stock quantities.

GitHub retains source; the Windows workflow publishes a versioned installer after its tests pass. Customer databases, tokens, App Secrets, pairing secrets and passwords are excluded from source and release assets.

## Start real trading

1. Keep an external backup, upgrade every PC in place and create local owner access. Assign café staff to Outlet; owners have all functions on every node.
2. Confirm shop/support details, Karnataka state code and registration. Leave GST off while unregistered; verify rates/cess and invoice details with the accountant.
3. Keep sample data separate. Establish a clean shared business snapshot, real opening quantities/dues, actual barcodes and pack quantities. Do not independently create equivalent stock on several nodes.
4. Set café prices and recipes, transfer ingredients into Outlet and validate a café bill against ingredients consumed.
5. Validate shop scanners and 58/80 mm or A4 printing, purchase/payment/sale reporting and recovery on the actual PCs.

## WhatsApp after review

Keep sending off during review. Reset the App Secret shared in chat and revoke exposed access tokens; save replacements directly in protected application fields. Confirm account restoration, sender permissions/quality, support/privacy details, approved branded templates, signed messages webhook and linked owned Commerce catalogue. Perform a small, bounded opted-in cart/delivery/STOP check before broader activation. Do not bypass restrictions. Use one active sender for the business.

## Review server permanently removed

The owner requested server removal on 6 October 2026. The saved private business/photo ZIP passed archive and SQLite integrity checks before termination. It contains 15 products, 7 invoices, 10 customer/supplier profiles and one uploaded image from the review environment. Newer records held only on a Windows PC are still on that PC; removal does not merge them.

The review VM, root disk and network interface are gone. Its dedicated security group and temporary IAM instance profile/role were removed and verified absent. Shared VPC/subnet resources were retained. No scheduled automatic expiry remains. The former review address, website, online sync and WhatsApp webhook are unavailable.

Keep the verified installer, private backup and source. Windows works offline. For each PC still pointing at the deleted server, upgrade in place, then use Settings → Server permanently removed? and type RETIRED. This owner-only operation makes a local backup and preserves all business records, unsent/incoming events and recovery identity before removing the old address. It pauses WhatsApp and does not claim a completed final exchange. A failed backup leaves the connection unchanged.

Reconcile records on every PC with the saved server backup before enabling a shared available-offline folder. Do not independently reload opening stock or join with disposable-sample replacement when real trading records exist. Folder scans alone do not prove transport delivery. Unresolved financial conflicts need assisted reconciliation. A future hosted deployment needs its own HTTPS, backup, access and webhook configuration.

## Keyboard access

F2 opens scanning; F3 searches; F5 selects a customer; F6 edits quantity; F7 edits discount; F8 checks out. Alt+C/U/D/B chooses checkout payment, F10 prints a saved receipt and F2 begins the next bill. Enter advances through validated fields, Shift+Enter goes back and Ctrl+Enter saves explicitly. Purchases scan/search each item, then Enter advances through quantity/cost to the next item; Alt+C sets a case and Alt+P selects amount paid. Page Up/Down browses full results and arrows move between products/record actions. See [complete guide](KEYBOARD.md).

Basket updates retain the scan input rather than redrawing the entire catalogue. Product/stock/code indexes and pagination bound routine rendering. On the final isolated Windows run with 10,000 SKUs, median basket addition was 0.3 ms and scan-to-frame p95 was 15.1 ms; these are test-machine measurements, not a guarantee for every PC. Unknown/ambiguous codes, stock limits, restored drafts, pending saves and delayed suggestion selection are checked before release.

## Recovery, privacy and updates

Download backup with photos produces a portable archive with staff/session/pairing verification rows and secret files excluded. It still contains private business records. Automatic/database-only snapshots can include password hashes and account metadata and must also stay private.

Restore backup validates the archive/database, preserves current local accounts/device identity, clears sessions and leaves sync/WhatsApp off. Recovery failure restores previous records/photos. Paired-node recovery needs reconciliation. Keep an external backup; local snapshots alone do not protect against loss of the PC.

Lost owner passwords can be reset from the Windows account owning the data using `tools/reset_owner.py`; it prompts privately. Apply off-WhatsApp opt-outs through profile/contact consent controls. For data requests, verify identity and reconcile required financial retention before removal. Keep public privacy/deletion support routes accurate and do not store/send sensitive identifiers in message notes.

Periodic snapshot retention keeps the latest eight plus one per latest seven recorded days. Manual/update/recovery snapshots remain until the owner archives them. Photos are included; keep an external copy and monitor storage.
