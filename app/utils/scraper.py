"""
CatalogIQ — Web Scraping Utilities

Base scraping functions for competitor marketplace monitoring.
Uses httpx for async HTTP and BeautifulSoup for HTML parsing.
"""

import re
import logging
import random
from typing import Optional
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("catalogiq.scraper")

# Rotate user agents to reduce blocking
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@dataclass
class ScrapedProduct:
    """Data structure for a scraped competitor product."""
    title: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    in_stock: bool = True
    url: Optional[str] = None
    source: str = ""


def get_random_headers() -> dict[str, str]:
    """Generate random HTTP headers to reduce scraping detection.

    Returns:
        Dictionary of HTTP headers with a random user agent.
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


async def fetch_page(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a web page and return its HTML content.

    Args:
        url: URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        HTML content as string, or None if the request fails.
    """
    try:
        async with httpx.AsyncClient(
            headers=get_random_headers(),
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.warning(f"Request error fetching {url}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {str(e)}")
    return None


def extract_price(text: str) -> Optional[float]:
    """Extract a numeric price from text.

    Handles various price formats like $19.99, Rs. 1,299, etc.

    Args:
        text: Text containing a price.

    Returns:
        Extracted price as float, or None if no price found.
    """
    if not text:
        return None
    # Find the first sequence that starts with a digit and contains digits, commas, or dots
    match = re.search(r"\d[\d,.]*", text)
    if not match:
        return None
    
    num_str = match.group(0).rstrip(".")
    num_str = num_str.replace(",", "")
    try:
        return float(num_str)
    except ValueError:
        return None


def build_search_url(query: str, source: str) -> str:
    """Build a marketplace search URL for a product query.

    Args:
        query: Product search query string.
        source: Marketplace source (amazon, walmart, flipkart).

    Returns:
        Formatted search URL for the specified marketplace.
    """
    encoded_query = query.replace(" ", "+")

    urls: dict[str, str] = {
        "amazon": f"https://www.amazon.com/s?k={encoded_query}",
        "walmart": f"https://www.walmart.com/search?q={encoded_query}",
        "flipkart": f"https://www.flipkart.com/search?q={encoded_query}",
    }

    return urls.get(source.lower(), urls["amazon"])


async def scrape_amazon(query: str) -> list[ScrapedProduct]:
    """Scrape Amazon search results for product listings.

    Args:
        query: Product search query.

    Returns:
        List of scraped product data from Amazon.
    """
    url = build_search_url(query, "amazon")
    html = await fetch_page(url)
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning(f"Failed to fetch Amazon results for: {query}")
        return products

    soup = BeautifulSoup(html, "html.parser")

    # Parse Amazon search result items
    items = soup.select("div[data-component-type='s-search-result']")
    for item in items[:5]:  # Limit to top 5 results
        try:
            title_el = item.select_one("h2 a span")
            price_whole = item.select_one("span.a-price-whole")
            price_frac = item.select_one("span.a-price-fraction")
            link_el = item.select_one("h2 a")

            title = title_el.get_text(strip=True) if title_el else None
            price = None
            if price_whole:
                price_text = price_whole.get_text(strip=True)
                if price_frac:
                    price_text += price_frac.get_text(strip=True)
                price = extract_price(price_text)

            product_url = None
            if link_el and link_el.get("href"):
                product_url = "https://www.amazon.com" + link_el["href"]

            if title:
                products.append(ScrapedProduct(
                    title=title,
                    price=price,
                    currency="USD",
                    in_stock=True,
                    url=product_url,
                    source="amazon",
                ))
        except Exception as e:
            logger.debug(f"Error parsing Amazon result: {str(e)}")
            continue

    return products


async def scrape_walmart(query: str) -> list[ScrapedProduct]:
    """Scrape Walmart search results for product listings.

    Args:
        query: Product search query.

    Returns:
        List of scraped product data from Walmart.
    """
    url = build_search_url(query, "walmart")
    html = await fetch_page(url)
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning(f"Failed to fetch Walmart results for: {query}")
        return products

    soup = BeautifulSoup(html, "html.parser")

    # Parse Walmart search results
    items = soup.select("div[data-item-id]")
    for item in items[:5]:
        try:
            title_el = item.select_one("span[data-automation-id='product-title']")
            price_el = item.select_one("div[data-automation-id='product-price'] span")
            link_el = item.select_one("a[link-identifier]")

            title = title_el.get_text(strip=True) if title_el else None
            price = extract_price(price_el.get_text()) if price_el else None

            product_url = None
            if link_el and link_el.get("href"):
                href = link_el["href"]
                product_url = href if href.startswith("http") else f"https://www.walmart.com{href}"

            if title:
                products.append(ScrapedProduct(
                    title=title,
                    price=price,
                    currency="USD",
                    in_stock=True,
                    url=product_url,
                    source="walmart",
                ))
        except Exception as e:
            logger.debug(f"Error parsing Walmart result: {str(e)}")
            continue

    return products


async def scrape_flipkart(query: str) -> list[ScrapedProduct]:
    """Scrape Flipkart search results for product listings.

    Args:
        query: Product search query.

    Returns:
        List of scraped product data from Flipkart.
    """
    url = build_search_url(query, "flipkart")
    html = await fetch_page(url)
    products: list[ScrapedProduct] = []

    if not html:
        logger.warning(f"Failed to fetch Flipkart results for: {query}")
        return products

    soup = BeautifulSoup(html, "html.parser")

    # Parse Flipkart search results
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
                product_url = "https://www.flipkart.com" + link_el["href"]

            if title:
                products.append(ScrapedProduct(
                    title=title,
                    price=price,
                    currency="INR",
                    in_stock=True,
                    url=product_url,
                    source="flipkart",
                ))
        except Exception as e:
            logger.debug(f"Error parsing Flipkart result: {str(e)}")
            continue

    return products
