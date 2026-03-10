"""Structured data models for enrichment and scoring results."""
from dataclasses import dataclass


@dataclass
class EnrichmentResult:
    """Structured output from AI-powered organization enrichment."""
    overview: str = ""
    is_lp: bool | None = None
    lp_evidence: str = ""
    has_credit_allocation: bool | None = None
    credit_evidence: str = ""
    has_sustainability_mandate: bool | None = None
    sustainability_evidence: str = ""
    aum_millions: float | None = None
    aum_source: str = ""
    brand_recognition: str = "unknown"
    brand_details: str = ""
    has_emerging_manager_program: bool | None = None
    emerging_manager_evidence: str = ""
    confidence: str = "low"
    key_findings: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "EnrichmentResult":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}

        aum = filtered.get("aum_millions")
        if aum is not None:
            try:
                filtered["aum_millions"] = float(aum)
            except (ValueError, TypeError):
                filtered["aum_millions"] = None

        return cls(**filtered)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def _clamp(val: float | None) -> float | None:
    if val is None:
        return None
    return max(1.0, min(10.0, float(val)))


@dataclass
class ScoringResult:
    """
    Structured output from AI-powered organization scoring.

    Each AI-scored dimension (D1, D3, D4) is broken into weighted sub-components
    for auditability and calibration.
    """

    # --- Dimension 1: Sector & Mandate Fit ---
    # Component A: LP Status (40%)
    d1_a_lp_status: float | None = None
    d1_a_reasoning: str = ""
    # Component B: Credit Allocation (30%)
    d1_b_credit: float | None = None
    d1_b_reasoning: str = ""
    # Component C: Sustainability Mandate (30%)
    d1_c_sustainability: float | None = None
    d1_c_reasoning: str = ""
    # Composite
    sector_fit_score: float | None = None
    sector_fit_reasoning: str = ""
    d1_confidence: str = "MEDIUM"

    # --- Dimension 3: Halo & Strategic Value ---
    # Component A: Brand Recognition (50%)
    d3_a_brand: float | None = None
    d3_a_reasoning: str = ""
    # Component B: Network Centrality (30%)
    d3_b_network: float | None = None
    d3_b_reasoning: str = ""
    # Component C: Signal Specificity (20%)
    d3_c_specificity: float | None = None
    d3_c_reasoning: str = ""
    # Composite
    halo_score: float | None = None
    halo_reasoning: str = ""
    d3_confidence: str = "MEDIUM"

    # --- Dimension 4: Emerging Manager Fit ---
    # Component A: Structural Openness (40%)
    d4_a_structural: float | None = None
    d4_a_reasoning: str = ""
    # Component B: Emerging Manager Track Record (40%)
    d4_b_track_record: float | None = None
    d4_b_reasoning: str = ""
    # Component C: Mission Alignment (20%)
    d4_c_mission: float | None = None
    d4_c_reasoning: str = ""
    # Composite
    emerging_manager_score: float | None = None
    emerging_manager_reasoning: str = ""
    d4_confidence: str = "MEDIUM"

    # Overall confidence
    confidence_note: str = ""

    def __post_init__(self):
        for attr in (
            "d1_a_lp_status", "d1_b_credit", "d1_c_sustainability", "sector_fit_score",
            "d3_a_brand", "d3_b_network", "d3_c_specificity", "halo_score",
            "d4_a_structural", "d4_b_track_record", "d4_c_mission", "emerging_manager_score",
        ):
            setattr(self, attr, _clamp(getattr(self, attr)))

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringResult":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class ProspectScore:
    """Final composite score for a contact-level prospect."""
    sector_fit: float | None = None
    relationship_depth: float | None = None
    halo_value: float | None = None
    emerging_manager_fit: float | None = None
    composite: float | None = None
    tier: str = "UNSCORED"
    check_size_low: float | None = None
    check_size_high: float | None = None
