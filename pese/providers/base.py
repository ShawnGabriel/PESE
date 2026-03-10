"""Abstract base class for AI providers used in enrichment and scoring."""
from abc import ABC, abstractmethod

from pese.cost_tracker import CostTracker
from pese.models import EnrichmentResult, ScoringResult


class AIProvider(ABC):
    """
    Interface for AI-powered enrichment and scoring.

    Implementations must handle their own API auth, rate limiting,
    and retry logic. Results are returned as structured dataclasses
    so the pipeline is decoupled from any specific provider's response format.
    """

    @abstractmethod
    def enrich(
        self,
        org_name: str,
        org_type: str,
        region: str,
        cost_tracker: CostTracker | None = None,
    ) -> EnrichmentResult:
        """
        Research an organization using web search and return structured findings.

        Raises:
            EnrichmentError: If enrichment fails after retries.
        """

    @abstractmethod
    def score(
        self,
        org_name: str,
        org_type: str,
        region: str,
        enrichment: EnrichmentResult,
        cost_tracker: CostTracker | None = None,
    ) -> ScoringResult:
        """
        Score an organization across dimensions 1, 3, and 4 using enrichment data.

        Raises:
            ScoringError: If scoring fails after retries.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
