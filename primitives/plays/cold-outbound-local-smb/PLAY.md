---
id: cold-outbound-local-smb
name: Local SMB Cold Outbound Campaign
kind: playbook
description: Run outbound experiments targeting local businesses — med spas, dentists,
  roofers, restaurants — using Openmart for prospecting and local-specific messaging.
category: outbound
tags:
- sales
- email
- prospecting
- local-smb
- outbound
source_repo: kathrynwu/GTMbrain
channel: email
---

# Local SMB Cold Outbound Campaign

Run outbound experiments targeting local businesses — med spas, dentists, roofers, restaurants — using Openmart for prospecting and local-specific messaging.

## Outcome

**Goal:** Book meetings with local business owners through localized cold outreach

## Hypothesis

Local SMB outbound targeting the owner (not front-desk) with city-specific proof points converts at 2x the rate of generic outreach.

## Success Criteria

- **reply_rate**: >5%
- **meetings_booked_per_100**: >3
- **owner_reach_rate**: >60% of replies from owners

## Knowledge Required

- **icp-definition-local**: Vertical, geography, business size, owner persona, reject rules *(required)*
- **local-outreach-templates**: City-specific subject lines, local proof points, first-touch + follow-ups *(required)*
- **brand-voice**: Tone guidelines — casual, local, non-agency-sounding *(required)*

## Workflows

- `prospect-enrichment`
- `email-sequence-send`
- `crm-activity-logging`

## Skills

- `cold-email-sequence-generator`
- `personalization-at-scale`

## Tools

- **openmart-api**: Find local businesses by vertical + geography
- **email-sender**: Send local outbound sequences
- **acrm-cli**: Log leads and outcomes

## Agent Config

- **Role:** Local SMB Outbound Operator
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Owner vs Front-Desk Test

Target owner directly vs generic email, measure who responds

### Local Proof Test

City-specific proof points vs generic copy, measure reply rate

### Vertical Test

Med spas vs dentists vs roofers in same city, measure conversion
