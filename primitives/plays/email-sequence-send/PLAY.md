---
id: email-sequence-send
name: Email Sequence Send Pipeline
kind: workflow
description: Take approved prospect list, generate personalized email sequences, send
  via email tool, log activity to CRM.
category: outbound
tags:
- email
- outbound
- sequences
- personalization
channel: email
---

# Email Sequence Send Pipeline

Take approved prospect list, generate personalized email sequences, send via email tool, log activity to CRM.

## Steps

1. **Load approved prospects**
2. **Generate personalized first lines** → skill: `personalization-at-scale`
3. **Build email sequences** → skill: `cold-email-sequence-generator`
4. **Apply subject line optimization** → skill: `email-subject-line-optimizer`
5. **Send sequences** → tool: `email-sender`
6. **Log to CRM** → tool: `acrm-cli`

## Tools

- `email-sender`
- `acrm-cli`

## Skills

- `personalization-at-scale`
- `cold-email-sequence-generator`
- `email-subject-line-optimizer`
