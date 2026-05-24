---
id: local-prospecting
name: Local SMB Prospecting
channel: multi
description: Build a clean local-business prospect list with the owner identified, normalized data, and approval before any spend.
---

# Local SMB Prospecting

Use this play when selling to local businesses (restaurants, salons, med spas, HVAC, dental practices, etc.). The goal is not "run a search." It is to turn a rough ICP into a list that is clean enough to route into a CRM or outbound workflow without a human cleanup project later — with the owner identified, not the front desk.

## ICP

- Local businesses (single-location or small multi-location) in a defined geography + category
- Active web presence (working website, recent reviews)
- A real owner or operator buying path exists
- Visible conversion path (booking flow, contact form, working phone)
- Bad fit: chain or franchise locations when the offer is for independents, businesses with no online footprint, segments where the owner cannot be reached

Primary buyer: **the owner**.

Secondary buyers: general manager or marketing director — only when they clearly own the budget and the day-to-day decision.

Junior contacts (front-desk manager, receptionist, social coordinator) are routing context, not buyers. A row with only a front-desk email is not outbound-ready.

## Hypothesis

A focused list of `~200` ICP-fit local businesses in one geography + category, with the owner identified on every row and one usable contact path (phone or email), will outperform a 5,000-row export of front-desk contacts, measured by booked discovery calls per 100 contacts touched.

## Sequence

1. Restate the ICP in one plain-English sentence (e.g. "Owner-operated roofing companies in Texas with a working website and visible phone number").
2. Pull the broad set from **Openmart** (default for local SMB) via the Openmart Composio actions — start with the search endpoint, not the decision-maker endpoint.
3. Inspect the first page. Tighten by category, location count, website presence, review quality. Remove obvious junk before going deeper.
4. Apply primary filters: location count, has website, Google review rating, technology signals if relevant.
5. For each promising row, find the owner via Openmart's decision-maker endpoint. If only a junior contact exists, keep the row but reroute upward — preserve the junior note as context.
6. Approve only the rows worth working. Reject reasons (capture in the row): no active web presence, no plausible decision-maker, obvious franchise when offer is for independents, already an unqualified row.
7. Preserve per-row context: business name, address, neighborhood, category, owner name, phone, email, website, review rating, source, `source_query`, one-line outreach hook.
8. Save the approved list via `GOOGLESHEETS_BATCH_UPDATE` or push to CRM. Keep the `source_query` field on every row.
9. Save a one-paragraph memory: segment, count, owner-identification rate, geographies covered, decisions made.
10. Hand off to `local-enriching` (if owner data needs verification) or directly to `local-emailing` / `local-cold-calling`.

## Success criteria

- Every approved row has: business name, category, location, owner name, at least one verified contact path.
- Junior-only rows are rerouted, not approved.
- `source_query` preserved on every row.
- Outcome metric: discovery calls booked per 100 contacts touched — threshold `<set after baseline>`.
- Quality gates that fail the play even if numbers look ok:
  - majority of approved rows have a front-desk contact as the named owner
  - franchise locations slip into a list scoped to independents
  - phone or email never gets verified
  - rows missing a one-line outreach hook
  - reviews/website check skipped (junk businesses enter the list)
