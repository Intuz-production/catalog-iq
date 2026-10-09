"""
CatalogIQ — Web Scraping Utilities

Base scraping functions for competitor marketplace monitoring.
Uses httpx for async HTTP and BeautifulSoup for HTML parsing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.config.marketplaces import MarketplaceConfig

logger = logging.getLogger("catalogiq.scraper")

CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

RETRYABLE_STATUS_CODES = frozenset({403, 429, 503})
BOT_PAGE_MARKERS = (
    "captcha",
    "robot",
    "automated access",
    "access denied",
    "sorry, something went wrong",
)

_active_session: ContextVar[ScrapeSession | None] = ContextVar("scrape_session", default=None)


@dataclass
class ScrapedProduct:
    """Data structure for a scraped competitor product."""
    title: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    in_stock: bool = True
    url: Optional[str] = None
    source: str = ""
    is_simulated: bool = False
    match_score: Optional[float] = None


class ScrapeSession:
    """Shared HTTP client for a competitor scrape batch."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ScrapeSession:
        self._client = httpx.AsyncClient(
            headers=build_browser_headers(),
            follow_redirects=True,
            timeout=settings.SCRAPE_REQUEST_TIMEOUT,
        )
        _active_session.set(self)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
        _active_session.set(None)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ScrapeSession is not active")
        return self._client

    async def delay(self) -> None:
        """Pause between marketplace requests to reduce rate limiting."""
        delay_ms = settings.SCRAPE_DELAY_MS
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)


