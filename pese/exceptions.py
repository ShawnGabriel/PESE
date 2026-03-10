"""Custom exceptions for the PESE pipeline."""


class PESEError(Exception):
    """Base exception for all PESE errors."""


class IngestionError(PESEError):
    """Raised when CSV ingestion fails (missing columns, bad data, etc.)."""


class EnrichmentError(PESEError):
    """Raised when AI-powered enrichment fails for an organization."""

    def __init__(self, org_name: str, message: str):
        self.org_name = org_name
        super().__init__(f"Enrichment failed for '{org_name}': {message}")


class ScoringError(PESEError):
    """Raised when scoring fails for an organization."""

    def __init__(self, org_name: str, message: str):
        self.org_name = org_name
        super().__init__(f"Scoring failed for '{org_name}': {message}")


class ProviderError(PESEError):
    """Raised when an AI provider encounters a configuration or API error."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"Provider '{provider}' error: {message}")
