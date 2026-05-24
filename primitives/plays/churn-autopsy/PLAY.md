---
id: churn-autopsy
name: Churn Autopsy
kind: skill
description: Post-mortem analysis when a client churns.
category: strategy
tags:
- churn
- analysis
- retention
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Churn Autopsy

Post-mortem analysis when a client churns.

## Input

- **customer_data** (crm_export): Churned customer history and interactions

## Output

- **autopsy** (markdown): Root cause analysis with prevention recommendations
