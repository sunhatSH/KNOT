"""Provider registry for managing LLM providers."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.config import settings
from knot.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for LLM providers.

    Allows registering providers by name and retrieving them at runtime.
    Supports lazy initialization of the default provider.
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        """Register an LLM provider."""
        self._providers[name] = provider
        logger.info("Registered LLM provider: %s", name)

    def get(self, name: str | None = None) -> LLMProvider:
        """Get a provider by name. Defaults to the configured provider."""
        provider_name = name or settings.llm_provider
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(
                f"LLM provider '{provider_name}' not registered. "
                f"Available: {list(self._providers)}"
            )
        return provider

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers)

    def __getitem__(self, name: str) -> LLMProvider:
        return self.get(name)


# Global registry instance
registry = ProviderRegistry()


def init_default_providers() -> None:
    """Initialize and register default providers based on configuration."""
    from knot.llm.deepseek import DeepSeekProvider

    if settings.deepseek_api_key:
        registry.register(
            "deepseek",
            DeepSeekProvider(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            ),
        )
        logger.info("Initialized DeepSeek provider")
    else:
        logger.warning("DEEPSEEK_API_KEY not set; DeepSeek provider not initialized")
