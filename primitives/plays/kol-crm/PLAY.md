---
id: kol-crm
name: KOL CRM
channel: multi
description: Track influencer sourcing, outreach, pricing, owner, and status through a simple six-state partnership pipeline.
---

# KOL CRM

Use this play when running a creator or influencer partnership motion and you need a lightweight, inspectable CRM — not when doing local SMB or B2B outbound. The outcome is one row per influencer, an explicit status that tells you the next action, and a pipeline that survives more than one campaign without becoming a mystery spreadsheet.

This is a tracking play, not a list-building play. Sourcing happens upstream of the CRM. The CRM is where partnerships move from "saw them on Twitter" to `Partnered` (or `Closed`).

## ICP

- YouTube and Twitter (X) creators as the v1 platforms; expand carefully
- Creators with a niche that maps to your product or audience — one niche per working batch, not "all tech"
- Reach matched to the campaign (micro, mid, or top-tier) and to the budget
- A reachable contact path: business email, DM-open profile, manager email, or business inquiries link
- Bad fit: software-to-software B2B prospecting, local SMB outbound, anonymous accounts with no contact path, creators whose niche doesn't overlap with your audience

## Hypothesis

A simple six-state pipeline (`Not Contacted → Contacted → Replied → In Negotiation → Partnered → Closed`) with an explicit owner, an updated `last_contact` date, and an optional `pricing` field will keep influencer partnerships moving without automation, and will surface the rows that need the next action this week.

## Sequence

1. Source influencers off-CRM — channel scraping, manual research, recommendations, prior partner alumni, or a creator marketplace.
2. Qualify by niche, reach, audience fit, and contactability before importing. Don't dump every creator you saw into the pipeline.
3. Import the qualified set via CSV using the influencer schema fields: `name`, `handle`, `platform`, `followers`, `niche`, `owner`, `status`, `pricing`, `last_contact`. Or add records manually.
4. Set every new record to `Not Contacted` and assign an explicit `owner`. No empty owner fields.
5. Send the first outreach (DM via Twitter, email via business address, or manager email). Move the record to `Contacted` and update `last_contact`.
6. When the influencer replies, move to `Replied`. This is the first high-signal state — prioritize.
7. Open the pricing and terms conversation. Move to `In Negotiation`. Capture the quoted rate in `pricing` once a real number exists.
8. Update `last_contact` every time outreach or negotiation actually moves. Never let the date go stale on an active row.
9. When the collaboration is live or agreed, move to `Partnered`. When the opportunity is done, paused, or not moving forward, move to `Closed`. `Closed` is terminal for v1.
10. Use the high-signal views weekly: all influencers, needs first outreach, replied, has pricing, in negotiation, partnered.
11. Log outcome notes against the row — content delivered, performance summary, future-collab flag — so the next campaign can reuse the relationship instead of starting cold.
12. Refresh sourcing on a cadence. A KOL CRM that hasn't seen a new `Not Contacted` row in months is just a graveyard.

## Success criteria

- Every record has the required fields: `name`, `platform`, `owner`, `status`. Plus `handle` and `niche` for usable filtering.
- `status` is always explicit and never inferred from empty fields.
- `last_contact` actually changes when outreach or negotiation moves.
- High-signal views are small enough to act on this week (`Replied`, `In Negotiation`, `needs first outreach`).
- Track reply rate, negotiation rate, partnered rate, and repeat-partner rate per niche and platform — thresholds `<set after baseline>`.
- Quality gates that fail the play even if numbers look ok:
  - records with no owner
  - `status` inferred from blank fields instead of set explicitly
  - `pricing` treated as required before negotiation starts
  - `Closed` rows being reopened without a new outreach record
  - status names quietly drift away from the six canonical states
  - the pipeline has no new `Not Contacted` rows in months
