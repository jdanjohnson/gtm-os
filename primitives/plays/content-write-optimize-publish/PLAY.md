---
id: content-write-optimize-publish
name: Content Write → Optimize → Publish Pipeline
kind: workflow
description: Write long-form content from a research plan, run through 5 optimization
  agents, auto-revise if needed, publish.
category: content
tags:
- content
- writing
- optimization
- publishing
channel: multi
---

# Content Write → Optimize → Publish Pipeline

Write long-form content from a research plan, run through 5 optimization agents, auto-revise if needed, publish.

## Steps

1. **Write draft**
2. **Scrub AI patterns** → tool: `content-scrubber`
3. **Score content quality** → tool: `content-scorer`
   - threshold: `70`
   - max_retries: `2`
4. **Auto-revise if below threshold**
5. **Run optimization agents**
6. **Publish** → tool: `wordpress-api`

## Tools

- `content-scrubber`
- `content-scorer`
- `wordpress-api`

## Skills

- `seo-optimizer`
