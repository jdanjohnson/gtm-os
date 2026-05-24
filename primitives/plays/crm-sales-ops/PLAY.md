---
id: crm-sales-ops
name: CRM-Driven Sales Operations
kind: playbook
description: Run automated sales operations — call prep, follow-up drafting, stale
  deal recovery, pipeline hygiene — through a headless CRM.
category: sales
tags:
- crm
- sales-ops
- pipeline
- follow-up
- recurring
source_repo: cluster-software/agent-crm
channel: multi
---

# CRM-Driven Sales Operations

Run automated sales operations — call prep, follow-up drafting, stale deal recovery, pipeline hygiene — through a headless CRM.

## Outcome

**Goal:** Keep pipeline healthy and reps productive by automating CRM hygiene and follow-up

## Hypothesis

Automated call prep + follow-up drafting + stale deal sweeps increase rep productivity by 30% measured by meetings held per rep per week.

## Success Criteria

- **rep_meetings_per_week**: >12 meetings held per rep
- **stale_deal_recovery_rate**: >15% of stale deals re-engaged
- **follow_up_response_rate**: >20% of AI-drafted follow-ups get a reply

## Knowledge Required

- **crm-schema**: Attio model: people, companies, deals, posts, transcripts *(required)*
- **call-prep-template**: Structure for pre-call briefs — history, recent activity, discovery questions *(required)*
- **follow-up-voice**: User's writing voice for follow-up drafts *(required)*
- **pipeline-hygiene-rules**: Stale deal thresholds, activity scoring weights, stage duration limits *(required)*

## Workflows

- `crm-activity-logging`
- `deal-qualification-pipeline`

## Skills

- `sales-call-prep-assistant`
- `deal-momentum-analyzer`
- `pipeline-health-analyzer`
- `rep-performance-scorecard`

## Tools

- **acrm-cli**: All CRM operations — init, import, query, export
- **transcript-provider**: Granola, Otter, Fireflies, Fathom, Zoom — pluggable
- **email-sender**: Send follow-up drafts after review

## Agent Config

- **Role:** Sales Operations Agent
- **Process:** polling
- **Phases:** design, build, execute, measure, learn

## Experiments

### Follow-Up Cadence

2-day vs 5-day vs 7-day auto-follow-up intervals, measure response rate

### Call Prep Impact

AI call briefs vs no prep, measure meeting-to-opportunity conversion

### Stale Deal Recovery

Different re-engagement templates for 14d vs 30d vs 60d stale deals
