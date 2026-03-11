# PESE — LP Prospect Enrichment & Scoring Engine

A system that ingests LP prospect contacts, enriches them with publicly available web data using AI, scores them across four weighted dimensions, and presents the scored pipeline through an interactive Streamlit dashboard.

Built for PaceZero Capital Partners Fund II fundraising.

## Architecture

```
CSV → Ingest (dedup by org) → Enrich (OpenAI + web search) → Score (4 dimensions) → SQLite → Dashboard
```

**Key design decisions:**

- **Org-level deduplication**: Enrichment runs once per organization (not per contact), saving API costs and ensuring consistency. Multiple contacts at the same org share scores. Known aliases are resolved (e.g., PBUCC → Pension Boards United Church of Christ).
- **Resumability**: The pipeline skips already-enriched orgs (`--no-skip` to override), so interrupted runs can be resumed without redundant API calls.
- **Separation of enrichment and scoring**: Enrichment gathers facts via web search; scoring applies rubrics to those facts in a separate call. Rubrics are auditable and tunable without re-running enrichment.
- **Multi-layered LP/GP distinction**: Four layers enforce LP vs GP accuracy: (1) enrichment prompt crosschecks CSV org types against web evidence, (2) scoring prompt has a mandatory pre-scoring check, (3) confirmed GP/Service Providers skip the scoring call entirely, (4) post-processing cap enforces a hard ceiling on sector fit for non-LPs.
- **Cost tracking**: Every API call is logged with token counts, web search call counts, and cost estimates including projected costs at scale.

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

## Sample Output

Full pipeline run on the 100-contact challenge CSV (99 valid contacts after skipping 1 blank row, mapping to 93 unique organizations after deduplication):

```
──────────────────────────────── Pipeline Complete ────────────────────────────────
                Run Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Metric                      ┃ Value     ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Contacts ingested           │ 99        │
│ Unique organizations        │ 93        │
│ Orgs enriched this run      │ 93        │
│ API calls                   │ 183       │
│ Web search calls            │ 93        │
│ Total tokens                │ 1,229,978 │
│ Run cost (USD)              │ $1.2794   │
│ Projected cost (1,000 orgs) │ $14.06    │
└─────────────────────────────┴───────────┘
```

### Top 20 Prospects

```
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ #  ┃ Contact             ┃ Organization                   ┃ Sector ┃ Rel. ┃ Halo ┃ Emrg. ┃ Composite ┃ Tier           ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ 1  │ Roman Torres Boscan │ The Schmidt Family Foundation  │    9.4 │  9.0 │  8.2 │   8.0 │       8.8 │ PRIORITY CLOSE │
│ 2  │ Kim Lew             │ Columbia Investment Mgmt Co.   │    9.0 │  7.0 │  8.0 │   8.0 │       8.1 │ PRIORITY CLOSE │
│ 3  │ Lorenzo Mendez      │ The Rockefeller Foundation     │    9.3 │  6.0 │  9.3 │   7.6 │       8.1 │ PRIORITY CLOSE │
│ 4  │ Minoti Dhanaraj     │ Pension Boards UCC (PBUCC)     │    8.2 │  9.0 │  5.8 │   3.4 │       7.2 │ STRONG FIT     │
│ 5  │ Manuel Alvarez      │ Morgan Stanley Alt. Inv. Ptrs  │    8.5 │  5.0 │  7.8 │   7.6 │       7.2 │ STRONG FIT     │
│ 6  │ Antonio Casal       │ AlTi Global                    │    8.5 │  4.0 │  7.8 │   8.0 │       6.9 │ STRONG FIT     │
│ 7  │ Howard Fischer      │ Gratitude Railroad             │    8.2 │  6.0 │  6.0 │   7.0 │       6.9 │ STRONG FIT     │
│ 8  │ Preet Chawla        │ Carnegie Corporation of NY     │    8.2 │  4.0 │  8.0 │   7.8 │       6.8 │ STRONG FIT     │
│ 9  │ Alexander Gottlieb  │ Neuberger Berman               │    8.6 │  4.0 │  7.6 │   7.4 │       6.8 │ STRONG FIT     │
│ 10 │ Michael FitzSimons  │ Bessemer Trust                 │    8.4 │  4.0 │  7.6 │   7.0 │       6.7 │ STRONG FIT     │
│ 11 │ Lan Cai             │ Pension Boards UCC (PBUCC)     │    8.2 │  7.0 │  5.8 │   3.4 │       6.6 │ STRONG FIT     │
│ 12 │ Sukant Sethi        │ Lincoln Financial Group        │    8.5 │  4.0 │  6.2 │   7.4 │       6.5 │ STRONG FIT     │
│ 13 │ Shane Wolter        │ HSBC                           │    8.6 │  4.0 │  7.3 │   4.6 │       6.4 │ MODERATE FIT   │
│ 14 │ Michael Moriarty    │ Collaborative Capital Advisors │    8.3 │  4.0 │  5.7 │   6.4 │       6.2 │ MODERATE FIT   │
│ 15 │ Saeed Mouzaffar     │ Willett Advisors               │    8.2 │  4.0 │  6.5 │   4.4 │       6.0 │ MODERATE FIT   │
│ 16 │ Jake Kaminski       │ Johnson Family Office          │    8.2 │  4.0 │  5.0 │   6.2 │       6.0 │ MODERATE FIT   │
│ 17 │ Manpreet Singh      │ Singh Capital Partners         │    8.0 │  4.0 │  5.9 │   5.5 │       6.0 │ MODERATE FIT   │
│ 18 │ Chanmeet Narang     │ Singh Capital Partners         │    8.0 │  4.0 │  5.9 │   5.5 │       6.0 │ MODERATE FIT   │
│ 19 │ Al Kim              │ Helmsley Charitable Trust      │    8.0 │  4.0 │  6.5 │   4.0 │       5.9 │ MODERATE FIT   │
│ 20 │ Dan Carroll         │ Inherent Group                 │    8.0 │  5.0 │  5.5 │   3.2 │       5.9 │ MODERATE FIT   │
└────┴─────────────────────┴────────────────────────────────┴────────┴──────┴──────┴───────┴───────────┴────────────────┘
```

