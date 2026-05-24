---
id: inbound-lead-qualification
name: Inbound Lead Qualification Pipeline
kind: playbook
description: Qualify inbound leads from email/form submissions — score by ICP fit,
  intent, and urgency — route to sales or nurture.
category: inbound
tags:
- inbound
- lead-qualification
- email
- crm
- routing
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Inbound Lead Qualification Pipeline

Qualify inbound leads from email/form submissions — score by ICP fit, intent, and urgency — route to sales or nurture.

## Outcome

**Goal:** Qualify inbound leads within 5 minutes and route to the right sales motion

## Hypothesis

Automated lead scoring + instant routing reduces time-to-first-contact from 24h to <5min, increasing qualified meeting rate by 3x.

## Success Criteria

- **time_to_first_contact**: <5 minutes
- **qualified_rate**: >25% of inbound leads are ICP-fit
- **meeting_conversion**: >15% of qualified leads book a meeting

## Knowledge Required

- **icp-definition**: Company size, vertical, title, budget signals that define a qualified lead *(required)*
- **scoring-weights**: How to weight firmographic, behavioral, and intent signals *(required)*
- **routing-rules**: Score thresholds for hot (route to AE), warm (nurture), cold (archive) *(required)*

## Workflows

- `inbound-scoring-pipeline`
- `crm-activity-logging`

## Skills

- `inbound-lead-qualifier`
- `lead-scoring-model`
- `intent-signal-aggregator`

## Tools

- **gmail-api**: Read inbound emails and form submission notifications
- **acrm-cli**: Create/update lead records with scores and routing
- **email-sender**: Send instant follow-up to hot leads

## Agent Config

- **Role:** Inbound Qualification Agent
- **Process:** event-driven
- **Phases:** design, build, execute, measure, learn

## Experiments

### Speed-to-Lead Test

5-min auto-response vs 24h manual response, measure meeting rate

### Scoring Model Test

Firmographic-only vs firmographic+behavioral scoring, measure qualification accuracy

### Routing Threshold Test

Aggressive (score >50 = hot) vs conservative (score >70 = hot), measure AE time waste
