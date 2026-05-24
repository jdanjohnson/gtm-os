---
id: b2b-prospecting
name: B2B Prospecting
channel: multi
description: Build software-to-software B2B prospect lists targeting the buyer who can actually move the deal.
---

# B2B Prospecting

Use this play when a software company sells to another software company and the next step is "build the company set." The goal is not a giant list. The goal is the right company, the right buyer, a real why-now signal, and a row clean enough to hand off to enrichment, email, or calling without a noisy reply problem later.

## ICP

- Mid-market or early-growth B2B SaaS
- Outbound team already exists and is scaling (roughly 5 → 20+ reps)
- ACV ≥ $5K
- Cares about contact data quality, TAM coverage, or outbound workflow speed
- Bad fit: pre-outbound startups, junior-led ops teams with no budget, accounts where the buyer is not visible

Primary buyers (titles that can actually move the deal):

- Head of Revenue Operations
- Head of Sales Operations
- Head of GTM Engineering
- Salesforce Administrator (when they truly own the workflow + tool decision)

Secondary buyer: Head of Sales when they clearly own the problem and the buying path.

Junior titles (analyst, SDR manager, etc.) are routing context — not the campaign target.

## Hypothesis

A focused list of `~200` ICP-fit accounts with a senior buyer named on every row and one live why-now signal will outperform a 5,000-row export with junior titles and no triggers, measured by qualified meetings booked per 100 contacts touched. Polite replies from junior titles do not count as traction.

## Sequence

1. Restate the ICP in one sentence (company type, segment, buyer, why-now).
2. Pull the broad set from Apollo (default for B2B) via `APOLLO_SEARCH_PEOPLE` or `APOLLO_SEARCH_ORGANIZATIONS`. Only layer a second source (e.g. Crunchbase, LinkedIn Sales Nav) when it clearly improves coverage for a specific segment.
3. Tighten by company fit, buyer fit, and trigger. Remove obvious junk (wrong size, wrong segment, no plausible buyer path).
4. For each row, name the senior buyer explicitly. If only a junior contact exists, reroute to the right title before approving.
5. Tag each row with a why-now trigger when present: hiring, funding, CRM migration, team build-out, outbound ramp, expansion. No trigger = lower priority, not auto-reject.
6. Pressure-test the working set with BANT: Budget (do they already spend on this problem?), Authority (is the named buyer on the decision path?), Needs (is the pain real?), Timing (is there a live reason to move now?).
7. Preserve per-row context: company name, domain, contact name + title, source, source query, trigger note, one-line company summary, one-line outreach hook.
8. Save the list via `GOOGLESHEETS_BATCH_UPDATE` or push directly to the CRM via the appropriate Composio action. Keep a `source_query` field so the row is inspectable later.
9. Save a one-paragraph memory summarizing: segment, count, buyer title distribution, trigger mix, decisions made.
10. Hand off to `b2b-enriching` (if contact paths are weak) or directly to `b2b-emailing` / `b2b-cold-calling` (if the row is already complete).

## Success criteria

- Every approved row has: company, domain, buyer name + senior title, one trigger or clear ICP fit, one-line context.
- Junior-only rows are rerouted, not approved.
- Working list passes BANT pressure-test before sequencing.
- Outcome metric: qualified meetings booked per 100 contacts touched — threshold `<set after baseline>`.
- Quality gates that fail the play even if numbers look ok:
  - majority of approved rows have a junior contact as the named buyer
  - rows missing a one-line outreach hook
  - source_query field is missing or unreadable
  - trigger field is invented rather than observed
  - reply volume is high but meetings booked stays flat (segment/buyer mismatch)
