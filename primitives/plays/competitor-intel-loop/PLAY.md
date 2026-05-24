---
id: competitor-intel-loop
name: Competitive Intelligence Loop
kind: playbook
description: Run ongoing competitive monitoring — track pricing, content, hiring,
  product changes — and generate actionable briefs on a schedule.
category: intelligence
tags:
- competitive-intel
- monitoring
- research
- recurring
source_repo: calesthio/Crucix
channel: multi
---

# Competitive Intelligence Loop

Run ongoing competitive monitoring — track pricing, content, hiring, product changes — and generate actionable briefs on a schedule.

## Outcome

**Goal:** Detect competitive threats and opportunities faster than competitors detect yours

## Hypothesis

Monitoring competitor pricing, hiring, content, and product pages weekly will surface actionable signals within 48 hours of change, enabling faster GTM response.

## Success Criteria

- **signal_detection_speed**: <48 hours from competitor change to internal brief
- **actionable_signals_per_week**: >3
- **false_positive_rate**: <20%

## Knowledge Required

- **competitor-watchlist**: Companies, products, URLs, and people to track *(required)*
- **alert-thresholds**: What constitutes a meaningful signal vs noise per data source *(required)*
- **brief-format**: Structure for briefs — signal, context, implication, recommended action *(required)*
- **market-context**: Industry-specific interpretation rules for signals

## Workflows

- `competitor-monitoring-sweep`
- `intelligence-brief-generation`

## Skills

- `competitor-intel-agent`
- `competitor-content-analyzer`
- `competitor-price-tracker`
- `intent-signal-aggregator`

## Tools

- **changedetection-io**: Monitor competitor websites for pricing, content, and product changes
- **web-search**: Search for competitor news, press releases, job postings
- **maigret**: Track competitor employee social presence and activity
- **llm-scraper**: Extract structured data from competitor pages

## Agent Config

- **Role:** Competitive Intelligence Analyst
- **Process:** polling
- **Phases:** design, build, execute, measure, learn

## Experiments

### Signal Precision Tuning

Tune alert thresholds over 30 days, measure false positive reduction

### Source Coverage Test

Web monitoring only vs web + social + job boards, measure signal completeness

### Brief Automation Test

Auto-generated briefs vs human-written, measure actionability rating
