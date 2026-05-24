---
id: competitor-monitoring-sweep
name: Competitor Monitoring Sweep
kind: workflow
description: Run a scheduled sweep across competitor websites, job boards, social
  presence, and news — collect signals and generate a change report.
category: intelligence
tags:
- monitoring
- competitor
- signals
- recurring
channel: multi
---

# Competitor Monitoring Sweep

Run a scheduled sweep across competitor websites, job boards, social presence, and news — collect signals and generate a change report.

## Steps

1. **Check website changes** → tool: `changedetection-io`
2. **Check job postings** → tool: `web-search`
3. **Check social presence** → tool: `maigret`
4. **Check news and press** → tool: `web-search`
   - recency: `7d`
   - sources: `['news', 'press-releases']`
5. **Aggregate signals**
6. **Generate change report** → output: `intelligence_brief`

## Tools

- `changedetection-io`
- `web-search`
- `maigret`
