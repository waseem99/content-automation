from __future__ import annotations

from decimal import Decimal

from src.domain.budget_models import ProviderPricing


class PricingNotFound(RuntimeError):
    pass


class PricingCatalog:
    def __init__(self, profiles: tuple[ProviderPricing, ...]) -> None:
        self._profiles = {(item.provider, item.operation, item.model_id): item for item in profiles}

    def find(self, *, provider: str, operation: str, model_id: str | None = None) -> ProviderPricing:
        key = (provider, operation, model_id)
        fallback = (provider, operation, None)
        profile = self._profiles.get(key) or self._profiles.get(fallback)
        if profile is None:
            raise PricingNotFound(f"Pricing not found for {provider}:{operation}:{model_id or 'default'}")
        return profile

    def estimate(self, *, provider: str, operation: str, model_id: str | None, units: Decimal) -> tuple[Decimal, ProviderPricing]:
        profile = self.find(provider=provider, operation=operation, model_id=model_id)
        return (profile.unit_cost_usd * units).quantize(Decimal("0.0001")), profile


def default_pricing_catalog() -> PricingCatalog:
    return PricingCatalog(
        (
            ProviderPricing(provider="openai", operation="image", model_id="standard", unit_name="image", unit_cost_usd=Decimal("0.0400")),
            ProviderPricing(provider="openai", operation="image", model_id="premium", unit_name="image", unit_cost_usd=Decimal("0.2000"), premium=True),
            ProviderPricing(provider="elevenlabs", operation="voice", model_id="standard", unit_name="minute", unit_cost_usd=Decimal("0.0300")),
            ProviderPricing(provider="serpapi", operation="search", model_id="standard", unit_name="query", unit_cost_usd=Decimal("0.0100")),
        )
    )
