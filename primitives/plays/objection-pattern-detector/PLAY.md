---
id: objection-pattern-detector
name: Objection Pattern Detector
kind: skill
description: Mine lost deals for recurring objection patterns.
category: sales
tags:
- objections
- analysis
- lost-deals
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Objection Pattern Detector

Mine lost deals for recurring objection patterns.

## Input

- **lost_deals** (crm_export): Lost deal records with notes and reasons

## Output

- **patterns** (json): Top objection patterns with frequency and responses
