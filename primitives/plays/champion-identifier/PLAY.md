---
id: champion-identifier
name: Champion Identifier
kind: skill
description: Find internal champions in target accounts.
category: sales
tags:
- champions
- accounts
- stakeholders
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Champion Identifier

Find internal champions in target accounts.

## Input

- **account_contacts** (crm_export): All known contacts at the account

## Output

- **champion_analysis** (json): Ranked champion candidates with engagement strategy
