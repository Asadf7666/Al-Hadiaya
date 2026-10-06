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

The application's owner-approved campaign UI currently supports approved body-only templates with three text parameters. Image/button/carousel samples were exercised directly against Meta's API; this test does not add media campaign composition to the app UI. PDF invoice delivery, WhatsApp Channels, app broadcast-list posting, and group messaging are not implemented.

## Remaining checks

1. Meta must approve the four Al Hidaya templates. Refresh template status and retest those exact names/language after approval.
2. Configure the protected webhook app secret and verification token, subscribe the public callback and messages field, then test live delivered/read receipts and a STOP reply.
3. Authorize Commerce catalogue management, connect an owned catalogue with accurate retailer IDs, prices and product photos, then test actual product/card/cart messages. Do not publish the entire unpriced starter inventory as sellable Meta products.
4. Confirm receipt of the 16 new sample messages. An API message ID proves acceptance, not delivery.
5. Register the intended production business number and replace the temporary token with suitable production credentials before unattended operation.
