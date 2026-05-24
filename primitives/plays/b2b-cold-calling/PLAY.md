---
id: b2b-cold-calling
name: B2B Cold Calling
channel: cold-call
description: Verify, hook, and book — a 3-step B2B cold-call loop aimed at the senior buyer who can actually move the deal.
---

# B2B Cold Calling

Use this play when the list is clean enough to call and the B2B segment is specific enough that a short phone conversation can create urgency. The goal of the call is not to fully sell. The goal is to verify the prospect is qualified, show enough relevance to earn interest, and book the meeting on the phone.

## ICP

- Approved B2B account list (via `b2b-prospecting` + `b2b-enriching`)
- Phones verified, senior buyer named on every row
- Pain hypothesis exists for the segment (e.g. "RevOps drowning in bounced emails")
- Call windows match buyer geography (8am–6pm local, Tue–Wed best)
- Bad fit: junior-title-only lists, unverified phones, accounts with no clear pain hypothesis

Default buyers: Head of RevOps, Head of SalesOps, Head of GTM Engineering, Salesforce Admin (when they own the workflow).

## Hypothesis

A 3-step call (credibility → value → meeting) aimed at a senior buyer with a verified phone and a real pain hook will book meetings at ≥ 5% per qualified conversation. Polite calls with analysts do not count as meetings booked.

## Sequence

1. Pull the approved + enriched row set. Confirm each row has: verified phone, senior buyer, pain hypothesis, one-line company context.
2. Pre-call prep (60s per row): check news if relevant, check LinkedIn, open the CRM page, confirm the buyer is still in role.
3. **Step 1 — Build credibility** (≈ 8–12 seconds): conviction in voice, straight-to-the-point delivery, clear reason for the call. Template: `Hi {name}, this is {rep} from {company}. Quick 30 seconds to explain why I'm calling?`
4. **Step 2 — Build value**: name the segment-specific pain, give one number-backed proof point, ask a short discovery question. Pattern: hook → value → question.
   - Hook: `I talk to RevOps leads drowning in bounced emails and stale contacts.`
   - Value: `We push phone-verified contacts plus intent scores into Salesforce, cutting list-build time by 10 hours a week.`
   - Discovery: `How are you handling contact accuracy today?`
5. **Step 3 — Book the meeting**: define the next step, lock day + time, send the calendar invite, get acceptance on the phone. Template: `Worth a 15-minute compare? I'm free Tuesday at 10:00 or Wednesday at 3:00 PT.`
6. Handle objections with `A-R-P` (acknowledge, re-frame, permission). Maintain an objection library: "send me an email," "already have ZoomInfo," "no budget," "not interested."
7. Follow-up cadence: max 6 attempts per prospect across 14 days. Each follow-up adds new information (not "just checking in"). Voicemail pattern: reference context → add new value → re-ask for meeting.
8. Gatekeeper handling: ask confidently for the target by name; if questioned, give brief value for the target's department; if blocked, politely ask for the best time or voicemail. Respect beats deception.
9. Log every call outcome to CRM via `HUBSPOT_CREATE_NOTE` or equivalent: who you reached, what they said, next step, scheduled meeting datetime.
10. Save a one-paragraph memory summarizing: calls made, qualified conversations, meetings booked, objections that hit hardest, segment-specific phrases worth keeping.

## Success criteria

- Connection rate ≥ 15% on verified-phone rows.
- Qualified conversation rate ≥ 30% of connections.
- Meeting-booked rate ≥ 5% per qualified conversation.
- Show rate ≥ 70% on booked meetings.
- Every call logged with outcome + next step.
- Quality gates that fail the play even if numbers look ok:
  - meetings booked are with junior titles (analysts, SDR managers)
  - "send me an email" is treated as a soft yes instead of a true objection
  - voicemails repeat the same message across follow-ups
  - calls happen outside the verified business hours window
  - the rep does not lock the day + time on the phone
