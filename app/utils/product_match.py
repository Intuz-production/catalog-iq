"""
CatalogIQ — Competitor listing match scoring.

Ranks scraped marketplace results against catalog products using title
similarity, brand overlap, and plausible price range checks.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from app.config import settings
from app.models.schemas import Product
from app.utils.scraper import ScrapedProduct

STOP_WORDS = frozenset({
    "a", "an", "and", "for", "in", "of", "on", "the", "to", "with",
    "new", "pack", "set", "size", "color", "edition",
})

MIN_MATCH_SCORE = 0.15
PRICE_RATIO_MIN = 0.25
PRICE_RATIO_MAX = 4.0
SAVE_PRICE_RATIO_MIN = 0.15
SAVE_PRICE_RATIO_MAX = 6.0


def _tokenize(text: str) -> set[str]:
    """Tokenize product text for overlap scoring."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {token for token in tokens if token not in STOP_WORDS and len(token) > 1}


def title_similarity(reference: str, candidate: str) -> float:
    """Score how similar two product titles are (0.0 to 1.0)."""
    if not reference or not candidate:
        return 0.0

    tokens_ref = _tokenize(reference)
    tokens_candidate = _tokenize(candidate)
    if not tokens_ref or not tokens_candidate:
        return SequenceMatcher(None, reference.lower(), candidate.lower()).ratio()

    intersection = tokens_ref & tokens_candidate
    union = tokens_ref | tokens_candidate
    jaccard = len(intersection) / len(union)
    sequence = SequenceMatcher(None, reference.lower(), candidate.lower()).ratio()
    return (0.6 * jaccard) + (0.4 * sequence)


def normalize_listing_price(
    price: float,
    currency: str,
    product: Product,
) -> Optional[float]:
    """Normalize a competitor listing price into the product's currency."""
    if product.currency == currency:
        return price
    if currency == "INR" and product.currency == "USD":
        return price / settings.USD_INR_EXCHANGE_RATE
    if currency == "USD" and product.currency == "INR":
        return price * settings.USD_INR_EXCHANGE_RATE
    return None


def price_plausibility_score(normalized_price: float, our_price: float) -> float:
    """Score whether a competitor price is in a plausible range vs ours."""
    if our_price <= 0:
        return 0.5

    ratio = normalized_price / our_price
    if PRICE_RATIO_MIN <= ratio <= PRICE_RATIO_MAX:
        return 1.0
    if 0.1 <= ratio <= 10.0:
        return 0.35
    return 0.0


def score_listing(product: Product, listing: ScrapedProduct) -> float:
    """Compute an overall match score for a scraped listing."""
    brand = (product.brand or "").strip()
    title = (product.title or "").strip()
    reference = f"{brand} {title}".strip() if brand else title
    competitor_title = listing.title or ""

    title_score = title_similarity(reference, competitor_title)
    brand_bonus = 0.12 if brand and brand.lower() in competitor_title.lower() else 0.0

    price_component = 0.0
    if listing.price is not None and product.price:
        normalized = normalize_listing_price(
            listing.price,
            listing.currency,
            product,
        )
        if normalized is not None:
            price_component = price_plausibility_score(normalized, product.price) * 0.2

    return min(1.0, (title_score * 0.68) + brand_bonus + price_component)


def is_acceptable_competitor_price(
    product: Product,
    price: float,
    currency: str,
) -> bool:
    """Return True when a scraped price is plausible enough to persist."""
    if price <= 0:
        return False

    if not product.price or product.price <= 0:
        return True

    normalized = normalize_listing_price(price, currency, product)
    if normalized is None:
        return False

    ratio = normalized / product.price
    return SAVE_PRICE_RATIO_MIN <= ratio <= SAVE_PRICE_RATIO_MAX


def infer_listing_currency(
    price: float,
    currency: str,
    product: Product,
    marketplace_currency: str,
) -> str:
    """Correct mislabeled currencies (e.g. INR amounts saved as USD on Amazon)."""
    if (
        currency == marketplace_currency
        and product.currency == "USD"
        and marketplace_currency == "USD"
        and price > product.price * 8
        and is_acceptable_competitor_price(product, price, "INR")
    ):
        return "INR"

    return currency


def pick_best_listing(
    product: Product,
    listings: list[ScrapedProduct],
) -> tuple[Optional[ScrapedProduct], float]:
    """Pick the best-matching scraped listing for a catalog product.

    Returns:
        Tuple of (best listing or None, match score).
    """
    if not listings:
        return None, 0.0

    scored = [(score_listing(product, listing), listing) for listing in listings]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_listing = scored[0]

    if best_score < MIN_MATCH_SCORE:
        return None, best_score

    return best_listing, best_score
