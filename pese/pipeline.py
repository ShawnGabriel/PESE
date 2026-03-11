"""
Pipeline orchestrator: coordinates ingestion, enrichment, scoring, and persistence.

Uses the AIProvider interface so the LLM backend is swappable.
Supports resumability — skips organizations that are already enriched.
"""
import logging
import time
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

from pese.config import AI_PROVIDER
from pese.cost_tracker import CostTracker
from pese.database import Contact, Organization, RunLog, get_session, init_db
from pese.exceptions import EnrichmentError, ScoringError
from pese.providers import create_provider
from pese.providers.base import AIProvider
from pese.scoring import classify_tier, compute_composite, estimate_check_size

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(
    csv_path: str | None = None,
    skip_enriched: bool = True,
    limit: int | None = None,
    provider: AIProvider | None = None,
) -> dict:
    """
    Run the full enrichment + scoring pipeline.

    Args:
        csv_path: Path to contacts CSV (uses default if None).
        skip_enriched: Skip orgs that already have enrichment data.
        limit: Max number of orgs to enrich (for testing/cost control).
        provider: AI provider instance (created from config if None).

    Returns:
        Summary dict with stats and costs.
    """
    init_db()
    session = get_session()

    from pese.ingest import ingest
    ingest_stats = ingest(csv_path)

    if provider is None:
        provider = create_provider(AI_PROVIDER)

    run_log = RunLog(status="running")
    session.add(run_log)
    session.commit()

    cost_tracker = CostTracker()

    orgs = session.query(Organization).all()
    if skip_enriched:
        orgs = [o for o in orgs if not o.is_enriched]

    if limit:
        orgs = orgs[:limit]

    console.print(f"\n[bold]Enriching and scoring {len(orgs)} organizations via [{provider.name}]...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing organizations", total=len(orgs))

        for org in orgs:
            progress.update(task, description=f"[cyan]{org.name[:40]}[/cyan]")
            try:
                _process_organization(session, org, provider, cost_tracker)
            except (EnrichmentError, ScoringError) as e:
                logger.error(str(e))
                console.print(f"  [red]{e}[/red]")
            except Exception as e:
                logger.error(f"Unexpected error for {org.name}: {e}")
                console.print(f"  [red]Error: {org.name} — {e}[/red]")

            progress.advance(task)
            time.sleep(0.5)

    _compute_contact_scores(session)

    scored_count = session.query(Contact).filter(Contact.composite_score.isnot(None)).count()
    run_log.mark_complete(
        orgs_enriched=len(orgs),
        contacts_scored=scored_count,
        cost_usd=cost_tracker.total_cost,
    )
    session.commit()

    summary = {
        **ingest_stats,
        "orgs_enriched": len(orgs),
        "cost": cost_tracker.summary(),
        "projected_cost_1000_orgs": cost_tracker.projected_cost(1000),
    }

    _print_summary(session, summary, cost_tracker)
    session.close()
    return summary


def _process_organization(
    session,
    org: Organization,
    provider: AIProvider,
    cost_tracker: CostTracker,
) -> None:
    """Enrich and score a single organization through the provider interface."""
    enrichment = provider.enrich(
        org_name=org.name,
        org_type=org.org_type or "",
        region=org.region or "",
        cost_tracker=cost_tracker,
    )

    org.apply_enrichment(enrichment, cost_usd=cost_tracker.calls[-1]["cost_usd"] if cost_tracker.calls else 0)

    scores = provider.score(
        org_name=org.name,
        org_type=org.org_type or "",
        region=org.region or "",
        enrichment=enrichment,
        cost_tracker=cost_tracker,
    )

    org.apply_scores(scores)

    low, high = estimate_check_size(org.aum_millions, org.org_type)
    org.apply_check_size(low, high)

    session.commit()


def _compute_contact_scores(session) -> None:
    """Compute composite scores and tiers for all contacts based on their org's scores.

    Only contacts whose organization has been enriched receive a composite score.
    Unenriched contacts are left as UNSCORED to avoid artificially ranking them
    based on relationship depth alone.
    """
    contacts = session.query(Contact).all()
    for contact in contacts:
        org = contact.organization
        if org is None:
            continue

        if not org.is_enriched:
            contact.apply_composite(None, "UNSCORED")
            continue

        composite = compute_composite(
            sector_fit=org.sector_fit_score,
            relationship_depth=contact.relationship_depth,
            halo=org.halo_score,
            emerging=org.emerging_manager_score,
        )
        contact.apply_composite(composite, classify_tier(composite))

    session.commit()


