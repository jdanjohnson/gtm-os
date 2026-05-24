---
id: seo-content-cluster
name: SEO Content Cluster Experiment
kind: playbook
description: Run a content cluster experiment — pillar page + supporting articles
  — targeting a keyword cluster. Measures ranking velocity, organic traffic, and lead
  generation.
category: content
tags:
- seo
- content
- organic
- inbound
source_repo: TheCraigHewitt/seomachine
channel: multi
---

# SEO Content Cluster Experiment

Run a content cluster experiment — pillar page + supporting articles — targeting a keyword cluster. Measures ranking velocity, organic traffic, and lead generation.

## Outcome

**Goal:** Rank in top 3 for a target keyword cluster and generate organic inbound leads

## Hypothesis

A pillar page with 5 supporting articles published over 4 weeks will rank top-10 faster than standalone articles, measured by impressions and clicks in GSC.

## Success Criteria

- **ranking_position**: Top 10 within 6 weeks, top 3 within 12 weeks
- **organic_clicks_per_week**: >100 after week 8
- **content_quality_score**: >70 on seomachine scorer

## Knowledge Required

- **brand-voice**: Tone, vocabulary, examples of on-brand writing *(required)*
- **seo-guidelines**: Target keywords, density rules, internal linking map, meta standards *(required)*
- **content-structure**: H1/H2/H3 hierarchy, intro hooks, CTA placement, section length targets *(required)*
- **internal-links-map**: All existing content URLs with anchor text for internal linking
- **ai-pattern-removal**: Rules for scrubbing AI watermarks and cliche patterns *(required)*

## Workflows

- `seo-research-pipeline`
- `content-write-optimize-publish`

## Skills

- `seo-optimizer`
- `seo-keyword-cluster-builder`
- `brand-voice-analyzer`
- `content-repurposer`
- `landing-page-copywriter`

## Tools

- **web-search**: SERP analysis — top 5 articles for target keyword
- **content-scorer**: Score across Humanity (30%), Specificity (25%), Structure (20%), SEO (15%), Readability (10%)
- **wordpress-api**: Publish draft with Yoast SEO metadata

## Agent Config

- **Role:** SEO Content Strategist
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Content Length Test

1500 vs 2500 vs 4000 word articles for same keyword, measure ranking velocity

### Research Depth Test

SERP-only vs SERP+Social research, measure content uniqueness

### Publishing Cadence Test

2x/week vs daily, measure domain authority and indexing speed

### Cluster vs Standalone Test

Pillar + 5 supporting vs 6 standalone articles, measure cluster ranking
