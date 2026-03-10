"""Structured data models for enrichment and scoring results."""
from dataclasses import dataclass, field


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


@dataclass
class ScoringResult:
    """Structured output from AI-powered organization scoring."""
    sector_fit_score: float | None = None
    sector_fit_reasoning: str = ""
    halo_score: float | None = None
    halo_reasoning: str = ""
    emerging_manager_score: float | None = None
    emerging_manager_reasoning: str = ""

    def __post_init__(self):
        for attr in ("sector_fit_score", "halo_score", "emerging_manager_score"):
            val = getattr(self, attr)
            if val is not None:
                setattr(self, attr, max(1.0, min(10.0, float(val))))

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
