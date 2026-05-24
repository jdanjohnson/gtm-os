---
id: client-health-dashboard
name: Client Health Dashboard
kind: skill
description: RAG status across all client accounts.
category: strategy
tags:
- client-health
- dashboard
- monitoring
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Client Health Dashboard

RAG status across all client accounts.

## Input

- **client_data** (crm_export): All client accounts with health signals

## Output

- **dashboard** (json): Red/Amber/Green status per account with risk factors