def build_browser_headers(referer: Optional[str] = None) -> dict[str, str]:
    """Build browser-like HTTP headers for marketplace requests."""
    headers = {
        "User-Agent": CHROME_USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def referer_for_url(url: str) -> str:
    """Derive a marketplace referer from a target URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def is_bot_or_blocked_page(html: str, source: str) -> bool:
    """Detect bot-wall or empty responses that should not be parsed."""
    if not html:
        return True

    result_markers: dict[str, tuple[str, ...]] = {
        "amazon": ("s-search-result",),
        "walmart": ("data-item-id", "product-title", "__NEXT_DATA__"),
        "ebay": ("s-item",),
        "target": ("product-card",),
        "flipkart": ("tUxRFH", "_4rR01T"),
    }
    markers = result_markers.get(source, ())
    if any(marker in html for marker in markers):
        return False

    sample = html[:12_000].lower()
    if any(marker in sample for marker in BOT_PAGE_MARKERS):
        return True

    return len(html) < 50_000


async def fetch_page(
    url: str,
    timeout: Optional[int] = None,
    source: Optional[str] = None,
) -> Optional[str]:
    """Fetch a web page with retries and shared session support."""
    request_timeout = timeout if timeout is not None else settings.SCRAPE_REQUEST_TIMEOUT
    referer = referer_for_url(url)
    session = _active_session.get()
    max_attempts = settings.SCRAPE_MAX_RETRIES + 1

    for attempt in range(1, max_attempts + 1):
        try:
            if session is not None:
                await session.delay()
                response = await session.client.get(
                    url,
                    headers=build_browser_headers(referer),
                    timeout=request_timeout,
                )
            else:
                async with httpx.AsyncClient(
                    headers=build_browser_headers(referer),
                    follow_redirects=True,
                    timeout=request_timeout,
                ) as client:
                    response = await client.get(url)

            if response.status_code in RETRYABLE_STATUS_CODES:
                logger.warning(
                    "HTTP %s fetching %s (attempt %s/%s)",
                    response.status_code,
                    url,
                    attempt,
                    max_attempts,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(attempt * settings.SCRAPE_RETRY_BACKOFF_SEC)
                    continue
                return None

            response.raise_for_status()
            html = response.text

            if source and is_bot_or_blocked_page(html, source):
                logger.warning(
                    "Blocked or empty %s page for %s (attempt %s/%s, len=%s)",
                    source,
                    url,
                    attempt,
                    max_attempts,
                    len(html),
                )
                if attempt < max_attempts:
                    await asyncio.sleep(attempt * settings.SCRAPE_RETRY_BACKOFF_SEC)
                    continue
                return None

            return html

        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP error fetching %s: %s", url, exc.response.status_code)
            if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                await asyncio.sleep(attempt * settings.SCRAPE_RETRY_BACKOFF_SEC)
                continue
        except httpx.RequestError as exc:
            logger.warning("Request error fetching %s: %s", url, exc)
            if attempt < max_attempts:
                await asyncio.sleep(attempt * settings.SCRAPE_RETRY_BACKOFF_SEC)
                continue
        except Exception as exc:
            logger.error("Unexpected error fetching %s: %s", url, exc)
            break

    return None


def detect_currency_from_text(text: str, default: str = "USD") -> str:
    """Infer listing currency from price text."""
    if not text:
        return default
    if "₹" in text or re.search(r"\bRs\.?\b", text, re.IGNORECASE):
        return "INR"
    if "$" in text or "USD" in text.upper():
        return "USD"
    return default


def parse_price_value(text: str, default_currency: str = "USD") -> tuple[Optional[float], str]:
    """Extract numeric price and currency from a price string."""
    currency = detect_currency_from_text(text, default_currency)
    return extract_price(text), currency


def extract_price(text: str) -> Optional[float]:
    """Extract a numeric price from text."""
    if not text:
        return None
    match = re.search(r"\d[\d,.]*", text)
    if not match:
        return None

    num_str = match.group(0).rstrip(".")
    num_str = num_str.replace(",", "")
    try:
        return float(num_str)
    except ValueError:
        return None


def _extract_amazon_title(item: BeautifulSoup) -> Optional[str]:
    """Extract product title from an Amazon search result card."""
    recipe = item.select_one("[data-cy='title-recipe']")
    if recipe and recipe.get_text(strip=True):
        return recipe.get_text(strip=True)

    link_span = item.select_one("a.a-link-normal span")
    if link_span and link_span.get_text(strip=True):
        brand_el = item.select_one("h2 span")
        brand = brand_el.get_text(strip=True) if brand_el else ""
        title = link_span.get_text(strip=True)
        if brand and brand.lower() not in title.lower():
            return f"{brand} {title}".strip()
        return title

    for selector in ("h2 span", "span.a-text-normal", "h2 a"):
        element = item.select_one(selector)
        if element and element.get_text(strip=True):
            return element.get_text(strip=True)

    return None


def _extract_amazon_price(item: BeautifulSoup, default_currency: str) -> tuple[Optional[float], str]:
    """Extract product price and currency from an Amazon search result card."""
    offscreen = item.select_one("span.a-offscreen")
    if offscreen and offscreen.get_text(strip=True):
        return parse_price_value(offscreen.get_text(strip=True), default_currency)

    price_whole = item.select_one("span.a-price-whole")
    if price_whole:
        whole_text = price_whole.get_text(strip=True).rstrip(".")
        price_frac = item.select_one("span.a-price-fraction")
        symbol = item.select_one("span.a-price-symbol")
        symbol_text = symbol.get_text(strip=True) if symbol else ""
        if price_frac:
            price_text = f"{symbol_text}{whole_text}.{price_frac.get_text(strip=True)}"
        else:
            price_text = f"{symbol_text}{whole_text}"
        return parse_price_value(price_text, default_currency)

    return None, default_currency


def _normalize_walmart_price_text(text: str) -> Optional[float]:
    """Normalize Walmart prices that omit the decimal separator (e.g. $13495)."""
    if not text:
        return None

    if "." in text:
        return extract_price(text)

    raw = extract_price(text.replace("$", ""))
    if raw is None:
        return None

    # Walmart often renders cents as trailing digits without a decimal point.
    if raw >= 1000:
        return round(raw / 100, 2)

    return raw


def _extract_walmart_price(item: BeautifulSoup) -> Optional[float]:
    """Extract product price from a Walmart search result card."""
    for selector in (
        "[data-automation-id='product-price']",
        "div[data-automation-id='product-price'] span",
        "span[data-automation-id='product-price']",
    ):
        element = item.select_one(selector)
        if element:
            price = _normalize_walmart_price_text(element.get_text(strip=True))
            if price is not None:
                return price

    characteristic = item.select_one("span[class*='price-characteristic']")
    mantissa = item.select_one("span[class*='price-mantissa']")
    if characteristic and mantissa:
        return extract_price(
            f"{characteristic.get_text(strip=True)}.{mantissa.get_text(strip=True)}"
        )

    price_prop = item.select_one("[itemprop='price']")
    if price_prop:
        content = price_prop.get("content") or price_prop.get_text(strip=True)
        price = _normalize_walmart_price_text(str(content))
        if price is not None:
            return price

    for match in re.finditer(r"\$\s*([\d,]+)(?:\.(\d{2}))?", item.get_text()):
        if match.group(2):
            price = extract_price(f"{match.group(1)}.{match.group(2)}")
        else:
            price = _normalize_walmart_price_text(f"${match.group(1)}")
        if price is not None and price < 100_000:
            return price

    return None


def _parse_walmart_json_ld(soup: BeautifulSoup) -> list[ScrapedProduct]:
    """Parse Walmart search results from JSON-LD blocks when present."""
    products: list[ScrapedProduct] = []
    for script in soup.select("script[type='application/ld+json']"):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        items = payload if isinstance(payload, list) else [payload]
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if entry.get("@type") != "Product":
                continue
            offers = entry.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = extract_price(str(offers.get("price", "")))
            products.append(
                ScrapedProduct(
                    title=entry.get("name"),
                    price=price,
                    currency=str(offers.get("priceCurrency") or "USD"),
                    url=entry.get("url"),
                    source="walmart",
                )
            )
    return products


def get_marketplace_config(source: str) -> MarketplaceConfig:
    """Resolve marketplace configuration for a source ID."""
    marketplace = settings.marketplaces.get(source.lower())
    if marketplace is None:
        raise KeyError(
            f"Marketplace source '{source}' is not available for region '{settings.scrape_region}'"
        )
    return marketplace


def build_search_url(query: str, source: str) -> str:
    """Build a marketplace search URL for a product query."""
    return get_marketplace_config(source).build_search_url(query)


async def scrape_amazon(query: str) -> list[ScrapedProduct]:
    """Scrape Amazon search results for product listings."""
    marketplace = get_marketplace_config("amazon")
    url = marketplace.build_search_url(query)
    html = await fetch_page(url, source="amazon")
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning("Failed to fetch Amazon results for: %s", query)
        return products

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div[data-component-type='s-search-result']")
    for item in items[:5]:
        try:
            title = _extract_amazon_title(item)
            price, currency = _extract_amazon_price(item, marketplace.currency)
            link_el = item.select_one("a.a-link-normal[href]") or item.select_one("h2 a")

            product_url = None
            if link_el and link_el.get("href"):
                product_url = marketplace.build_product_url(link_el["href"])

            if title:
                products.append(
                    ScrapedProduct(
                        title=title,
                        price=price,
                        currency=currency,
                        in_stock=True,
                        url=product_url,
                        source=marketplace.id,
                    )
                )
        except Exception as exc:
            logger.debug("Error parsing Amazon result: %s", exc)
            continue

    return products


async def scrape_walmart(query: str) -> list[ScrapedProduct]:
    """Scrape Walmart search results for product listings."""
    marketplace = get_marketplace_config("walmart")
    url = marketplace.build_search_url(query)
    html = await fetch_page(url, source="walmart")
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning("Failed to fetch Walmart results for: %s", query)
        return products

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div[data-item-id]")
    for item in items[:5]:
        try:
            title_el = item.select_one("span[data-automation-id='product-title']")
            link_el = item.select_one("a[link-identifier]") or item.select_one("a[href*='/ip/']")

            title = title_el.get_text(strip=True) if title_el else None
            price = _extract_walmart_price(item)

            product_url = None
            if link_el and link_el.get("href"):
                product_url = marketplace.build_product_url(link_el["href"])

            if title:
                products.append(
                    ScrapedProduct(
                        title=title,
                        price=price,
                        currency=marketplace.currency,
                        in_stock=True,
                        url=product_url,
                        source=marketplace.id,
                    )
                )
        except Exception as exc:
            logger.debug("Error parsing Walmart result: %s", exc)
            continue

    if not products:
        products = _parse_walmart_json_ld(soup)

    return products


async def scrape_ebay(query: str) -> list[ScrapedProduct]:
    """Scrape eBay US search results for product listings."""
    marketplace = get_marketplace_config("ebay")
    url = marketplace.build_search_url(query)
    html = await fetch_page(url, source="ebay")
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning("Failed to fetch eBay results for: %s", query)
        return products

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.s-item")
    for item in items[:5]:
        try:
            title_el = item.select_one(".s-item__title")
            price_el = item.select_one(".s-item__price")
            link_el = item.select_one("a.s-item__link")

            title = title_el.get_text(strip=True) if title_el else None
            if title and title.lower().startswith("shop on ebay"):
                continue

            price = extract_price(price_el.get_text()) if price_el else None
            product_url = None
            if link_el and link_el.get("href"):
                product_url = marketplace.build_product_url(link_el["href"])

            if title:
                products.append(
                    ScrapedProduct(
                        title=title,
                        price=price,
                        currency=marketplace.currency,
                        in_stock=True,
                        url=product_url,
                        source=marketplace.id,
                    )
                )
        except Exception as exc:
            logger.debug("Error parsing eBay result: %s", exc)
            continue

    return products


async def scrape_target(query: str) -> list[ScrapedProduct]:
    """Scrape Target US search results for product listings."""
    marketplace = get_marketplace_config("target")
    url = marketplace.build_search_url(query)
    html = await fetch_page(url, source="target")
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning("Failed to fetch Target results for: %s", query)
        return products

    soup = BeautifulSoup(html, "html.parser")
    items = (
        soup.select("[data-test='product-card']")
        or soup.select("[data-test='@web/ProductCard/ProductCardVariantDefault']")
    )
    for item in items[:5]:
        try:
            title_el = (
                item.select_one("[data-test='product-title']")
                or item.select_one("a[data-test='product-title']")
            )
            price_el = (
                item.select_one("[data-test='current-price']")
                or item.select_one("span[data-test='current-price']")
            )
            link_el = item.select_one("a[href*='/p/']")

            title = title_el.get_text(strip=True) if title_el else None
            price = extract_price(price_el.get_text()) if price_el else None

            product_url = None
            if link_el and link_el.get("href"):
                product_url = marketplace.build_product_url(link_el["href"])

            if title:
                products.append(
                    ScrapedProduct(
                        title=title,
                        price=price,
                        currency=marketplace.currency,
                        in_stock=True,
                        url=product_url,
                        source=marketplace.id,
                    )
                )
        except Exception as exc:
            logger.debug("Error parsing Target result: %s", exc)
            continue

    return products


async def scrape_flipkart(query: str) -> list[ScrapedProduct]:
    """Scrape Flipkart search results for product listings."""
    marketplace = get_marketplace_config("flipkart")
    url = marketplace.build_search_url(query)
    html = await fetch_page(url, source="flipkart")
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning("Failed to fetch Flipkart results for: %s", query)
        return products

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div._1AtVbE") or soup.select("div.tUxRFH")
    for item in items[:5]:
        try:
            title_el = item.select_one("div._4rR01T") or item.select_one("a.IRpwTa")
            price_el = item.select_one("div._30jeq3")
            link_el = item.select_one("a._1fQZEK") or item.select_one("a.IRpwTa")

            title = title_el.get_text(strip=True) if title_el else None
            price = extract_price(price_el.get_text()) if price_el else None

            product_url = None
            if link_el and link_el.get("href"):
                product_url = marketplace.build_product_url(link_el["href"])

            if title:
                products.append(
                    ScrapedProduct(
                        title=title,
                        price=price,
                        currency=marketplace.currency,
                        in_stock=True,
                        url=product_url,
                        source=marketplace.id,
                    )
                )
        except Exception as exc:
            logger.debug("Error parsing Flipkart result: %s", exc)
            continue

    return products
