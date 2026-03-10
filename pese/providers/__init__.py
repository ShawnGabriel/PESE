from pese.providers.base import AIProvider
from pese.providers.openai import OpenAIProvider


def create_provider(provider_name: str = "openai", **kwargs) -> AIProvider:
    """Factory function to instantiate the configured AI provider."""
    providers = {
        "openai": OpenAIProvider,
    }

    provider_cls = providers.get(provider_name.lower())
    if provider_cls is None:
        available = ", ".join(providers.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")

    return provider_cls(**kwargs)
