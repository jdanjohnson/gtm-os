---
id: inbound-lead-qualifier
name: Inbound Lead Qualifier
kind: skill
description: Score inbound leads by ICP fit, intent, and urgency.
category: sales
tags:
- inbound
- scoring
- qualification
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Inbound Lead Qualifier

Score inbound leads by ICP fit, intent, and urgency.

## Input

- **lead_data** (json): Inbound lead information

## Output

- **qualification** (json): ICP score, intent score, urgency score, routing decision
