"""
CatalogIQ — Marketplace configuration loaded from environment variables.

Set SCRAPE_REGION to us or in — applies to scraping, alerts, and prices app-wide.
Optional per-marketplace URL overrides via MARKETPLACE_<SOURCE>_* env vars.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

VALID_REGIONS: Final[tuple[str, ...]] = ("us", "in")


@dataclass(frozen=True)
class MarketplaceConfig:
    """Configuration for a single competitor marketplace."""

    id: str
    platform: str
    label: str
    search_url_template: str
    base_url: str
    currency: str

    def build_search_url(self, query: str) -> str:
        """Build a marketplace search URL for the given query."""
        encoded_query = query.replace(" ", "+")
        return self.search_url_template.format(query=encoded_query)

    def build_product_url(self, path: str) -> str:
        """Build an absolute product URL from a relative path."""
        if path.startswith("http"):
            return path
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


REGION_PRESETS: dict[str, dict[str, MarketplaceConfig]] = {
    "us": {
        "amazon": MarketplaceConfig(
            id="amazon",
            platform="Amazon",
            label="Amazon US",
            search_url_template="https://www.amazon.com/s?k={query}",
            base_url="https://www.amazon.com",
            currency="USD",
        ),
        "walmart": MarketplaceConfig(
            id="walmart",
            platform="Walmart",
            label="Walmart US",
            search_url_template="https://www.walmart.com/search?q={query}",
            base_url="https://www.walmart.com",
            currency="USD",
        ),
        # eBay and Target are disabled for US until Browse API / Playwright support is added.
        # Scrapers remain in app/utils/scraper.py for future re-enable.
    },
    "in": {
        "amazon": MarketplaceConfig(
            id="amazon",
            platform="Amazon",
            label="Amazon India",
            search_url_template="https://www.amazon.in/s?k={query}",
            base_url="https://www.amazon.in",
            currency="INR",
        ),
        "flipkart": MarketplaceConfig(
            id="flipkart",
            platform="Flipkart",
            label="Flipkart",
            search_url_template="https://www.flipkart.com/search?q={query}",
            base_url="https://www.flipkart.com",
            currency="INR",
        ),
    },
}


def _normalize_region(region: str) -> str:
    """Normalize and validate SCRAPE_REGION."""
    normalized = region.strip().lower()
    if normalized not in VALID_REGIONS:
        raise ValueError(
            f"Invalid SCRAPE_REGION '{region}'. Must be one of: {', '.join(VALID_REGIONS)}"
        )
    return normalized


def _apply_env_overrides(config: MarketplaceConfig) -> MarketplaceConfig:
    """Apply MARKETPLACE_<SOURCE>_* env overrides to a preset config."""
    prefix = f"MARKETPLACE_{config.id.upper()}_"
    search_url = os.getenv(f"{prefix}SEARCH_URL", config.search_url_template)
    base_url = os.getenv(f"{prefix}BASE_URL", config.base_url)
    currency = os.getenv(f"{prefix}CURRENCY", config.currency)
    label = os.getenv(f"{prefix}LABEL", config.label)
    platform = os.getenv(f"{prefix}PLATFORM", config.platform)

    return MarketplaceConfig(
        id=config.id,
        platform=platform,
        label=label,
        search_url_template=search_url,
        base_url=base_url,
        currency=currency,
    )


def load_marketplace_settings(
    region: str | None = None,
) -> tuple[str, list[str], dict[str, MarketplaceConfig]]:
    """Load region and all marketplaces for that region from env.

    Returns:
        Tuple of (region, enabled_source_ids, marketplace_config_map).
    """
    resolved_region = _normalize_region(region or os.getenv("SCRAPE_REGION", "us"))
    preset = REGION_PRESETS[resolved_region]
    enabled_sources = list(preset.keys())
    marketplaces = {
        source_id: _apply_env_overrides(preset[source_id])
        for source_id in enabled_sources
    }

    return resolved_region, enabled_sources, marketplaces
