---
id: content-repurposing-engine
name: Content Repurposing Engine
kind: playbook
description: Take one piece of content (blog post, podcast, webinar) and produce 8+
  formats — X posts, LinkedIn posts, newsletter, video hooks, email snippets, slide
  decks.
category: content
tags:
- content
- repurposing
- social
- distribution
- recurring
source_repo: OneWave-AI/claude-skills
channel: multi
---

# Content Repurposing Engine

Take one piece of content (blog post, podcast, webinar) and produce 8+ formats — X posts, LinkedIn posts, newsletter, video hooks, email snippets, slide decks.

## Outcome

**Goal:** Maximize distribution of every content asset by repurposing into every relevant channel

## Hypothesis

Repurposing one blog post into 8+ formats within 24 hours of publication generates 5x the total impressions of the original post alone.

## Success Criteria

- **formats_per_asset**: >8 distinct formats per content piece
- **total_impressions**: >5x original post impressions across all formats
- **production_time**: <30 minutes per repurposing cycle

## Knowledge Required

- **brand-voice**: Platform-specific tone rules (LinkedIn = professional, X = punchy, newsletter = conversational) *(required)*
- **platform-constraints**: Character limits, image sizes, hashtag rules per platform *(required)*
- **content-calendar**: Publishing schedule and platform priority order

## Workflows

- `content-repurposing-pipeline`

## Skills

- `content-repurposer`
- `social-repurposer`
- `social-selling-content-generator`
- `linkedin-post-optimizer`
- `email-template-generator`
- `podcast-content-suite`

## Tools

- **web-search**: Find trending hooks and angles relevant to the content topic
- **llm-scraper**: Extract key quotes and data points from original content

## Agent Config

- **Role:** Content Distribution Operator
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Platform Priority Test

LinkedIn-first vs X-first vs newsletter-first distribution, measure engagement

### Format Count Test

5 formats vs 8 formats vs 12 formats, measure diminishing returns

### Timing Test

Same-day repurposing vs 3-day staggered release, measure total reach