def _print_summary(session, summary: dict, cost_tracker: CostTracker) -> None:
    """Print a rich summary table."""
    console.print("\n")
    console.rule("[bold green]Pipeline Complete[/bold green]")

    table = Table(title="Run Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Contacts ingested", str(summary.get("contacts_added", "—")))
    table.add_row("Unique organizations", str(summary.get("total_orgs_in_db", "—")))
    table.add_row("Orgs enriched this run", str(summary.get("orgs_enriched", "—")))
    table.add_row("API calls", str(cost_tracker.total_calls))
    table.add_row("Total tokens", f"{cost_tracker.total_input_tokens + cost_tracker.total_output_tokens:,}")
    table.add_row("Run cost (USD)", f"${cost_tracker.total_cost:.4f}")
    table.add_row("Projected cost (1,000 orgs)", f"${summary.get('projected_cost_1000_orgs', 0):.2f}")
    console.print(table)

    top = (
        session.query(Contact)
        .filter(Contact.composite_score.isnot(None))
        .order_by(Contact.composite_score.desc())
        .limit(15)
        .all()
    )

    if top:
        t2 = Table(title="Top 15 Prospects")
        t2.add_column("#", style="dim")
        t2.add_column("Contact")
        t2.add_column("Organization")
        t2.add_column("Sector", justify="right")
        t2.add_column("Rel.", justify="right")
        t2.add_column("Halo", justify="right")
        t2.add_column("Emrg.", justify="right")
        t2.add_column("Composite", justify="right", style="bold")
        t2.add_column("Tier", style="bold")

        for i, c in enumerate(top, 1):
            org = c.organization
            tier_color = {
                "PRIORITY CLOSE": "green",
                "STRONG FIT": "blue",
                "MODERATE FIT": "yellow",
                "WEAK FIT": "red",
            }.get(c.tier, "white")

            t2.add_row(
                str(i),
                c.name,
                org.name if org else "—",
                f"{org.sector_fit_score:.1f}" if org and org.sector_fit_score else "—",
                f"{c.relationship_depth:.1f}" if c.relationship_depth else "—",
                f"{org.halo_score:.1f}" if org and org.halo_score else "—",
                f"{org.emerging_manager_score:.1f}" if org and org.emerging_manager_score else "—",
                f"{c.composite_score:.1f}" if c.composite_score else "—",
                f"[{tier_color}]{c.tier}[/{tier_color}]",
            )

        console.print(t2)

    _run_validation(session)


def _run_validation(session) -> None:
    """Flag scoring anomalies and org-type conflicts for review."""
    console.print("\n[bold yellow]Validation Checks[/bold yellow]")
    score_issues: list[str] = []
    type_conflicts: list[str] = []

    for org in session.query(Organization).filter(Organization.enriched_at.isnot(None)).all():
        if org.is_lp is False and org.sector_fit_score and org.sector_fit_score > 5:
            score_issues.append(f"  {org.name}: flagged non-LP but sector_fit={org.sector_fit_score:.1f}")

        if org.is_lp is True and org.sector_fit_score and org.sector_fit_score < 3:
            score_issues.append(f"  {org.name}: flagged LP but sector_fit={org.sector_fit_score:.1f}")

        if org.enriched_org_type and org.org_type:
            csv_type = (org.org_type or "").strip().lower()
            enriched_type = (org.enriched_org_type or "").strip().lower()
            if csv_type and enriched_type and csv_type != enriched_type:
                note = org.org_type_conflict_note or "no details"
                type_conflicts.append(
                    f"  {org.name}: CSV='{org.org_type}' vs AI='{org.enriched_org_type}' — {note}"
                )

    if score_issues:
        console.print("[yellow]Score anomalies:[/yellow]")
        for issue in sorted(score_issues):
            console.print(f"[yellow]{issue}[/yellow]")
    else:
        console.print("  [green]No score anomalies detected[/green]")

    if type_conflicts:
        console.print(f"\n[yellow]Org-type conflicts ({len(type_conflicts)}):[/yellow]")
        for conflict in sorted(type_conflicts):
            console.print(f"[yellow]{conflict}[/yellow]")
    else:
        console.print("  [green]No org-type conflicts detected[/green]")
