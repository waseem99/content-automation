from decimal import Decimal

import pytest

from src.application.budget.metadata_filter import MASK, scrub_metadata
from src.application.budget.pricing import PricingCatalog, PricingNotFound
from src.domain.budget_models import ProviderPricing


def test_pricing_estimate_uses_provider_operation_and_model():
    catalog = PricingCatalog((ProviderPricing(provider="p", operation="op", model_id="m", unit_name="unit", unit_cost_usd=Decimal("0.2500")),))
    estimate, profile = catalog.estimate(provider="p", operation="op", model_id="m", units=Decimal("2"))
    assert estimate == Decimal("0.5000")
    assert profile.unit_name == "unit"


def test_unknown_pricing_is_not_zero():
    catalog = PricingCatalog(())
    with pytest.raises(PricingNotFound):
        catalog.estimate(provider="missing", operation="op", model_id=None, units=Decimal("1"))


def test_metadata_filter_masks_sensitive_fields():
    cleaned = scrub_metadata({"credential_value": "abc", "safe": {"name": "ok"}})
    assert cleaned["credential_value"] == MASK
    assert cleaned["safe"]["name"] == "ok"
