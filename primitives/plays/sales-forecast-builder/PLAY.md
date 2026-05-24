---
id: sales-forecast-builder
name: Sales Forecast Builder
kind: skill
description: Weighted pipeline forecast with scenario modeling.
category: sales
tags:
- forecasting
- pipeline
- revenue
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Sales Forecast Builder

Weighted pipeline forecast with scenario modeling.

## Input

- **pipeline_data** (crm_export): Full pipeline with stages and probabilities

## Output

- **forecast** (json): Best/base/worst scenario forecasts with confidence intervals
