---
id: prospect-enrichment
name: Prospect Enrichment Pipeline
kind: workflow
description: Take raw prospect list, enrich with contact data, score against ICP,
  output approved rows ready for outreach.
category: enrichment
tags:
- prospecting
- data
- enrichment
- scoring
channel: multi
---

# Prospect Enrichment Pipeline

Take raw prospect list, enrich with contact data, score against ICP, output approved rows ready for outreach.

## Steps

1. **Load raw prospects** → tool: `csv-reader`
2. **Enrich with contact data** → tool: `apollo-api`
3. **LinkedIn profile enrichment** → tool: `browser-use`
4. **Score against ICP** → skill: `lead-scoring-model`
5. **Apply approved-row standard** → tool: `filter`
   - min_score: `70`
   - required_fields: `['email', 'decision_maker_name', 'company_domain']`
6. **Tag with signals**
7. **Output approved list** → output: `enriched_prospects`

## Tools

- `csv-reader`
- `apollo-api`
- `browser-use`
- `filter`

## Skills

- `lead-scoring-model`
