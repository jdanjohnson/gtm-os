---
id: intent-signal-monitoring
name: Buyer Intent Signal Monitoring
kind: playbook
description: Monitor buyer intent signals across the web — job postings, tech stack
  changes, funding announcements, content engagement — and feed high-intent accounts
  into pipeline.
category: intelligence
tags:
- intent
- signals
- monitoring
- pipeline
- recurring
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Buyer Intent Signal Monitoring

Monitor buyer intent signals across the web — job postings, tech stack changes, funding announcements, content engagement — and feed high-intent accounts into pipeline.

## Outcome

**Goal:** Identify accounts showing buying intent before they enter a formal evaluation

## Hypothesis

Accounts with 3+ intent signals (hiring, funding, tech migration) convert to meetings at 4x the rate of cold-sourced accounts.

## Success Criteria

- **intent_signals_per_week**: >20 high-confidence signals
- **signal_to_meeting_rate**: >10% of signaled accounts accept a meeting
- **pipeline_from_intent**: >30% of new pipeline attributed to intent signals

## Knowledge Required

- **signal-definitions**: What counts as a buying signal — hiring for roles, tech stack changes, funding, content consumption *(required)*
- **icp-definition**: Which accounts to monitor for signals *(required)*
- **signal-scoring**: How to weight different signal types and recency *(required)*

## Workflows

- `competitor-monitoring-sweep`
- `inbound-scoring-pipeline`

## Skills

- `intent-signal-aggregator`
- `lookalike-customer-finder`
- `lead-scoring-model`

## Tools

- **changedetection-io**: Monitor career pages and tech stack pages for changes
- **web-search**: Search for funding announcements and press releases
- **llm-scraper**: Extract structured hiring and product data from company pages

## Agent Config

- **Role:** Intent Signal Analyst
- **Process:** polling
- **Phases:** design, build, execute, measure, learn

## Experiments

### Signal Type Test

Hiring signals vs funding signals vs tech stack signals, measure which predicts buying best

### Signal Freshness Test

Signals from last 7 days vs last 30 days, measure meeting acceptance rate

### Multi-Signal Threshold

1 signal vs 2+ signals vs 3+ signals required before outreach, measure conversion
