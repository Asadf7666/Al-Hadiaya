# Work with the keyboard

The counter workflow is scan → quantity/customer if needed → payment → save → print → next bill. The scan input stays in place when the basket changes. Large catalogues use indexed product/stock/code lookups and paginated results; every product remains searchable.

| Key | Action |
| --- | --- |
| F2 | Open POS ready to scan; from a saved receipt, start the next bill |
| F3 | Search products, inventory, profiles or invoice history; scan/search a purchase item |
| F4 | Add or receive on the current page, when permitted |
| F5 | Find/choose the bill customer by name or mobile; walk-in is available |
| F6 | Edit the last touched basket quantity; Enter returns to scanning |
| Ctrl+Up / Ctrl+Down | Move between basket quantities |
| F7 | Edit the bill discount; Enter returns to scanning |
| F8 | Open checkout; in a purchase form, focus amount paid |
| Alt+C / U / D / B | In checkout: Cash / UPI / Card / Bank, then focus amount received |
| F10 | Print the saved receipt currently open |
| F9 | Sale history; from Purchases, purchase history |
| Enter / Shift+Enter | Next / previous single-line form field; validate before moving forward |
| Ctrl+Enter / Command+Enter | Save the current form with normal validation |
| Alt+C | On a purchase row, set one case using its configured pack quantity |
| Alt+A / Alt+P | In a purchase form, add/focus the next item / amount paid |
| Page Up / Page Down | Previous / next POS, inventory, profile or invoice results page |
| Ctrl+K / Command+K | Find permitted pages/actions; Up/Down and Enter choose |
| Alt+K / F1 | Open this shortcut guide |
| Alt+1 … Alt+0 | Overview, Billing, Inventory, Purchases, Café, Profiles, Reports, Planning, WhatsApp orders, WhatsApp updates |
| Alt+S / Alt+T | Settings / staff |
| Alt+N / Alt+M | Focus navigation / workspace |
| Alt+L | Focus the transaction location selector |
| Escape | Close suggestions, a dialog or mobile navigation |
| Tab / Shift+Tab | Next / previous control; confined to an open dialog |

Function keys may require Fn. Browser/extension shortcuts can conflict; Tab remains available. Mac supports Command+K and Command+Enter. Page navigation follows staff permissions and stays blocked while a dialog is open.

## Bill at the counter

1. F2 opens the scan field. Scan an exact barcode/SKU and Enter adds one unit, clears the field and keeps focus for the next scan. Keyboard-emulating scanners with an Enter suffix work here. Unknown/ambiguous codes are rejected; they never create a product or select an approximate match.
2. For name search, type then Down to enter the results. Arrows/Home/End choose a card; Enter/Space adds it. Enter adds a unique name match or focuses the first of several results. Page Up/Down browses the full list, 60 products at a time.
3. F6 changes the last touched item's quantity; Ctrl+Up/Down chooses another row. Zero removes a row; invalid quantities or unavailable stock are rejected. Case buttons add the configured pack quantity. F5 finds a customer; adding a new profile from this dialog attaches it to the bill. Enter in the mobile field also looks up a profile. F7 sets the discount.
4. F8 opens checkout. Alt+C/U/D/B chooses the payment and selects the received amount. Enter moves forward through supply state/reference; Ctrl+Enter saves explicitly. Wait for the saved receipt. UPI/card choices record a payment; they do not charge the customer.
5. F10 opens Windows/browser printing. F2 closes the receipt and returns to an empty next bill. Customer, discount and selling tier reset; transaction location and the café menu filter are retained. Escape also returns to scanning. F9 finds previous invoices.

F2 retains an unfinished basket. Clear bill is a separate action. An unfinished basket, its customer, tier and discount survive a tab reload; review current prices/stock before saving. Held Enter does not repeatedly add items or submit forms. Save/cancel controls stay guarded while a financial save is pending.

## Receive purchases without the mouse

Alt+4 opens Purchases; F4 starts receipt. Choose the supplier, Enter through location and the required supplier invoice reference, then scan/type the first product. Enter chooses an exact code or the highlighted name result. Up/Down chooses suggestions. F3 focuses a product search from elsewhere in the form.

Enter moves from product to quantity to cost. Alt+C in the row sets its configured case quantity; fractional quantities remain available for ingredients. Enter after cost starts the next row, ready for another scan. Shift+Enter goes back. Alt+A adds/focuses an unused row and Alt+P/F8 selects amount paid. Choose the payment with the native select; Ctrl+Enter saves after review. A blank trailing row is ignored; typed but unselected products block saving. Purchase orders and their receipt forms use the same product entry.

## Profiles, inventory and other pages

Alt+3/Alt+6 opens inventory/profiles; F3 searches. Down or Enter moves into the first record action. Up/Down moves to the corresponding action on another row; Home/End chooses the first/last row. Enter opens the action. Page Up/Down browses 100 records at a time. F9 history has the same paging controls and searchable full history. Purchases shows its latest 100 records with F9 for older records.

F4 starts the primary form on inventory, purchases, café menu, profiles, reports, planning and permitted staff/WhatsApp pages. Ctrl+K also finds actions such as Add customer or Transfer stock. Enter/Shift+Enter traverses single-line fields; textarea Enter keeps its normal newline. Tab reaches buttons, checkboxes, files and other controls. Enter/Space activates native buttons. Dialogs start on the first editable field and restore the opener when closed. Background redraws preserve field focus/selection.

Left/Right or Home/End changes view/category tabs. Focus is outlined clearly; the first Tab link skips navigation. On a small screen, Alt+N opens navigation; Escape closes it and returns to Menu. Ctrl+K stays available.

## Retire the deleted review connection

As owner, Alt+S opens Settings. Tab to Server permanently removed?, Enter, type RETIRED and Ctrl+Enter. The PC makes a local backup, removes the old address, pauses delivery and keeps local records/pending changes. Reconcile all PCs with the saved private server backup before folder exchange.
