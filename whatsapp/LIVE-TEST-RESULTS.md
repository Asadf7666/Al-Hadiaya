# WhatsApp live test results — 6 October 2026

Tests completed at approximately 13:44 Asia/Riyadh (10:44 UTC). All live sends were authorized by the owner and addressed to the single Meta-verified owner test recipient. Full provider message IDs and the recipient number remain in private server test logs, not in this report.

| Test | Actual result | Scope / limitation |
|---|---|---|
| Initial Hello World | Owner confirmed receipt | First connection test |
| New utility Hello World | Meta accepted | New message ID returned; delivery not yet independently confirmed |
| Plain marketing text | Meta accepted | Approved Meta Jasper's Market sample; not an Al Hidaya campaign |
| Image with static URL button | Meta accepted | Uploaded a small generated test PNG; direct provider-format test |
| Two-card media carousel | Meta accepted | Approved Meta sample; direct provider-format test |
| 12 business-case parameter tests | All 12 Meta accepted | Used approved three-parameter order-confirmation sample with TEST ONLY parameters |
| 12 custom-template application sends | All rejected, error 132001 | Al Hidaya invoice/payment/internal templates remained PENDING |
| Custom marketing campaign | Application blocked before send | Correctly requires an approved marketing template |
| Linked WhatsApp catalogues | Empty | No Commerce catalogue is connected |
| Owned Commerce catalogue listing | Rejected, error 200 | Token lacks business_management permission |
| Catalogue interactive message | Rejected, error 131009 | No valid connected catalogue; no product list was delivered |
| Signed webhook / STOP processing | Automated and HTTP tests passed | Live Meta subscription awaits the app secret and verification token |
| Hosted app / downloads | Passed | UI, protected credential fields, policies and download checksums verified |

The 12 business cases covered invoice receipt, customer payment receipt, customer/supplier internal payment updates, sales, purchase, expense, stock transfer, invoice reversal, low stock and daily summary. The sample template's fixed wording remains Meta's sample order-confirmation wording; TEST ONLY parameters distinguish each case. These sends verify parameter transport, not approval or delivery of the actual Al Hidaya template wording.

Meta returned account_review_status APPROVED for the test WABA, but business_verification_status pending_submission. Business marketing onboarding returned NOT_STARTED. These statuses do not establish production readiness and do not explain every template-review delay.

Financial transactions and stock changes for message generation used a temporary shop database. No hosted business invoices or stock were changed. Only test notification logs were added to the hosted notification screen. Production automation remains paused and there are no configured staff recipients.

Version 0.5's owner-approved campaign UI supported approved body-only templates with three text parameters. Image/button/carousel samples were exercised directly against Meta's API; this test does not add media campaign composition to the app UI. PDF invoice delivery, WhatsApp Channels, app broadcast-list posting, and group messaging are not implemented.

## Remaining checks

1. Meta must approve the four Al Hidaya templates. Refresh template status and retest those exact names/language after approval.
2. Configure the protected webhook app secret and verification token, subscribe the public callback and messages field, then test live delivered/read receipts and a STOP reply.
3. Authorize Commerce catalogue management, connect an owned catalogue with accurate retailer IDs, prices and product photos, then test actual product/card/cart messages. Do not publish the entire unpriced starter inventory as sellable Meta products.
4. Confirm receipt of the 16 new sample messages. An API message ID proves acceptance, not delivery.
5. Register the intended production business number and replace the temporary token with suitable production credentials before unattended operation.


## Version 0.6 and corrected branding

At approximately 14:13 Asia/Riyadh (11:13 UTC), Meta accepted a direct image message using the new Al Hadiya Traders artwork, with cold drinks, mint mojito and iced coffee. This replaces the flat PNG test fixture. Recipient confirmation of this specific photo remains pending; acceptance does not establish delivery.

Five correctly branded templates were submitted and returned PENDING: `al_hadiya_invoice`, `al_hadiya_payment`, `al_hadiya_internal`, `al_hadiya_offer`, and the IMAGE-header `al_hadiya_offer_image`. The previous `al_hidaya_*` submissions remain historical provider records. Hosted sender settings now reference the corrected utility names. Production automation remains paused.

Version 0.6 adds image upload, image-template campaign draft/preview/approval and a separate public web photo catalogue with baskets and contact-consented order requests. Chromium verified image upload and campaign preview, order submission and a subsequent basket, using an isolated fixture. Hosted verification passed for the image library, campaign form, public banner, mobile rendering, and installer/source checksums. There are no live published products yet: actual product photographs and confirmed prices are required. Native WhatsApp Commerce catalogue permissions/linkage are still pending. PDF invoice delivery, carousels in app campaigns, Channels and group messaging remain unavailable.

## 2026-10-06 — 0.8 itemised updates, daily summary and replenishment

The owner confirmed receipt of both previous 0.7 Purchase and Sale internal test messages. Version 0.8 adds detailed invoice lines, actual location stock deltas, profile notifications, planning/purchase-order activity, daily summaries and stock-condition alerts. These workflows passed isolated automated/browser tests; they do not imply provider delivery.

The authorised new live-format test used a separate temporary shop for all sample financial/stock records, with the saved sender credential loaded only at runtime. The first new Purchase message was rejected by Meta with **HTTP 401 / OAuth code 190**. Testing stopped immediately; Sale/Profile/Procurement/Daily messages were **not sent**. No real business invoices, stock or ledger balances were modified. A private test record is stored on the server, and the failed attempt is visible in its notification history.

A fresh valid access token must be entered directly in **WhatsApp updates → Configure sender → Access token**. Native catalogue/webhook activation and production template approval remain prerequisites; saving a token alone does not establish native ordering or scheduled production delivery. No verification, webhook delivery or new message receipt is claimed.

### Credential refresh and recipient confirmation

After the owner supplied a refreshed credential, Meta accepted all five isolated 0.8 test messages: Purchase, Sale, Profile, Procurement and Daily summary / stock planning. **The owner confirmed all five were received**, then reported that the formatting was difficult to read. This confirms delivery for those session-message tests only. All six branded templates still returned PENDING; no linked Commerce catalogue or saved webhook secret was found. The daily summary remains configured for 20:00 Asia/Kolkata (17:30 Asia/Riyadh).

Version 0.8.1 changes presentation to bold WhatsApp headings, paragraph-separated sections, short item/quantity lines, rupee amounts, distinct payment/account details and stock before/after balances. Daily detail pages are bounded to 2,200 characters. These layout changes preserve the underlying financial and inventory calculations.

### Revised 0.8.1 examples

Meta accepted six new session-message examples after the layout update: Purchase, Sale, Profile, Procurement, Daily summary / stock planning, and a separate Stock alert. Each message uses an isolated financial fixture and a clear demo label. Receipt/readability of this revised set was not yet confirmed when this report was written. The preceding five-message set was confirmed received by the owner.

The 0.8.1 hosted app passed browser checks without JavaScript errors; all 89 automated tests passed. The hosted installer and source download SHA-256 hashes were verified. Windows installer execution remains unverified. No native Commerce ordering, webhook receipt or outside-window template delivery was confirmed by these tests.
