---
id: renewal-predictor
name: Renewal Predictor
kind: skill
description: Predict renewal likelihood from health score signals.
category: sales
tags:
- renewals
- churn
- prediction
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Renewal Predictor

Predict renewal likelihood from health score signals.

## Input

- **customer_health** (crm_export): Health scores, usage data, support tickets

## Output

- **predictions** (json): Renewal probability per account with risk factors
