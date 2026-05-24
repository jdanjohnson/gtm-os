---
id: local-emailing
name: Local SMB Emailing
channel: email
description: Helpful-offer-first local SMB cold email aimed at the owner, written to start a real conversation rather than push a demo.
---

# Local SMB Emailing

Use this play when selling to local businesses and the list is clear enough to send short, relevant emails. The goal is not a demo ask. The goal is to give the business a reason to respond before the full sales conversation starts — by leading with something useful, naming a concrete observation, and keeping the message under 50 words.

## ICP

- Approved local SMB list (via `local-prospecting`) with owner identified
- Verified email on every row
- Sending infrastructure: dedicated `.com` sending domain, SPF/DKIM/DMARC configured, warmed inboxes (≤50 sends/inbox/day for first ramp)
- Bad fit: lists where the named contact is front desk, unverified emails, fresh sending domain with no warm-up

Primary buyer: the owner. Move away from the owner only when there is a clear operator or marketing lead who can actually approve spend.

## Hypothesis

A 2–3 sentence helpful-offer-first cold email tied to a real business observation and aimed at the owner will produce a reply rate ≥ 3% and a meeting rate ≥ 1% — measured per inbox, per week. Polite replies from front desk do not count as positive.

## Sequence

1. Pull the approved list. Confirm every row has a named owner + verified email.
2. Pick the helpful-offer pattern based on the segment:
   - Offer a useful artifact (e.g. shoot a TikTok of the business, feature in local news, free sample, free local insight).
   - Ask a concrete business question (e.g. catering pricing, booking window) that starts a real exchange.
   - Avoid openers like "can I book time," "want a demo," "we are the leading platform."
3. Write a personalized 2–4 word subject line. Use the business name or the neighborhood directly.
4. Write the body in 2–3 sentences:
   - Line 1: one specific observation (a real fact about the business — not flattery).
   - Line 2: one offer that helps them.
   - Line 3: one small CTA.
5. Personalize only with fields you actually have: business name, neighborhood/city, category, website quality, ratings/review context, owner name. Never fake flattery or invent observations.
6. Generate the campaign via `GOOGLEDOCS_CREATE_DOC` (for review) or push directly into the sequencer via the relevant Composio action.
7. Call `request_approval` with the full campaign + first 20 personalized rows before any send.
8. After approval, send first touch. Follow up max 3 times — each follow-up adds new information.
9. Pull metrics: opens, replies, meetings booked. Save a one-paragraph memory: segment, count, pattern used, results, decisions for next iteration.
10. If reply rate < 1% with normal opens: change segment + offer, then rewrite. If open rate < 40%: check deliverability and data quality first.

## Success criteria

- Reply rate ≥ 3% from owners (front-desk replies excluded).
- Meeting-booked rate ≥ 1% per 100 sends.
- Open rate ≥ 40%.
- Every send had a verified email, named owner, and one specific observation.
- Quality gates that fail the play even if numbers look ok:
  - replies come from front-desk staff, not the owner
  - personalization is invented or generic
  - subject line is corporate / cold-template feel
  - the email leads with "demo" or "book time"
  - sending volume scaled past warm-up ceiling
