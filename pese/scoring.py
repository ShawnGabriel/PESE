"""
Pure scoring logic — no AI/API calls.

Handles composite score computation, tier classification, and check-size estimation.
AI-powered dimension scoring lives in the providers/ layer.
"""
from pese.config import SCORING_WEIGHTS, TIER_THRESHOLDS, ALLOCATION_RANGES


def compute_composite(
    sector_fit: float | None,
    relationship_depth: float | None,
    halo: float | None,
    emerging: float | None,
) -> float | None:
    """
    Weighted composite score.

    If all dimensions are present, uses exact weights.
    If some are missing, normalizes across available dimensions.
    Returns None if no dimensions are present.
    """
    weights = list(SCORING_WEIGHTS.values())
    values = [sector_fit, relationship_depth, halo, emerging]

    present = [(v, w) for v, w in zip(values, weights) if v is not None]
    if not present:
        return None

    total_weight = sum(w for _, w in present)
    return round(sum(v * w for v, w in present) / total_weight, 2)


def classify_tier(composite: float | None) -> str:
    """Map a composite score to a tier label."""
    if composite is None:
        return "UNSCORED"
    for threshold, tier in TIER_THRESHOLDS:
        if composite >= threshold:
            return tier
    return "WEAK FIT"


def estimate_check_size(
    aum_millions: float | None,
    org_type: str | None,
) -> tuple[float | None, float | None]:
    """Estimate likely commitment range (in $M) based on AUM and org-type allocation norms."""
    if aum_millions is None or org_type is None:
        return None, None
    low_pct, high_pct = ALLOCATION_RANGES.get(org_type, (0.01, 0.03))
    return round(aum_millions * low_pct, 2), round(aum_millions * high_pct, 2)
