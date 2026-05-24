---
id: local-enriching
name: Local SMB Enriching
channel: multi
description: Enrich approved local-business rows with the owner, a verified contact path, and enough workflow context to send or call without a cleanup project later.
---

# Local SMB Enriching

Use this play after a local-business list has been approved upstream (typically via `local-prospecting`). The goal is not to enrich everything — it is to filter junk first, enrich only the rows worth working, find the real owner contact path, and preserve enough context that the CRM sync still makes sense later.

## ICP

- Approved local SMB row set with business, category, location, website
- A defined next motion (email, call, LinkedIn, or CRM sync)
- Bad fit: unapproved raw exports, rows with no plausible owner path, rows where the next motion is undecided

Active buyers (high-priority enrichment targets):

- Owner, founder, general manager, marketing director (when they clearly run the budget)

Junior or routing-only contacts:

- Front-desk manager, receptionist, social media coordinator

## Hypothesis

Enriching only approved rows with the owner's verified email + phone + one-line business context will lift downstream meeting rate by ≥ 30% versus enriching the full export, because front-desk noise is removed before sequencing.

## Sequence

1. Pull the approved row set. Confirm every row has business name, category, location, and a website check passed.
2. First-pass filters (cheap signals before spending credits):
   - location count (single vs multi)
   - has website
   - Google review rating
   - technology signals if relevant
   Reject rows that fail obvious fit before enrichment.
3. For each remaining row, find the owner via **Openmart's decision-maker endpoint** (default for local SMB). If `Clay` is the broader workflow, route SMB owner-finding to Openmart inside Clay.
4. Capture per-row high-priority fields: owner name, role/title, phone, email, personal email when available, technology context, one-line business summary.
5. If only a junior contact exists, keep the row alive and reroute upward — preserve the junior note as context, not as the primary owner.
6. Verify every email via `ZEROBOUNCE_VALIDATE_EMAIL`. Keep verification status visible on the row. If email is weak, mark the row's preferred channel as call.
7. If ≥30% of the file fails verification: treat that as a source-quality problem, not normal list loss. Surface to the user before continuing.
8. Score phone quality. If phone is weak, do not let the row enter a call-first cadence.
9. Preserve workflow fields: `source_query`, fit score, routing status, rejection reason, source IDs.
10. Save a one-paragraph memory: total approved, total enriched, owner-identification rate, verification pass rate, channel mix.
11. Hand off: email-first → `local-emailing`, call-first → `local-cold-calling`, hybrid → both with channel field set.

## Success criteria

- Every enriched row has a named owner (not a front-desk contact).
- Email verification rate ≥ 90% on rows tagged email-first.
- Phone scored on every row tagged call-first.
- Workflow fields (`source_query`, fit score, routing status, rejection reason) preserved.
- Quality gates that fail the play even if numbers look ok:
  - enriched rows still default to front-desk as the active owner
  - emails enter the sequencer unverified
  - the file's verification failure rate is high but the run continues without surfacing it
  - rows are marked outbound-ready without a one-line business summary
  - source_query is lost during enrichment
