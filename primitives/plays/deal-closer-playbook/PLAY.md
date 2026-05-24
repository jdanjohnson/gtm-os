---
id: deal-closer-playbook
name: Deal Closer Playbook
kind: skill
description: Closing strategy with buying committee mapping and objection handling.
category: sales
tags:
- closing
- deals
- objections
- buying-committee
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Deal Closer Playbook

Closing strategy with buying committee mapping and objection handling.

## Input

- **deal_data** (crm_record): Deal with contacts, activity history, and notes
- **lost_deal_patterns** (json): Historical objection patterns from lost deals

## Output

- **closing_strategy** (markdown): Step-by-step closing plan with committee engagement map
- **objection_responses** (json): Prepared responses for likely objections

## Knowledge

- **closing-frameworks**: MEDDIC champion-based close, multi-thread engagement, mutual action plans
