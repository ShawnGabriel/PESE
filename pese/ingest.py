"""CSV ingestion with organization-level deduplication."""
import pandas as pd
from rich.console import Console

from pese.config import DATA_DIR
from pese.database import Contact, Organization, get_session, init_db
from pese.exceptions import IngestionError

console = Console()

REQUIRED_COLUMNS = {"Contact Name", "Organization"}


def normalize_org_name(name: str) -> str:
    """Normalize organization names for deduplication."""
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower().replace(",", "").replace(".", "").replace("llc", "").replace("inc", "").strip()


def load_csv(path: str | None = None) -> pd.DataFrame:
    """Load and validate the contacts CSV."""
    csv_path = path or str(DATA_DIR / "challenge_contacts.csv")

    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise IngestionError(f"CSV file not found: {csv_path}")
    except Exception as e:
        raise IngestionError(f"Failed to read CSV: {e}")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise IngestionError(f"CSV missing required columns: {missing}")

    df = df.dropna(subset=["Contact Name", "Organization"])
    df = df[df["Contact Name"].str.strip() != ""]
    df.columns = [c.strip() for c in df.columns]
    console.print(f"[green]Loaded {len(df)} contacts from CSV[/green]")
    return df


def ingest(csv_path: str | None = None) -> dict:
    """Ingest CSV into database with org-level deduplication. Returns summary stats."""
    init_db()
    df = load_csv(csv_path)
    session = get_session()

    org_cache: dict[str, Organization] = {}
    contacts_added = 0
    orgs_added = 0

    for _, row in df.iterrows():
        org_name = str(row["Organization"]).strip()
        org_key = normalize_org_name(org_name)

        if not org_key:
            continue

        if org_key not in org_cache:
            existing = session.query(Organization).filter(
                Organization.name == org_name
            ).first()
            if existing:
                org_cache[org_key] = existing
            else:
                org = Organization(
                    name=org_name,
                    org_type=str(row.get("Org Type", "")).strip() or None,
                    region=str(row.get("Region", "")).strip() or None,
                )
                session.add(org)
                session.flush()
                org_cache[org_key] = org
                orgs_added += 1

        org = org_cache[org_key]

        contact = Contact(
            name=str(row["Contact Name"]).strip(),
            organization_id=org.id,
            role=str(row.get("Role", "")).strip() or None,
            email=str(row.get("Email", "")).strip() or None,
            region=str(row.get("Region", "")).strip() or None,
            contact_status=str(row.get("Contact Status", "")).strip() or None,
            relationship_depth=float(row.get("Relationship Depth", 0)) if pd.notna(row.get("Relationship Depth")) else None,
        )
        session.add(contact)
        contacts_added += 1

    session.commit()
    session.close()

    summary = {
        "contacts_added": contacts_added,
        "unique_orgs": orgs_added,
        "total_orgs_in_db": len(org_cache),
    }
    console.print(f"[green]Ingested {contacts_added} contacts across {len(org_cache)} organizations ({orgs_added} new)[/green]")
    return summary
