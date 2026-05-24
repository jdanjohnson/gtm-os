---
id: inbound-scoring-pipeline
name: Inbound Lead Scoring Pipeline
kind: workflow
description: Score inbound leads by ICP fit, intent signals, and urgency — route to
  sales (hot), nurture (warm), or archive (cold).
category: inbound
tags:
- inbound
- scoring
- routing
- qualification
channel: multi
---

# Inbound Lead Scoring Pipeline

Score inbound leads by ICP fit, intent signals, and urgency — route to sales (hot), nurture (warm), or archive (cold).

## Steps

1. **Receive inbound lead**
2. **Enrich lead data** → tool: `llm-scraper`
3. **Score ICP fit** → skill: `inbound-lead-qualifier`
4. **Score intent** → skill: `intent-signal-aggregator`
5. **Score urgency**
6. **Compute composite score**
7. **Route lead** → output: `routing_decision`
   - hot_threshold: `70`
   - warm_threshold: `40`
8. **Log to CRM** → tool: `acrm-cli`

## Tools

- `llm-scraper`
- `acrm-cli`

## Skills

- `inbound-lead-qualifier`
- `intent-signal-aggregator`
