---
id: b2b-enriching
name: B2B Enriching
channel: multi
description: Enrich approved B2B rows with the right senior buyer, a usable contact path, and enough context to start outreach without going cold.
---

# B2B Enriching

Use this play after a B2B list has been approved upstream (typically via `b2b-prospecting`). The goal is not to enrich every possible person on the account — it is to confirm the right buyer, find a usable contact path, preserve enough context for outbound, and avoid pushing weak rows downstream.

## ICP

- Approved B2B account list with company, domain, ICP fit, and at least a contact placeholder
- A real buyer authority pattern exists (e.g. RevOps owns the KPI for a data quality offer)
- The next motion is email, calling, LinkedIn, or CRM sync — enrichment must support that motion
- Bad fit: unapproved raw exports, accounts where no plausible senior buyer exists, rows where the next motion is not yet decided

Active buyers (high-priority enrichment targets):

- Head of Revenue Operations
- Head of Sales Operations
- VP Revenue Operations
- Head of GTM Engineering
- Salesforce Administrator (when they own the workflow)

Junior or partial-authority contacts (keep as context, not as the primary owner):

- RevOps analyst, SalesOps analyst, SDR manager

## Hypothesis

Enriching only approved rows with the senior buyer's verified email + phone + LinkedIn + one-line company context will lift downstream meeting rate by ≥ 30% versus enriching the full export, because the wrong-buyer noise floor is removed before sequencing.

## Sequence

1. Pull the approved row set. Confirm every row has a company + domain + plausible senior buyer title (or escalation path).
2. For each row, find the senior buyer name and contact path. Default sources: Apollo (`APOLLO_SEARCH_PEOPLE`, `APOLLO_GET_PERSON_DETAILS`), LinkedIn Sales Nav, Crunchbase. Only layer a second source when the first has a known gap for the segment.
3. Capture the high-priority fields per row: contact name, title, email, phone, LinkedIn profile URL, what the company does (one line), company type, business size, one-line outreach hook, verification status, buyer-fit note.
4. If only a junior contact exists, keep the row alive and reroute upward — preserve the junior note as context, not as the active owner. Do not discard the account.
5. Verify every email via `ZEROBOUNCE_VALIDATE_EMAIL` (or equivalent). Keep the verification status visible. If email is weak, mark the row's preferred channel as call or LinkedIn.
6. Score phone quality. If phone is weak, do not let the row enter a call-first cadence.
7. Tag the next motion per row: email-first, call-first, LinkedIn-first, or CRM-sync-only.
8. Preserve workflow fields: `source_query`, fit score, routing status, rejection reason, source IDs. Without these the row looks useful for one day and confusing forever.
9. Save a one-paragraph memory summarizing: total approved, total enriched, buyer-title distribution, verification pass rate, channel mix.
10. Hand off cleanly: email-first → `b2b-emailing`, call-first → `b2b-cold-calling`, hybrid → both with channel field set.

## Success criteria

- Every enriched row has a named senior buyer (not junior).
- Email verification rate ≥ 90% on rows tagged email-first.
- Phone quality scored on every row tagged call-first.
- Per-row context line + buyer-fit note present.
- Workflow fields (`source_query`, fit score, routing status) preserved.
- Quality gates that fail the play even if numbers look ok:
  - enriched rows still default to junior contacts as the active owner
  - emails enter the sequencer unverified
  - `source_query` is lost during enrichment
  - rows are marked outbound-ready without a one-line outreach hook
  - reverification is skipped on stale rows older than 90 days
