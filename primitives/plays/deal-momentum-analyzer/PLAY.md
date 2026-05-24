---
id: deal-momentum-analyzer
name: Deal Momentum Analyzer
kind: skill
description: Score deal velocity from engagement patterns and activity recency.
category: sales
tags:
- deals
- velocity
- engagement
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Deal Momentum Analyzer

Score deal velocity from engagement patterns and activity recency.

## Input

- **deal_activity** (crm_export): Activity log with timestamps

## Output

- **momentum_score** (json): Velocity score with trend direction and key signals
