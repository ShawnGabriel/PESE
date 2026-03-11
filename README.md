# PESE — LP Prospect Enrichment & Scoring Engine

A prototype system that ingests LP prospect contacts, enriches them with publicly available web data using AI, scores them across four dimensions, and presents the scored pipeline through an interactive dashboard.

Built for PaceZero Capital Partners Fund II fundraising.

## Architecture

```
CSV → Ingest (dedup by org) → Enrich (OpenAI + web search) → Score (4 dimensions) → SQLite → Dashboard
```

**Key design decisions:**

- **Org-level deduplication**: Enrichment runs once per organization (not per contact), saving API costs and ensuring consistency. Multiple contacts at the same org share scores.
- **Resumability**: The pipeline skips already-enriched orgs, so interrupted runs can be resumed without redundant API calls.
- **Separation of enrichment and scoring**: Enrichment gathers facts via web search; scoring applies rubrics to those facts. This makes the rubrics auditable and tunable without re-running enrichment.
- **Cost tracking**: Every API call is logged with token counts and cost estimates.

## Setup

### 1. Install dependencies

```bash
cd PESE
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Run the pipeline

```bash
# Full run (enrich + score all organizations)
python main.py run

# Test with a small subset first
python main.py run --limit 5

# Re-enrich everything (ignore cached results)
python main.py run --no-skip

# Use a different CSV
python main.py run --csv /path/to/contacts.csv
```

### 4. View the dashboard

```bash
python main.py dashboard
# or directly:
streamlit run dashboard.py
```

### Other commands

```bash
# Ingest CSV only (no enrichment)
python main.py ingest

# Reset the database
python main.py reset
```

## Scoring Dimensions

| Dimension | Weight | Source |
|-----------|--------|--------|
| Sector & Mandate Fit | 35% | AI-scored: LP status + credit allocation + sustainability mandate |
| Relationship Depth | 30% | Pre-computed from CRM (CSV column, used as-is) |
| Halo & Strategic Value | 20% | AI-scored: brand recognition + network centrality + signal specificity |
| Emerging Manager Fit | 15% | AI-scored: structural program + behavioral track record + check size fit |

**Composite** = (Sector × 0.35) + (Relationship × 0.30) + (Halo × 0.20) + (Emerging × 0.15)

**Tiers**: >= 8.0 PRIORITY CLOSE | >= 6.5 STRONG FIT | >= 5.0 MODERATE FIT | < 5.0 WEAK FIT

### Research-Backed Weight Rationale

The 35/30/20/15 weights are defined by the challenge specification and validated by academic and industry literature (up to March 2026):

**D1 — Sector & Mandate Fit (35%)**. Mandate alignment is the primary gate in every LP allocation framework studied. Goyal, Wahal & Yavuz (SSRN 3910494, 2021-2024) find that LPs invest in first-time GPs at rates similar to top-quartile performers, suggesting mandate fit outweighs track record as a predictor of commitment. bfinance's "Impact Private Debt: DNA of a Manager Search" (2025) confirms mandate alignment as the threshold filter for impact private debt specifically. The GIIN "State of the Market 2025" survey shows two-thirds of impact investors now formalize impact criteria in investment governance, making sustainability mandates a reliable structural signal.

**D2 — Relationship Depth (30%)**. Warm introductions convert at ~4x the rate of cold outreach (74% vs ~20%), and GPs with systematic relationship mapping close funds 6-9 months faster (Altss, "Institutional LP Allocation Decision Framework," 2024-2025). Lerner et al. (SSRN 2514248) show relationship depth functions as currency in private markets — LPs with deeper GP relationships gain access to oversubscribed funds. This dimension is pre-computed from CRM data and reflects effort already invested, making it the most actionable signal for a fundraising team.

**D3 — Halo & Strategic Value (20%)**. Cole & Zochowski (HBS, 2020) find that impact funds with anchor investors are $9M larger at final close, driven by a catalytic "halo effect" where the anchor's endorsement signals quality to risk-averse LPs. For emerging managers with weak signals (limited track record), halo amplification is disproportionately valuable — unrealized performance positively influences fundraising only when amplified by institutional credibility (Exeter, "Media Attention and Resource Mobilization," 2024). PE firms sharing common LP partners are 3x more likely to transact (Clique Premium Research, 2024), validating network centrality as a measurable signal.

**D4 — Emerging Manager Fit (15%)**. Rede Partners (September 2024) surveyed 68 US-based LPs actively investing in emerging managers: 100% plan to maintain or increase EM allocations, but 74% still prioritize proven track records, confirming EM fit as a secondary filter downstream of mandate alignment. Only 0.26% of $92.2T in institutional assets is managed by emerging managers (LEIA, 2025), making EM program presence a meaningful differentiator when found.

**Cross-cutting**: Braun, Jenkinson, Schemmerl & Phalippou (SSRN 4490991, 2023) demonstrate a 25% performance spread between top and bottom terciles based on qualitative PPM information that LPs fail to incorporate — validating the use of AI to extract and score qualitative signals (mandate fit, sustainability, EM programs) that traditional processes handle poorly. The weighted composite approach is consistent with Analytic Hierarchy Process (AHP) methodology used in institutional investment appraisal (IJEF, 2023).

## Cost Estimation

Using `gpt-4o-mini` with web search:
- ~2 API calls per organization (enrichment + scoring)
- Estimated ~$0.01–0.03 per organization
- 100 contacts (~90 unique orgs): ~$1–3
- 1,000 orgs projected: ~$10–30

## Project Structure

```
PESE/
├── main.py              # CLI entry point
├── dashboard.py         # Streamlit dashboard
├── requirements.txt
├── .env.example
├── data/
│   └── challenge_contacts.csv
└── pese/
    ├── config.py        # Configuration and constants
    ├── database.py      # SQLAlchemy ORM models
    ├── models.py        # Structured dataclasses (EnrichmentResult, ScoringResult)
    ├── exceptions.py    # Custom exception hierarchy
    ├── ingest.py        # CSV ingestion with org dedup
    ├── scoring.py       # Composite scoring and tier classification
    ├── cost_tracker.py  # API cost tracking
    ├── pipeline.py      # Orchestrator with validation layer
    └── providers/
        ├── __init__.py  # Provider factory
        ├── base.py      # Abstract AIProvider interface
        └── openai.py    # OpenAI implementation (web search + scoring prompts)
```
