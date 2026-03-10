"""
PESE — LP Prospect Enrichment & Scoring Engine
CLI entry point.
"""
import argparse
import logging
import sys

from pese.database import init_db


def main():
    parser = argparse.ArgumentParser(
        description="PESE — LP Prospect Enrichment & Scoring Engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest contacts from CSV")
    ingest_parser.add_argument("--csv", type=str, default=None, help="Path to contacts CSV")

    # run
    run_parser = subparsers.add_parser("run", help="Run full enrichment + scoring pipeline")
    run_parser.add_argument("--csv", type=str, default=None, help="Path to contacts CSV")
    run_parser.add_argument("--limit", type=int, default=None, help="Max orgs to enrich (for testing)")
    run_parser.add_argument("--no-skip", action="store_true", help="Re-enrich already-enriched orgs")

    # dashboard
    subparsers.add_parser("dashboard", help="Launch Streamlit dashboard")

    # reset
    subparsers.add_parser("reset", help="Reset the database")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "ingest":
        from pese.ingest import ingest
        ingest(args.csv)

    elif args.command == "run":
        from pese.pipeline import run_pipeline
        run_pipeline(
            csv_path=args.csv,
            skip_enriched=not args.no_skip,
            limit=args.limit,
        )

    elif args.command == "dashboard":
        import subprocess
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "dashboard.py",
            "--server.headless", "true",
        ])

    elif args.command == "reset":
        from pese.config import DB_PATH
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"Deleted {DB_PATH}")
        init_db()
        print("Database reset.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
