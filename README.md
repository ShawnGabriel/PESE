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
| Halo & Strategic Value | 20% | AI-scored: brand recognition + signaling value |
| Emerging Manager Fit | 15% | AI-scored: structural openness + documented programs |

**Composite** = (Sector × 0.35) + (Relationship × 0.30) + (Halo × 0.20) + (Emerging × 0.15)

**Tiers**: >= 8.0 PRIORITY CLOSE | >= 6.5 STRONG FIT | >= 5.0 MODERATE FIT | < 5.0 WEAK FIT

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
    ├── database.py      # SQLAlchemy models
    ├── ingest.py        # CSV ingestion with org dedup
    ├── enrichment.py    # AI web enrichment
    ├── scoring.py       # Scoring rubrics and composite logic
    ├── cost_tracker.py  # API cost tracking
    └── pipeline.py      # Orchestrator
```
