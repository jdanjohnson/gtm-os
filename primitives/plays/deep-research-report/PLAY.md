---
id: deep-research-report
name: Deep Research Report
kind: playbook
description: Generate comprehensive, cited research reports on any GTM-relevant topic
  — competitor analysis, market maps, ICP research, trend reports, battlecards.
category: research
tags:
- research
- reports
- intelligence
- citations
source_repo: stanford-oval/storm
channel: multi
---

# Deep Research Report

Generate comprehensive, cited research reports on any GTM-relevant topic — competitor analysis, market maps, ICP research, trend reports, battlecards.

## Outcome

**Goal:** Produce a publication-quality research report with citations that informs GTM strategy

## Hypothesis

AI-generated research reports with multi-source citation and expert persona simulation match the quality of analyst reports at 1/10th the time.

## Success Criteria

- **citation_count**: >20 unique sources per report
- **production_time**: <2 hours per report
- **actionability_score**: >80% of readers rate it actionable

## Knowledge Required

- **topic-context**: What the user already knows, what gaps need filling *(required)*
- **source-preferences**: Preferred sources, excluded domains, recency requirements

## Workflows

- `storm-research-pipeline`

## Skills

- `market-sizing`
- `competitor-intel-agent`
- `competitor-content-analyzer`

## Tools

- **web-search**: Multi-provider search (Bing, Serper, Brave, Tavily, Google, DuckDuckGo)
- **llm-scraper**: Extract structured data from research sources
- **vector-store**: Semantic search over collected research for section writing

## Agent Config

- **Role:** Research Analyst
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Competitor Deep-Dive

Generate 5000-word report on a competitor's full GTM strategy

### Market Map

Research report on an entire market vertical with company comparisons

### ICP Research

Deep research on a buyer persona — pain points, watering holes, buying triggers

### Weekly Trend Report

Automated weekly trend report on your market

### Battlecard Generation

Research competitor products, generate sales battlecards with citations
