---
id: crm-activity-logging
name: CRM Activity Logging
kind: workflow
description: Log activity from any GTM motion back to the CRM — emails sent, calls
  made, meetings held, deals updated.
category: operations
tags:
- crm
- logging
- tracking
- pipeline
channel: multi
---

# CRM Activity Logging

Log activity from any GTM motion back to the CRM — emails sent, calls made, meetings held, deals updated.

## Steps

1. **Receive activity event**
2. **Resolve contact** → tool: `acrm-cli`
3. **Log activity** → tool: `acrm-cli`
4. **Update deal stage** → tool: `acrm-cli`
5. **Checkpoint**

## Tools

- `acrm-cli`
