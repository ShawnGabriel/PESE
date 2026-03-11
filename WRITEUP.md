# PESE — Design Decisions, Tradeoffs, and Future Improvements

## Key Design Decisions

**Split enrichment from scoring.** Enrichment gathers facts via OpenAI's web search tool; scoring applies rubrics to those facts in a separate call. This makes the scoring rubrics auditable and tunable without re-running expensive web searches — a critical property at scale. It also means enrichment data can be reused if scoring criteria change.

**Org-level deduplication with alias resolution.** The 100 contacts map to ~94 unique organizations. Enrichment runs once per org, not per contact, and an alias map (e.g., PBUCC → Pension Boards United Church of Christ) catches duplicates the CSV doesn't surface. At 1,000 contacts, this could cut API costs by 30–50%.

**Multi-layered LP/GP distinction.** Correctly separating LPs from GPs is the highest-leverage accuracy problem in this pipeline. Four layers enforce it: (1) the enrichment prompt crosschecks CSV org types against web evidence, (2) the scoring prompt has a mandatory pre-scoring check that caps non-LP scores, (3) confirmed GP/Service Providers skip the scoring API call entirely, and (4) a post-processing cap enforces a hard ceiling of 3.0 on sector fit for any non-LP that slips through. This defense-in-depth approach handles the reality that LLMs are probabilistic — no single prompt instruction is 100% reliable.

**Sub-component scoring with weighted composites.** Each AI-scored dimension is decomposed into 2–3 weighted sub-components (e.g., D1 = LP Status × 0.4 + Credit Allocation × 0.3 + Sustainability Mandate × 0.3). This forces the model to reason about each factor independently and makes scores interpretable — a fundraising team can see *why* an org scored 7.2, not just that it did.

**Provider abstraction.** An `AIProvider` abstract base class with a factory function means swapping from OpenAI to another provider (Claude, Gemini) requires implementing two methods (`enrich`, `score`) without touching any pipeline or scoring logic.

## Tradeoffs

**gpt-4o-mini over gpt-4o.** 10x cheaper ($0.15/$0.60 vs $2.50/$10.00 per 1M tokens). For structured extraction from web search results and rubric application, mini is sufficient — the quality bottleneck is in prompt design, not model capability. At 1,000 orgs, this saves ~$100+.

**Sequential processing over concurrency.** The pipeline processes orgs one at a time with a 0.5s delay. This is simple, safe with SQLite, and avoidable for a 100-contact run (~15 min). For 1,000+ orgs, async processing with connection pooling would be necessary.

**Free web data over paid sources.** PitchBook or Preqin would provide structured AUM and allocation data directly. Web search gives unstructured text that the LLM must interpret — noisier, but it tests the AI enrichment capability that is the core of this challenge. The system flags low-confidence results where web data was sparse.

**Scoring via Chat Completions (no web search).** Enrichment uses the Responses API with web search ($0.01/call + 8k search tokens). Scoring uses Chat Completions without web search — the enrichment data is already gathered, so paying for a second web search would be wasteful. This halves the web search cost per org.

## What I'd Improve With More Time

1. **Async concurrent processing** with configurable concurrency limits and a connection-pooled database (PostgreSQL) for throughput at 1,000+ orgs.
2. **Confidence-weighted composite scoring** — discount dimensions where the model reports LOW confidence rather than treating all scores equally.
3. **Human-in-the-loop review queue** for edge cases: the ~40 org-type conflicts and any scores that deviate from calibration anchors could surface in a review tab for manual override.
4. **Enrichment caching with TTL** — cache web search results with a configurable expiry (e.g., 30 days) so re-runs don't re-research orgs whose public profile hasn't changed.
5. **Cross-provider validation** — run a sample through both OpenAI and Claude, flag any scores that diverge by >2 points for manual review.
