---
id: local-cold-calling
name: Local SMB Cold Calling
channel: cold-call
description: Verify, hook, and book — a 3-step local SMB cold-call loop aimed at the owner, with respect for gatekeepers and short follow-ups that add information.
---

# Local SMB Cold Calling

Use this play when the list is clean enough to call and the local SMB segment is specific enough that a short phone conversation can create urgency. The goal of the call is not to fully sell. It is to verify the prospect is qualified, show enough relevance to earn interest, and book the meeting on the phone.

## ICP

- Approved local SMB list (via `local-prospecting` + `local-enriching`)
- Verified phones, owner named on every row
- Pain hypothesis exists for the segment (e.g. "med spa owners want more qualified consults without adding admin work")
- Call windows match buyer geography (typically 8am–6pm local, midweek best)
- Bad fit: front-desk-only lists, unverified phones, accounts with no clear pain hypothesis

Default buyer: the **owner**. Only treat a GM or marketing lead as primary when they clearly control the decision. Treat junior contacts as routing help, not the close path.

## Hypothesis

A 3-step call (credibility → value → meeting) aimed at the owner with a verified phone and a real pain hook will book discovery calls at ≥ 6% per qualified conversation. Polite chats with front desk do not count as meetings booked.

## Sequence

1. Pull the approved + enriched row set. Confirm: verified phone, owner named, pain hypothesis, one-line business context.
2. Pre-call prep (60s per row): check the website, scan Google reviews, check basic business context, open the CRM page.
3. **Step 1 — Build credibility** (≈ 8–12 seconds): conviction in voice, straight-to-the-point delivery, polished wording. Avoid "um," "like," "you know."
   - Opener template: `Hi {name}, this is {rep} from {company}. I'm calling because we help {segment} with {pain}. Quick question for you.`
4. **Step 2 — Build value**: name the segment-specific pain, give one number-backed proof, ask a short discovery question.
   - Hook: `A lot of {category} owners tell me they want more qualified local demand without adding admin work.`
   - Value: `We help local teams get more qualified leads and respond faster without creating extra work for the owner or front desk.`
   - Discovery: `How are you bringing in new {jobs_or_customers} today?`
5. **Step 3 — Book the meeting**: define next step, lock day + time, send the calendar invite, get acceptance on the phone (same day or ≤24 hours ideal).
   - Close: `Worth a 15-minute compare? I'm free Tuesday at 10:00 or Wednesday at 3:00 PT.`
6. Handle objections with `A-R-P` (acknowledge, re-frame, permission). Common rebuttals: "we already have someone," "send me an email," "not interested."
7. Follow-up cadence: max 6 attempts per prospect across 14 days. Each follow-up adds new information (reference last context → add new value → re-ask for meeting). Voicemails follow the same shape.
8. Gatekeeper handling: ask confidently for the owner by name; if questioned, give brief value for the business; if blocked, politely ask for the best time or voicemail. Respect beats deception.
9. Log every call to CRM via `HUBSPOT_CREATE_NOTE` or equivalent: who you reached, what they said, next step, scheduled meeting datetime.
10. Save a one-paragraph memory: calls made, qualified conversations, meetings booked, hardest objections, segment-specific phrases worth keeping.

## Success criteria

- Connection rate ≥ 20% on verified-phone rows.
- Qualified conversation rate ≥ 35% of connections.
- Meeting-booked rate ≥ 6% per qualified conversation.
- Show rate ≥ 70% on booked meetings.
- Every call logged with outcome + next step.
- Quality gates that fail the play even if numbers look ok:
  - meetings booked are with front-desk staff, not the owner
  - "send me an email" is treated as a soft yes
  - voicemails repeat the same message across follow-ups
  - calls happen outside the local business-hours window
  - the rep does not lock the day + time on the phone
  - gatekeeper handled with deception instead of value
