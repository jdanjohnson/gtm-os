---
id: storm-research-pipeline
name: STORM Research Pipeline
kind: workflow
description: Run the STORM multi-stage research pipeline — knowledge curation via
  simulated expert conversations, outline generation, article writing with citations,
  polishing.
category: research
tags:
- research
- storm
- citations
- reports
channel: multi
---

# STORM Research Pipeline

Run the STORM multi-stage research pipeline — knowledge curation via simulated expert conversations, outline generation, article writing with citations, polishing.

## Steps

1. **Knowledge curation** → tool: `web-search`
   - providers: `['bing', 'serper', 'brave', 'tavily', 'google', 'duckduckgo']`
   - max_sources: `30`
2. **Generate outline**
3. **Write article sections**
4. **Polish article**
5. **Output report** → output: `research_report`

## Tools

- `web-search`
- `vector-store`
