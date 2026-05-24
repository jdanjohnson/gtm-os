---
id: market-sizing-deliverable
name: TAM/SAM/SOM Market Sizing
kind: playbook
description: Produce a full TAM/SAM/SOM deliverable for a market vertical — top-down
  and bottom-up estimates with cited data sources.
category: strategy
tags:
- strategy
- market-sizing
- tam
- research
- fundraising
source_repo: OneWave-AI/claude-skills
channel: multi
---

# TAM/SAM/SOM Market Sizing

Produce a full TAM/SAM/SOM deliverable for a market vertical — top-down and bottom-up estimates with cited data sources.

## Outcome

**Goal:** Deliver a defensible market sizing analysis for fundraising, board decks, or GTM planning

## Hypothesis

Combining top-down (industry reports) and bottom-up (ICP count x ACV) approaches produces a more credible market size than either alone.

## Success Criteria

- **source_count**: >10 cited sources
- **methodology_coverage**: Both top-down and bottom-up presented
- **production_time**: <3 hours

## Knowledge Required

- **market-definition**: What vertical, what geography, what product category *(required)*
- **pricing-model**: Current or planned ACV for bottom-up calculation *(required)*
- **competitor-landscape**: Known competitors and their estimated revenue for triangulation

## Workflows

- `storm-research-pipeline`

## Skills

- `market-sizing`
- `pricing-strategy`
- `competitor-intel-agent`

## Tools

- **web-search**: Find industry reports, analyst estimates, public filings
- **llm-scraper**: Extract market data from research reports and press releases

## Agent Config

- **Role:** Market Analyst
- **Process:** sequential
- **Phases:** design, build, execute, measure, learn

## Experiments

### Methodology Comparison

Top-down only vs bottom-up only vs combined, compare credibility with stakeholders

### Adjacent Market Test

Size the core market vs 2 adjacent markets, identify expansion opportunities
