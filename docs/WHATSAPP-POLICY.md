# WhatsApp policy mapping — 6 October 2026

This review covers the policies relevant to this shop's Cloud API messaging, catalogue and customer data. It is not a review of unrelated Meta products or a guarantee against account enforcement.

## Official sources reviewed

- [Business Messaging Policy](https://business.whatsapp.com/policy): opt-in/out, service windows, approved templates, human escalation, restricted goods and data use.
- [WhatsApp Business Platform Terms](https://www.whatsapp.com/legal/WhatsApp-Terms-for-WhatsApp-Business-Platform): authorized business use, responsibilities, enforcement and data practices.
- [Commerce Policies](https://www.facebook.com/policies_center/commerce): prohibited/restricted products, genuine listings and rights.
- [Messaging Guidelines](https://www.whatsapp.com/legal/messaging-guidelines): spam, fraud, adversarial automation and unofficial clients.
- [Developer Platform Terms](https://developers.facebook.com/terms/): privacy, security, access, deletion and data-use responsibilities.
- [Data Processing Terms](https://www.whatsapp.com/legal/business-data-processing-terms): customer-data responsibilities, security and incorporated transfer terms.
- [Intellectual Property Policy](https://www.whatsapp.com/legal/ip-policy): rights in business names, logos, photographs and content.

These public pages were retrieved during this review. The additional [Meta Terms for WhatsApp Business Platform](https://www.facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform), linked by the WhatsApp terms, returned an unreadable Facebook shell, including an English-locale retry. Its full text has not been reviewed here; review it in Meta before production. Applicable Indian privacy, consumer, food, tax and marketing law also needs business/accountant review.

## Controls and responsibilities

| Policy requirement | Enforced app control | Owner/staff responsibility |
| --- | --- | --- |
| Accurate authorized identity | Explicit WABA/sender IDs; authenticated staff | Keep Meta profile/support details truthful; complete verification; do not impersonate brands |
| Opt-in before business outreach | Separate receipts/offers consent; evidence note for new consent or changed mobile; consent rechecked before sending | Record how/when/purpose of agreement; a phone number or order is not marketing consent |
| Respect all opt-outs | Signed STOP/UNSUBSCRIBE/OPT OUT revokes consent and cancels pending messages; staff can revoke outside chat; START does not re-enrol marketing | Act on in-store, email and telephone opt-outs too; no bought or scraped lists |
| Approved templates used for their purpose | APPROVED, supported templates checked within 24 hours; utility versus marketing category enforced | Use approved branded wording for its designated purpose; no offers hidden in receipts |
| Genuine 24-hour window | Authenticated inbound timestamps open the service window; direct replies blocked outside it | Never manufacture a reply or timestamp to bypass the rule |
| Human escalation | HELP/HUMAN/AGENT/SUPPORT provides the configured shop support route | Staff must actually answer; keep phone/address accurate |
| Avoid unwanted/repetitive contact | Owner preview/approval, deduplication, cancellation, send pacing and one accepted offer per recipient/day | Keep offers relevant, cancel stale promotions and monitor quality/complaints |
| Permitted commerce | Food/non-alcoholic drink scope, regulated-word checks, explicit publication review; changed items require review; policy issues block cart confirmation | Check actual goods/photos, legality, recalls, claims and image/brand rights; keyword checks cannot establish all of these |
| Protect customer data and identifiers | Staff access, signed webhooks, separate secret files and sensitive-identifier/credential pattern checks | Protect private backups; handle verified data requests; never send complete card/account/Aadhaar identifiers, OTPs or credentials |
| Respect restrictions | Account review and number-quality checks cached for at most ten minutes; unknown status blocks sends; REJECTED/RED and account/credential errors pause sending | Resolve review in Meta; do not evade restrictions with replacement accounts or unofficial clients |
| Report delivery honestly | Accepted differs from delivered/read; signed receipt updates; uncertain sends do not auto-retry | Check uncertain attempts before manual resend |

Pacing is an app precaution, not a safe threshold published by Meta: batches contain at most three different recipients, are at least ten seconds apart, and attempts to the same recipient are at least thirty seconds apart. Promotional offers are capped at one accepted offer per recipient per 24 hours. These limits do not guarantee acceptable use.

The messaging policy's regulated-vertical exceptions depend on country, age, licences and approved use cases. This app does not implement those exceptions. Its WhatsApp catalogue excludes those verticals, including alcohol, tobacco and medical products. A retail licence alone is not permission for Meta commerce.

## Incident and activation

The notice names an acceptable-use breach without identifying the activity. Both business and test WABAs returned REJECTED review status; the test number's GREEN quality does not override it. A review is pending. Recorded application logs over the inspected 48 hours contain 30 provider acceptances and no HTTP 429 records. Nine accepted-message rows have creation times within one minute; these are queue creation timestamps, not actual send timestamps, so they do not establish a send rate. These records cannot establish or exclude a cause or cover unrecorded activity.

Hosted sending is off. Use fixtures without outbound requests while restricted. Before production: restore access; rotate exposed secrets; review the additional Meta terms; verify business, support, privacy/deletion details; approve branded templates; subscribe the signed public HTTPS messages webhook; link the owned catalogue; and validate one genuine opted-in cart, delivery status and STOP. Keep financial operations independent of WhatsApp availability.
