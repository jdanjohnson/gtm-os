---
id: b2b-emailing
name: B2B Emailing
channel: email
description: Short, buyer-fit B2B cold email that solves a visible workflow problem and books a meeting with someone who can actually buy.
---

# B2B Emailing

Use this play when the B2B segment is clear, the buyer can actually move the deal, and the next step is "send short, relevant emails." It pairs a real why-now trigger with 2–3 sentences that name the work being removed, then runs a 3–4 touch cadence. The goal is replies and meetings from the right title — not vanity opens or polite curiosity from analysts.

## ICP

- B2B SaaS sending to another B2B SaaS
- List has already been through `b2b-prospecting` (or equivalent) — buyer fit and account fit are explicit
- Every row has: company, domain, buyer name + senior title, verified email, one-line context, one why-now trigger (or strong ICP fit)
- Sending infrastructure exists: dedicated sending domain, SPF/DKIM/DMARC configured, warmed inboxes
- Bad fit: lists where the named contact is a junior title, lists without verified emails, fresh sending domain with no warm-up

Primary buyers: Head of RevOps, Head of SalesOps, Head of GTM Engineering, Salesforce Admin (when they own the workflow).

## Hypothesis

A 2–3 sentence cold email tied to a real why-now trigger and aimed at a senior buyer will produce a reply rate ≥ 2% and a meeting rate ≥ 0.5% — measured per inbox, per week. Polite replies from junior titles do not count as positive.

## Sequence

1. Pull the approved list from prospecting/enrichment. Confirm every row has a senior buyer + verified email. Reject rows that don't.
2. Pick the pattern based on the strongest signal:
   - **Trigger-based opener** when the account has a live signal (hiring, funding, CRM migration).
   - **Observation + relief** when one visible fact already implies the pain.
   - **Credibility-first** when the sale needs trust before a direct ask.
3. Write a 2–4 word subject line. Use `{company_name}` or the trigger directly. No clickbait, no caps.
4. Write the body in 2–3 sentences: name the work being removed, name one specific result with a number when available, end with a small CTA. Stay under ~50 words.
5. Personalize only with fields you actually have: company name, buyer name, trigger, one real business observation. Never fake flattery or invent observations.
6. Generate the campaign via `GOOGLEDOCS_CREATE_DOC` (for review) or push directly into the sequencer via the relevant Composio action (e.g. `APOLLO_CREATE_EMAIL_SEQUENCE`, `INSTANTLY_ADD_LEADS_TO_CAMPAIGN`).
7. Call `request_approval` with the full campaign + first 20 personalized rows before any send. Operator does not send without human approval.
8. After approval, send first touch. Follow up 3 times max — each follow-up adds new information, never repeats the first email.
9. After the cadence completes, pull metrics: opens, replies, meetings booked. Save a one-paragraph memory with: segment, count, pattern used, results, decisions for next iteration.
10. If reply rate < 0.5% with normal opens: change segment + buyer, then rewrite. If open rate < 40%: check deliverability and data quality first.

## Success criteria

- Reply rate ≥ 2% from senior buyers (junior replies excluded).
- Meeting-booked rate ≥ 0.5% per 100 sends.
- Open rate ≥ 40% (deliverability healthy).
- Every send had a verified email, named senior buyer, and one trigger or specific observation.
- Quality gates that fail the play even if numbers look ok:
  - opens are high but replies come from junior titles only
  - reply rate is high but no meetings book (wrong buyer)
  - personalization is invented or generic
  - sending volume scaled past warm-up ceiling
  - follow-ups repeat the first email with no new information
