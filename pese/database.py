"""Database models and session management."""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    ForeignKey, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from pese.config import DATABASE_URL

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    org_type = Column(String)
    region = Column(String)

    enrichment_summary = Column(Text)
    aum_millions = Column(Float, nullable=True)
    is_lp = Column(Boolean, nullable=True)
    has_credit_allocation = Column(Boolean, nullable=True)
    has_sustainability_mandate = Column(Boolean, nullable=True)
    has_emerging_manager_program = Column(Boolean, nullable=True)

    # D1: Sector & Mandate Fit — sub-components
    d1_a_lp_status = Column(Float, nullable=True)
    d1_a_reasoning = Column(Text)
    d1_b_credit = Column(Float, nullable=True)
    d1_b_reasoning = Column(Text)
    d1_c_sustainability = Column(Float, nullable=True)
    d1_c_reasoning = Column(Text)
    sector_fit_score = Column(Float, nullable=True)
    sector_fit_reasoning = Column(Text)
    d1_confidence = Column(String, nullable=True)

    # D3: Halo & Strategic Value — sub-components
    d3_a_brand = Column(Float, nullable=True)
    d3_a_reasoning = Column(Text)
    d3_b_network = Column(Float, nullable=True)
    d3_b_reasoning = Column(Text)
    d3_c_specificity = Column(Float, nullable=True)
    d3_c_reasoning = Column(Text)
    halo_score = Column(Float, nullable=True)
    halo_reasoning = Column(Text)
    d3_confidence = Column(String, nullable=True)

    # D4: Emerging Manager Fit — sub-components
    d4_a_structural = Column(Float, nullable=True)
    d4_a_reasoning = Column(Text)
    d4_b_track_record = Column(Float, nullable=True)
    d4_b_reasoning = Column(Text)
    d4_c_mission = Column(Float, nullable=True)
    d4_c_reasoning = Column(Text)
    emerging_manager_score = Column(Float, nullable=True)
    emerging_manager_reasoning = Column(Text)
    d4_confidence = Column(String, nullable=True)

    estimated_check_size_low = Column(Float, nullable=True)
    estimated_check_size_high = Column(Float, nullable=True)
    confidence = Column(String, nullable=True)

    enriched_at = Column(DateTime, nullable=True)
    enrichment_cost_usd = Column(Float, default=0.0)

    contacts = relationship("Contact", back_populates="organization")

    def apply_enrichment(self, enrichment: "EnrichmentResult", cost_usd: float = 0.0) -> None:
        """Apply structured enrichment data to this organization."""
        from pese.models import EnrichmentResult
        self.enrichment_summary = json.dumps(enrichment.to_dict())
        self.is_lp = enrichment.is_lp
        self.has_credit_allocation = enrichment.has_credit_allocation
        self.has_sustainability_mandate = enrichment.has_sustainability_mandate
        self.has_emerging_manager_program = enrichment.has_emerging_manager_program
        self.aum_millions = enrichment.aum_millions
        self.confidence = enrichment.confidence
        self.enrichment_cost_usd = cost_usd
        self.enriched_at = datetime.now(timezone.utc)

    def apply_scores(self, scores: "ScoringResult") -> None:
        """Apply structured scoring data including sub-components."""
        from pese.models import ScoringResult

        # D1 sub-components
        self.d1_a_lp_status = scores.d1_a_lp_status
        self.d1_a_reasoning = scores.d1_a_reasoning
        self.d1_b_credit = scores.d1_b_credit
        self.d1_b_reasoning = scores.d1_b_reasoning
        self.d1_c_sustainability = scores.d1_c_sustainability
        self.d1_c_reasoning = scores.d1_c_reasoning
        self.sector_fit_score = scores.sector_fit_score
        self.sector_fit_reasoning = scores.sector_fit_reasoning
        self.d1_confidence = scores.d1_confidence

        # D3 sub-components
        self.d3_a_brand = scores.d3_a_brand
        self.d3_a_reasoning = scores.d3_a_reasoning
        self.d3_b_network = scores.d3_b_network
        self.d3_b_reasoning = scores.d3_b_reasoning
        self.d3_c_specificity = scores.d3_c_specificity
        self.d3_c_reasoning = scores.d3_c_reasoning
        self.halo_score = scores.halo_score
        self.halo_reasoning = scores.halo_reasoning
        self.d3_confidence = scores.d3_confidence

        # D4 sub-components
        self.d4_a_structural = scores.d4_a_structural
        self.d4_a_reasoning = scores.d4_a_reasoning
        self.d4_b_track_record = scores.d4_b_track_record
        self.d4_b_reasoning = scores.d4_b_reasoning
        self.d4_c_mission = scores.d4_c_mission
        self.d4_c_reasoning = scores.d4_c_reasoning
        self.emerging_manager_score = scores.emerging_manager_score
        self.emerging_manager_reasoning = scores.emerging_manager_reasoning
        self.d4_confidence = scores.d4_confidence

    def apply_check_size(self, low: float | None, high: float | None) -> None:
        """Set estimated check size range."""
        self.estimated_check_size_low = low
        self.estimated_check_size_high = high

    @property
    def is_enriched(self) -> bool:
        return self.enriched_at is not None


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    role = Column(String)
    email = Column(String)
    region = Column(String)
    contact_status = Column(String)
    relationship_depth = Column(Float)

    composite_score = Column(Float, nullable=True)
    tier = Column(String, nullable=True)

    organization = relationship("Organization", back_populates="contacts")

    def apply_composite(self, composite: float | None, tier: str) -> None:
        """Set the computed composite score and tier classification."""
        self.composite_score = composite
        self.tier = tier


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    total_orgs_enriched = Column(Integer, default=0)
    total_contacts_scored = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    status = Column(String, default="running")

    def mark_complete(self, orgs_enriched: int, contacts_scored: int, cost_usd: float) -> None:
        self.finished_at = datetime.now(timezone.utc)
        self.total_orgs_enriched = orgs_enriched
        self.total_contacts_scored = contacts_scored
        self.total_cost_usd = cost_usd
        self.status = "completed"


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
