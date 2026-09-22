"""
CatalogIQ — Competitor Monitoring Service

Pipeline 3: Scrapes competitor prices and stock status from Amazon,
Walmart, and Flipkart. Generates dashboard alerts when pricing
opportunities or competitor stockouts are detected.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.schemas import (
    Product, CompetitorPrice, CompetitorAlert,
    CompetitorSource, AlertType,
    CompetitorScrapeRequest,
)
from app.config import settings
from app.utils.scraper import (
    scrape_amazon, scrape_walmart, scrape_ebay, scrape_target, scrape_flipkart,
    ScrapedProduct, ScrapeSession,
)
from app.utils.product_match import (
    pick_best_listing,
    is_acceptable_competitor_price,
    infer_listing_currency,
)

logger = logging.getLogger("catalogiq.competitor_service")

# Mapping of source enum to scraper function
SCRAPER_MAP = {
    CompetitorSource.AMAZON: scrape_amazon,
    CompetitorSource.WALMART: scrape_walmart,
    CompetitorSource.EBAY: scrape_ebay,
    CompetitorSource.TARGET: scrape_target,
    CompetitorSource.FLIPKART: scrape_flipkart,
}


def get_default_scrape_sources() -> list[CompetitorSource]:
    """Return competitor sources for the configured SCRAPE_REGION."""
    return get_enabled_competitor_sources()


def get_enabled_competitor_sources() -> list[CompetitorSource]:
    """Return marketplace sources enabled by SCRAPE_REGION."""
    return [CompetitorSource(source_id) for source_id in settings.scrape_source_ids]


def _filter_sources_for_region(sources: list[CompetitorSource]) -> list[CompetitorSource]:
    """Keep only sources that belong to the active SCRAPE_REGION."""
    enabled = set(get_enabled_competitor_sources())
    filtered = [source for source in sources if source in enabled]
    return filtered or list(enabled)


def _create_or_update_alert(
    db: Session,
    product_id: int,
    alert_type: AlertType,
    source: CompetitorSource,
    message: str,
    our_price: Optional[float],
    competitor_price: Optional[float],
    price_difference: Optional[float] = None,
) -> Optional[CompetitorAlert]:
    """Create a new alert or refresh an existing unacknowledged duplicate.

    Returns:
        Newly created alert, or None if an existing alert was updated.
    """
    existing = db.query(CompetitorAlert).filter(
        CompetitorAlert.product_id == product_id,
        CompetitorAlert.alert_type == alert_type,
        CompetitorAlert.source == source,
        CompetitorAlert.acknowledged.is_(False),
    ).first()

    if existing:
        existing.message = message
        existing.our_price = our_price
        existing.competitor_price = competitor_price
        existing.price_difference = price_difference
        return None

    alert = CompetitorAlert(
        product_id=product_id,
        alert_type=alert_type,
        source=source,
        message=message,
        our_price=our_price,
        competitor_price=competitor_price,
        price_difference=price_difference,
    )
    db.add(alert)
    return alert


async def scrape_competitors_for_product(
    db: Session,
    product: Product,
    sources: list[CompetitorSource],
) -> tuple[list[CompetitorPrice], int, int]:
    """Scrape competitor listings for a single product.

    Args:
        db: Database session.
        product: Product to search for on competitor sites.
        sources: List of marketplace sources to scrape.

    Returns:
        Tuple of (price records, live result count, skipped result count).
    """
    results: list[CompetitorPrice] = []
    live_count = 0
    skipped_count = 0
    brand = (product.brand or "").strip()
    title = (product.title or "").strip()
    if brand and title.lower().startswith(brand.lower()):
        search_query = title
    else:
        search_query = f"{brand} {title}".strip()

    logger.info(f"Scraping competitors for product {product.id}: '{search_query[:60]}'")

    for source in sources:
        if source.value not in settings.marketplaces:
            logger.warning(f"Skipping disabled marketplace source: {source.value}")
            continue

        scraper_func = SCRAPER_MAP.get(source)
        if not scraper_func:
            logger.warning(f"No scraper available for source: {source}")
            continue

        try:
            scraped_products: list[ScrapedProduct] = await scraper_func(search_query)

            if not scraped_products:
                logger.info(
                    f"No live results from {source.value} for product {product.id}. Skipping."
                )
                skipped_count += 1
                continue

            best_match, match_score = pick_best_listing(product, scraped_products)
            if best_match is None:
                logger.info(
                    f"No confident live match on {source.value} for product {product.id}. Skipping."
                )
                skipped_count += 1
                continue

            if best_match.price is None:
                logger.info(
                    f"No price from {source.value} for product {product.id}. Skipping."
                )
                skipped_count += 1
                continue

            marketplace = settings.marketplaces[source.value]
            listing_currency = infer_listing_currency(
                best_match.price,
                best_match.currency,
                product,
                marketplace.currency,
            )
            if not is_acceptable_competitor_price(
                product, best_match.price, listing_currency
            ):
                logger.info(
                    f"Implausible price from {source.value} for product {product.id} "
                    f"({best_match.price} {listing_currency}). Skipping."
                )
                skipped_count += 1
                continue

            live_count += 1
            competitor_price = CompetitorPrice(
                product_id=product.id,
                source=source,
                competitor_title=best_match.title,
                competitor_url=best_match.url,
                competitor_price=best_match.price,
                competitor_currency=listing_currency,
                in_stock=best_match.in_stock,
                is_simulated=False,
                match_score=match_score,
                scraped_at=datetime.utcnow(),
            )
            db.add(competitor_price)
            results.append(competitor_price)

            logger.info(
                f"Found on {source.value}: price={best_match.price}, "
                f"in_stock={best_match.in_stock}, match_score={match_score}"
            )

        except Exception as e:
            logger.error(f"Error scraping {source.value} for product {product.id}: {str(e)}")
            continue

    if results:
        db.commit()

    return results, live_count, skipped_count


async def run_competitor_scrape(
    db: Session,
    request: CompetitorScrapeRequest,
) -> dict:
    """Run competitor scraping for specified products.

    Args:
        db: Database session.
        request: Scrape request with product IDs and sources.

    Returns:
        Summary of scraping results.
    """
    if request.product_ids:
        products = db.query(Product).filter(Product.id.in_(request.product_ids)).all()
    else:
        products = db.query(Product).filter(
            Product.status.in_(["active", "flagged"])
        ).all()

    if not products:
        logger.info("No products found for competitor scraping")
        return {
            "products_scraped": 0,
            "results_found": 0,
            "live_results": 0,
            "skipped_results": 0,
            "alerts_generated": 0,
        }

    total_results = 0
    total_live = 0
    total_skipped = 0
    total_alerts = 0

    sources_to_scrape = _filter_sources_for_region(request.sources)
    logger.info(
        f"Starting competitor scrape for {len(products)} products "
        f"in {settings.scrape_region} region: {[s.value for s in sources_to_scrape]}"
    )

    async with ScrapeSession():
        for product in products:
            try:
                price_records, live_count, skipped_count = await scrape_competitors_for_product(
                    db, product, sources_to_scrape
                )
                total_results += len(price_records)
                total_live += live_count
                total_skipped += skipped_count

                alerts = _analyze_and_alert(db, product, price_records)
                total_alerts += len(alerts)

            except Exception as e:
                logger.error(f"Error processing product {product.id}: {str(e)}")
                continue

    summary = {
        "products_scraped": len(products),
        "results_found": total_results,
        "live_results": total_live,
        "skipped_results": total_skipped,
        "alerts_generated": total_alerts,
    }

    logger.info(f"Competitor scrape complete: {summary}")
    return summary


def _normalize_competitor_price(
    competitor_price: float,
    competitor_currency: str,
    product: Product,
) -> float:
    """Normalize competitor price into the product currency."""
    if competitor_currency == product.currency:
        return competitor_price
    if competitor_currency == "INR" and product.currency == "USD":
        return competitor_price / settings.USD_INR_EXCHANGE_RATE
    if competitor_currency == "USD" and product.currency == "INR":
        return competitor_price * settings.USD_INR_EXCHANGE_RATE
    return competitor_price


def _analyze_and_alert(
    db: Session,
    product: Product,
    price_records: list[CompetitorPrice],
) -> list[CompetitorAlert]:
    """Analyze live competitor prices and generate deduplicated alerts."""
    alerts: list[CompetitorAlert] = []

    if not product.price or not price_records:
        return alerts

    for record in price_records:
        if record.is_simulated:
            logger.debug(
                f"Skipping alerts for simulated result: product={product.id}, "
                f"source={record.source.value}"
            )
            continue

        if not record.competitor_price:
            continue

        comp_price_normalized = _normalize_competitor_price(
            record.competitor_price,
            record.competitor_currency,
            product,
        )

        if comp_price_normalized < product.price:
            difference = product.price - comp_price_normalized
            pct_diff = (difference / product.price) * 100

            if pct_diff >= settings.ALERT_UNDERCUT_THRESHOLD_PCT:
                message = (
                    f"{record.source.value.title()} is selling a similar product "
                    f"at {record.competitor_currency} {record.competitor_price:.2f}, "
                    f"which is {pct_diff:.1f}% lower than your price of "
                    f"{product.currency} {product.price:.2f}."
                )
                alert = _create_or_update_alert(
                    db,
                    product.id,
                    AlertType.UNDERCUT,
                    record.source,
                    message,
                    product.price,
                    record.competitor_price,
                    difference,
                )
                if alert:
                    alerts.append(alert)

        if not record.in_stock:
            message = (
                f"Competitor on {record.source.value.title()} is OUT OF STOCK "
                f"for a similar product. This is a buying opportunity — "
                f"consider promoting your listing."
            )
            alert = _create_or_update_alert(
                db,
                product.id,
                AlertType.OUT_OF_STOCK,
                record.source,
                message,
                product.price,
                record.competitor_price,
            )
            if alert:
                alerts.append(alert)

        previous = db.query(CompetitorPrice).filter(
            CompetitorPrice.product_id == product.id,
            CompetitorPrice.source == record.source,
            CompetitorPrice.id != record.id,
            CompetitorPrice.is_simulated.is_(False),
            CompetitorPrice.competitor_price.isnot(None),
        ).order_by(CompetitorPrice.scraped_at.desc()).first()

        if previous and previous.competitor_price and record.competitor_price:
            change = record.competitor_price - previous.competitor_price
            pct_change = abs(change / previous.competitor_price) * 100

            if pct_change >= settings.ALERT_PRICE_CHANGE_THRESHOLD_PCT:
                if change < 0:
                    alert_type = AlertType.PRICE_DROP
                    message = (
                        f"Competitor on {record.source.value.title()} dropped price "
                        f"by {pct_change:.1f}% "
                        f"(from {previous.competitor_price:.2f} to "
                        f"{record.competitor_price:.2f})."
                    )
                else:
                    alert_type = AlertType.PRICE_INCREASE
                    message = (
                        f"Competitor on {record.source.value.title()} increased price "
                        f"by {pct_change:.1f}% "
                        f"(from {previous.competitor_price:.2f} to "
                        f"{record.competitor_price:.2f})."
                    )

                alert = _create_or_update_alert(
                    db,
                    product.id,
                    alert_type,
                    record.source,
                    message,
                    product.price,
                    record.competitor_price,
                    abs(change),
                )
                if alert:
                    alerts.append(alert)

    if alerts:
        db.commit()
        logger.info(f"Generated {len(alerts)} new alerts for product {product.id}")

    return alerts


def get_competitor_prices(
    db: Session,
    product_id: Optional[int] = None,
    source: Optional[CompetitorSource] = None,
    limit: int = 50,
) -> list[CompetitorPrice]:
    """Retrieve competitor price records for the active SCRAPE_REGION."""
    enabled_sources = get_enabled_competitor_sources()
    query = db.query(CompetitorPrice).filter(CompetitorPrice.source.in_(enabled_sources))

    if product_id:
        query = query.filter(CompetitorPrice.product_id == product_id)
    if source:
        if source not in enabled_sources:
            return []
        query = query.filter(CompetitorPrice.source == source)

    return query.order_by(CompetitorPrice.scraped_at.desc()).limit(limit).all()


def get_alerts(
    db: Session,
    acknowledged: Optional[bool] = None,
    product_id: Optional[int] = None,
    limit: int = 50,
) -> list[CompetitorAlert]:
    """Retrieve competitor monitoring alerts for the active SCRAPE_REGION."""
    enabled_sources = get_enabled_competitor_sources()
    query = db.query(CompetitorAlert).filter(CompetitorAlert.source.in_(enabled_sources))

    if acknowledged is not None:
        query = query.filter(CompetitorAlert.acknowledged == acknowledged)
    if product_id:
        query = query.filter(CompetitorAlert.product_id == product_id)

    return query.order_by(CompetitorAlert.created_at.desc()).limit(limit).all()


def acknowledge_alert(db: Session, alert_id: int) -> Optional[CompetitorAlert]:
    """Mark an alert as acknowledged."""
    alert = db.query(CompetitorAlert).filter(CompetitorAlert.id == alert_id).first()
    if alert:
        alert.acknowledged = True
        db.commit()
        db.refresh(alert)
        logger.info(f"Alert {alert_id} acknowledged")
    return alert
