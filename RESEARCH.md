# Product and open-source research

Reviewed on 5 October 2026. These are feature/design references; no code from the projects below was incorporated into this original Python/SQLite pilot. Marketing claims and upstream functionality do not prove this app's functionality.

## Indian billing references

- [Retail Daddy](https://retaildaddy.in/retail-daddy-billing-software): fast POS billing, barcode-led checkout, inventory and Indian GST workflows. The `.com` address was inaccessible; the correct `.in` product materials and search-indexed feature information were located. Its page's JavaScript-rendered screens were not fully extractable in this environment, so no claim of copying its exact UI is made.
- [Vyapar POS](https://vyaparapp.in/pos-billing-software): useful comparison for tax-inclusive billing, stock, party credit, suppliers, expense reporting, offline operation and hardware integration. Those flows informed the basic module structure, without reproducing proprietary UI/code.
- [Gofrugal](https://www.gofrugal.com/): combines retail, restaurant and distribution workflows. Warehouse transfers and café recipes should belong to one business system rather than disconnected stock sheets.

## Open-source alternatives

| Project | Relevant strengths | Fit and unresolved work for this shop |
|---|---|---|
| [ERPNext](https://github.com/frappe/erpnext), GPL-3.0 | Broad accounting, stock, purchases, sales and material consumption; self-hostable | Strong candidate for a mature accounting back office. Upstream setup involves a server stack; it is not a simple Windows offline `.exe`. Local disconnected POS and two-location replication must be evaluated for the actual version/add-ons. |
| [Odoo Community](https://github.com/odoo/odoo), LGPL-3.0 core | POS, restaurant and inventory modules, with India localisation options | Server-backed model. Loaded POS sessions can support temporary offline operation; that is different from independent full back offices at both sites. Verify Community/add-on availability and licences per feature. |
| [Open Source Point of Sale](https://github.com/opensourcepos/opensourcepos) | Items/kits, taxes, customers/suppliers, receivings, expenses and reports | PHP/MySQL web app; local hosting possible, but remote disconnected two-PC sync and this café recipe model are not demonstrated as a ready-made solution. Its licence includes attribution/footer requirements; review before reuse. |
| [uniCenta](https://unicenta.com/) | Desktop-oriented retail/hospitality POS with Windows support | Worth a hands-on trial for a till. Current packaging/version support, Karnataka GST, catalogue import and disconnected warehouse/outlet sync need verification; historical mirrors are not a safe source of current binaries. |
| [Posnic](https://github.com/Posnic/POS) | Offline-first local retail/restaurant POS; downloadable desktop packages | Closest architectural reference for an owned Windows POS. Its source is AGPL-3.0-only and bundled components have separate licences including MongoDB SSPL. Published offline evidence is bounded, not proof of every workflow. Indian tax classification and two-address warehouse sync remain to be validated. |

There is no basis to call any of these universally compatible with all POS hardware or every Indian inventory item. For a production system with formal accounts, ERPNext with an evaluated offline POS layer deserves a pilot comparison before committing to long-term maintenance of a custom implementation. The custom application here remains a first pilot of the simpler local workflow, not a replacement for the maturity of those projects.

## GST findings reflected in the implementation

- [PIB: GST reforms 2025](https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=3&NoteId=155151&lang=1&reg=6) describes the aerated-drink 40% rate under reforms effective 22 September 2025. [Official FAQs](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2163560&lang=1&reg=1) explain the changes. Therefore a stale blanket 28% GST + 12% cess default is unsuitable for new beverage invoices. The app leaves catalogue classifications unconfirmed and offers explicit product-level rates; demo rates are illustrative.
- [CBIC invoice particulars](https://cbic-gst.gov.in/gst-invoice-rules.html) and [CBIC sectoral FAQs](https://cbic-gst.gov.in/hindi/sectoral-faq.html) support keeping consecutive invoice series unique per financial year and invoice numbers within 16 characters. Each device uses a distinct series, a financial-year code and a consecutive five-digit suffix. Saved invoice details remain snapshots when business/product settings change.
- Taxes vary with product classification, restaurant status and registration. Configurable calculation and CSV exports are not equivalent to GST portal integration, current-rate certification, ITC eligibility or statutory return filing.

The supplied Al Hidaya sign image informed the black/gold identity, tagline and categories. The image was not embedded as a software logo; the app uses its own text mark.

## WhatsApp automation

Uses the official WhatsApp Business Cloud API template-message endpoint; recipients must opt in. Policy source: https://whatsappbusiness.com/policy/ . API send documentation: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages (documentation fetch rate-limited in this workspace). The app requires an API version configured from the business Meta console rather than guessing a current version. API acceptance and actual delivery are separate; public webhook support is reserved for the future hosted platform.
