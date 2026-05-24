---
id: cold-outbound-b2b
name: B2B Cold Outbound Campaign
kind: playbook
description: Run a multi-touch outbound experiment against a defined B2B ICP — from
  prospecting through enrichment to sequenced email outreach.
category: outbound
tags:
- sales
- email
- prospecting
- b2b
- outbound
source_repo: kathrynwu/GTMbrain
channel: email
---

# B2B Cold Outbound Campaign

Run a multi-touch outbound experiment against a defined B2B ICP — from prospecting through enrichment to sequenced email outreach.

## Outcome

**Goal:** Book qualified meetings from cold outbound email to B2B prospects

## Hypothesis

A focused list of ~200 ICP-fit accounts with senior buyers and why-now signals will outperform a 5000-row export measured by meetings booked per 100 contacts.

## Success Criteria

- **reply_rate**: >3%
- **meetings_booked_per_100**: >5
- **positive_reply_ratio**: >40% of replies are positive

## Knowledge Required

- **icp-definition**: Geography, vertical, company size, buyer persona, reject rules, approved-row standard *(required)*
- **outreach-templates**: Subject lines, first-touch templates, follow-up cadences, CTAs *(required)*
- **brand-voice**: Tone and messaging guidelines for outbound copy *(required)*
- **enrichment-requirements**: Required fields before outreach — email, phone, website, qualification signals *(required)*

## Workflows

- `prospect-enrichment`
- `email-sequence-send`
- `crm-activity-logging`

## Skills

- `cold-email-sequence-generator`
- `personalization-at-scale`
- `lead-scoring-model`
- `objection-pattern-detector`

## Tools

- **apollo-api**: Find contacts at target companies by title, seniority, and signals
- **email-sender**: Send multi-touch sequences via Instantly, Smartlead, or SMTP
- **acrm-cli**: Log leads, activity, and outcomes to CRM

## Agent Config

- **Role:** GTM Outbound Operator
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### ICP Test

Define 3 different ICPs for same vertical, prospect 50 leads each, measure reply rates

### Channel Test

Email-first vs call-first vs LinkedIn-first for same ICP

### Copy Test

A/B test 3 different first-touch emails, measure open + reply rates

### Cadence Test

3-touch vs 5-touch vs 7-touch sequences, measure meeting conversion

### Geography Test

Same ICP across 3 cities, measure which converts best

### Persona Test

Owner vs VP Sales vs RevOps as target persona, measure response quality
