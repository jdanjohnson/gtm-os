---
id: content-repurposing-pipeline
name: Content Repurposing Pipeline
kind: workflow
description: Take one content asset and produce 8+ derivative formats for multi-channel
  distribution.
category: content
tags:
- content
- repurposing
- distribution
- social
channel: multi
---

# Content Repurposing Pipeline

Take one content asset and produce 8+ derivative formats for multi-channel distribution.

## Steps

1. **Analyze source content**
2. **Generate X posts** → skill: `social-repurposer`
   - platform: `x`
   - count: `5`
3. **Generate LinkedIn posts** → skill: `linkedin-post-optimizer`
   - count: `3`
4. **Generate newsletter section** → skill: `email-template-generator`
   - format: `newsletter_section`
5. **Generate video hooks**
6. **Generate email snippets** → skill: `email-template-generator`
   - format: `nurture_snippet`
7. **Generate slide content**
8. **Generate SEO derivative** → skill: `seo-keyword-cluster-builder`
9. **Output content package** → output: `content_package`

## Skills

- `social-repurposer`
- `linkedin-post-optimizer`
- `email-template-generator`
- `seo-keyword-cluster-builder`
