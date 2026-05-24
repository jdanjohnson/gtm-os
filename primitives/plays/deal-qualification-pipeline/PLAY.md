---
id: deal-qualification-pipeline
name: Deal Qualification Pipeline
kind: workflow
description: Qualify deals through MEDDIC/BANT frameworks — map buying committee,
  assess risk, score deal health, recommend next actions.
category: sales
tags:
- deals
- qualification
- meddic
- bant
- pipeline
channel: multi
---

# Deal Qualification Pipeline

Qualify deals through MEDDIC/BANT frameworks — map buying committee, assess risk, score deal health, recommend next actions.

## Steps

1. **Load deal data** → tool: `acrm-cli`
2. **Run MEDDIC assessment** → skill: `deal-review-framework`
   - methodology: `meddic`
3. **Map buying committee** → skill: `champion-identifier`
4. **Score deal momentum** → skill: `deal-momentum-analyzer`
5. **Identify objection risks** → skill: `objection-pattern-detector`
6. **Generate next actions** → output: `deal_action_plan`
7. **Update CRM** → tool: `acrm-cli`

## Tools

- `acrm-cli`

## Skills

- `deal-review-framework`
- `champion-identifier`
- `deal-momentum-analyzer`
- `objection-pattern-detector`
