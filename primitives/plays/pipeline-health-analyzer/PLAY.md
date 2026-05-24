---
id: pipeline-health-analyzer
name: Pipeline Health Analyzer
kind: skill
description: Identify stalled deals and predict close probability from pipeline data.
category: sales
tags:
- pipeline
- deals
- forecasting
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Pipeline Health Analyzer

Identify stalled deals and predict close probability from pipeline data.

## Input

- **deal_pipeline** (crm_export): Current pipeline with stages, dates, and activity

## Output

- **health_report** (markdown): Pipeline health with stalled deal flags and recommendations
