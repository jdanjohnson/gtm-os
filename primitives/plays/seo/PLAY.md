---
id: seo
name: SEO
channel: seo
description: GSC-first SEO loop — diagnose CTR vs position, validate intent in Semrush, decide improve-existing vs new-page, then check PostHog after the click.
---

# SEO

Use this play to grow pages that already have traction, not to publish more content. It starts from real Google Search Console data, diagnoses CTR vs position to pick the right page action, validates volume and intent in Semrush, and uses PostHog to confirm the page promise matches the product after the user clicks. The default move is to fix what is already showing up — not to add a new page just because a topic feels interesting.

## ICP

- A product or content site with at least one page already showing impressions in Google Search Console
- A target keyword set that is ICP-fit: search volume ≥150, top-10 dominated by relevant competitors or category pages, ≥3 related question queries showing real demand
- A team that owns both content and product copy and can edit existing pages without a heavy release process
- PostHog (or equivalent post-click analytics) installed so user behavior after the click is visible
- Bad fit: brand-new sites with zero impressions, keyword targets with no commercial intent, teams that cannot ship copy changes

## Hypothesis

Diagnosing the CTR-vs-position bottleneck on existing pages with impressions and applying the matching fix — rewrite the snippet for low CTR, strengthen the page and add supporting content for low position — produces more clicks per impression and more ICP-fit traffic than publishing new pages. PostHog confirms whether the page promise actually matches the product after the click.

## Sequence

1. Pull the previous day's GSC data (impressions, queries, pages with traction) via `GSC_SEARCH_ANALYTICS`.
2. For each query/page with meaningful impressions, diagnose the bottleneck:
   - Low CTR with reasonable position → snippet / page promise problem.
   - Low position with reasonable CTR → ranking / content-strength problem.
3. Validate the keyword in Semrush via `SEMRUSH_KEYWORD_OVERVIEW`: search volume, commercial variations, and the top-ranking pages that actually match the product.
4. Inspect the top 10 SERP results with `GOOGLESEARCH_SEARCH`. If they are mostly tutorial blogs, intent is informational — plan a supporting blog or insert into an existing page, not a hard-sell product page.
5. Decide the page action:
   - **Improve existing page** (default when the page already has impressions or the keyword already attaches to a product/category page).
   - **Create a new page** (when intent is informational and no existing page matches, or when a query cluster clearly justifies its own page).
   - **Consolidate** (merge multiple weak low-impression pages into one stronger page when overlap is high).
6. If CTR is low: rewrite `<title>` and meta description so the promise is clearer, add richer sections, strengthen credibility on the page.
7. If position is low: add relevant high-volume keywords naturally, benchmark higher-ranking pages, strengthen sections with better content + interactive elements, add a stronger conversion CTA. Add a supporting blog if the SERP demands it.
8. Apply the default page outline: H1 with core keyword → pain/use-case section → core H2/H3 sections → internal-linking section → FAQ → bottom CTA. Add a breadcrumb path `Home > Category > Current page` and a related-content block.
9. Write the page brief in `GOOGLEDOCS_CREATE_DOC`: target keyword, current GSC metrics, diagnosis, recommended action, outline, internal links, CTA. Track keyword decisions in `GOOGLESHEETS_BATCH_UPDATE`.
10. Call `request_approval` before publishing. After approval, ship the change.
11. Check PostHog after the click via `POSTHOG_QUERY`: entry URLs, drop-off points, session recordings to confirm the SERP promise matches the product reality.
12. Re-pull GSC after impressions accumulate. Iterate on the page or the snippet based on the new diagnosis. Refresh actively worked pages with fresher data; refresh social proof. Check Semrush every 1–2 weeks for new competitors emerging around core terms.

## Success criteria

- Clicks per impression increase on the targeted page/query.
- ICP-fit traffic share rises (validated via PostHog landing-page-to-product-event conversion).
- Position moves into the top 10 (then top 3) for at least one targeted query within the iteration window.
- Quality gates that fail the play even if numbers look ok:
  - new pages created when an existing page already had impressions for the same query
  - keyword targets that fail the volume/intent/question-query checks
  - title/meta rewrites that don't actually match the underlying page content
  - PostHog post-click check skipped — the promise → product reality gap is invisible
  - "refresh" turns into rewriting the URL or breaking inbound links