### Validation

The pipeline runs automated validation after each run:

- **Score anomalies**: Flags non-LPs with high sector fit scores (>5) and confirmed LPs with low scores (<3). Latest run: **0 anomalies detected**.
- **Org-type conflicts**: Crosschecks CSV-reported org types against AI-enriched classifications. Latest run: **36 conflicts flagged** — the majority are CSV entries labeled "Multi-Family Office" or "Single Family Office" that the AI classified as "Mixed (LP+GP)" based on evidence of both internal management and external allocations.
- **Non-LP cost optimization**: 3 organizations (Meridian Capital Group, PLP, First New York) were identified as GP/Service Providers during enrichment, so the scoring API call was skipped entirely, saving ~$0.04.
- **Non-LP score cap**: 3 Asset Managers (Flat World Partners, New Holland Capital, Variant Investments) had sector fit scores capped from 3.5–5.5 → 3.0 by the post-processing safety net.

## Scoring Dimensions

| Dimension | Weight | Source |
|-----------|--------|--------|
| Sector & Mandate Fit | 35% | AI-scored: LP status (40%) + credit allocation (30%) + sustainability mandate (30%) |
| Relationship Depth | 30% | Pre-computed from CRM (CSV column, used as-is per challenge spec) |
| Halo & Strategic Value | 20% | AI-scored: brand recognition (50%) + network centrality (30%) + signal specificity (20%) |
| Emerging Manager Fit | 15% | AI-scored: structural program (40%) + behavioral track record (40%) + check size fit (20%) |

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

Using `gpt-4o-mini` with web search (Responses API):

| Component | Rate |
|-----------|------|
| Input/output tokens | $0.15 / $0.60 per 1M tokens |
| Web search tool call | $0.01 per call |
| Web search content tokens | Fixed 8k input tokens per call |

Per organization:
- 1 enrichment call (web search) + 1 scoring call (chat completions) = 2 API calls
- Confirmed non-LPs (GP/Service Provider) skip the scoring call, saving ~50% per org
- Estimated ~$0.012–0.015 per organization (including web search fees)
- **Actual run: 99 contacts → 93 unique orgs → $1.28 (~$0.014/org)**
- **Projected: 1,000 orgs → ~$14**

## Project Structure

```
PESE/
├── main.py              # CLI entry point (ingest, run, dashboard, reset)
├── dashboard.py         # Streamlit BI layer with filters, charts, detail views
├── WRITEUP.md           # Design decisions, tradeoffs, and improvements
├── requirements.txt
├── .env.example
├── data/
│   └── challenge_contacts.csv
└── pese/
    ├── config.py        # Centralized configuration and constants
    ├── database.py      # SQLAlchemy ORM models (Organization, Contact, RunLog)
    ├── models.py        # Structured dataclasses (EnrichmentResult, ScoringResult)
    ├── exceptions.py    # Custom exception hierarchy
    ├── ingest.py        # CSV ingestion with org dedup and alias resolution
    ├── scoring.py       # Pure composite scoring, tier classification, check-size estimation
    ├── cost_tracker.py  # API cost tracking (tokens + web search fees)
    ├── pipeline.py      # Orchestrator with validation layer and cost optimization
    └── providers/
        ├── __init__.py  # Provider factory
        ├── base.py      # Abstract AIProvider interface
        └── openai.py    # OpenAI implementation (enrichment + scoring prompts)
```
