---
id: deal-closing-motion
name: Deal Closing Motion
kind: playbook
description: Run a structured closing strategy — map the buying committee, handle
  objections, drive urgency, and close.
category: sales
tags:
- sales
- closing
- deal-management
- pipeline
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Deal Closing Motion

Run a structured closing strategy — map the buying committee, handle objections, drive urgency, and close.

## Outcome

**Goal:** Increase close rate on qualified pipeline by running a structured closing motion

## Hypothesis

Deals with mapped buying committees and pre-handled objections close at 2x the rate of unstructured follow-up.

## Success Criteria

- **close_rate**: >30% of qualified pipeline
- **sales_cycle_days**: <45 days average
- **deal_value**: No unnecessary discounting (>90% of list price)

## Knowledge Required

- **deal-review-framework**: MEDDIC/BANT assessment with risk scoring criteria *(required)*
- **objection-patterns**: Common objection patterns mined from lost deals *(required)*
- **buying-committee-map**: Roles (champion, economic buyer, technical evaluator, blocker) and engagement strategy per role *(required)*
- **competitive-battlecards**: Per-competitor positioning, weaknesses, displacement talk tracks

## Workflows

- `deal-qualification-pipeline`
- `crm-activity-logging`

## Skills

- `deal-closer-playbook`
- `deal-review-framework`
- `deal-momentum-analyzer`
- `champion-identifier`
- `objection-pattern-detector`
- `sales-call-prep-assistant`

## Tools

- **acrm-cli**: Track deal stage, activity, and buying committee contacts
- **email-sender**: Send follow-up and nurture sequences to buying committee

## Agent Config

- **Role:** Deal Strategist
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### MEDDIC vs BANT

Run MEDDIC qualification on 20 deals vs BANT on 20 deals, measure close rate

### Multi-Thread vs Single-Thread

Engage 3+ buying committee members vs champion-only, measure deal velocity

### Objection Pre-Handle Test

Proactively address top 3 objections vs reactive handling, measure close rate
