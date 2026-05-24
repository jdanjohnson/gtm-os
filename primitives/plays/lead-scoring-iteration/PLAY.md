---
id: lead-scoring-iteration
name: Lead Scoring Model Iteration
kind: playbook
description: Build, test, and iterate a lead scoring model from historical win/loss
  data. Compounds learning as more deals close.
category: sales
tags:
- scoring
- qualification
- analytics
- pipeline
- compounding
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Lead Scoring Model Iteration

Build, test, and iterate a lead scoring model from historical win/loss data. Compounds learning as more deals close.

## Outcome

**Goal:** Build a lead scoring model that predicts deal close probability within 10% accuracy

## Hypothesis

A scoring model trained on historical win/loss data with firmographic + behavioral + intent signals outperforms gut-feel qualification.

## Success Criteria

- **prediction_accuracy**: Within 10% of actual close rate per score bucket
- **ae_time_savings**: >20% reduction in time spent on unqualified leads
- **model_improvement**: Accuracy improves each quarter as more deals close

## Knowledge Required

- **historical-deals**: Won/lost deals with company attributes, engagement data, and outcome *(required)*
- **scoring-methodology**: How to weight firmographic, behavioral, and intent signals *(required)*
- **icp-definition**: Current ICP to validate model alignment *(required)*

## Workflows

- `inbound-scoring-pipeline`

## Skills

- `lead-scoring-model`
- `intent-signal-aggregator`
- `deal-review-framework`

## Tools

- **acrm-cli**: Query historical deal data and apply scores to current pipeline

## Agent Config

- **Role:** Revenue Operations Analyst
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Signal Weight Test

Firmographic-heavy vs behavioral-heavy vs intent-heavy weighting, measure prediction accuracy

### Threshold Test

Score >50 vs >60 vs >70 as "qualified" threshold, measure AE acceptance rate

### Quarterly Retrain

Retrain model each quarter with new closed deals, measure accuracy improvement
