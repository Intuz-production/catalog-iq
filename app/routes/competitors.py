"""
CatalogIQ — Competitor Monitoring API Routes

Endpoints for scraping competitor prices, viewing results,
and managing monitoring alerts.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    CompetitorSource,
    CompetitorPriceResponse, CompetitorAlertResponse,
    CompetitorScrapeRequest,
)
from app.services import competitor_service

logger = logging.getLogger("catalogiq.routes.competitors")

router = APIRouter(prefix="/api/competitors", tags=["Competitor Monitoring"])


@router.post("/scrape")
async def trigger_scrape(
    request: CompetitorScrapeRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Trigger competitor price scraping.

    Scrapes specified marketplaces for matching products and
    generates alerts for pricing opportunities.
    """
    logger.info(f"Manual scrape triggered: sources={request.sources}")

    result = await competitor_service.run_competitor_scrape(db, request)
    return {
        "message": "Competitor scraping completed.",
        "summary": result,
    }


@router.get("/prices", response_model=list[CompetitorPriceResponse])
def list_competitor_prices(
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    source: Optional[CompetitorSource] = Query(None, description="Filter by marketplace"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[CompetitorPriceResponse]:
    """List competitor price snapshots."""
    prices = competitor_service.get_competitor_prices(
        db, product_id=product_id, source=source, limit=limit
    )
    return [CompetitorPriceResponse.model_validate(p) for p in prices]


@router.get("/alerts", response_model=list[CompetitorAlertResponse])
def list_alerts(
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[CompetitorAlertResponse]:
    """List competitor monitoring alerts."""
    alerts = competitor_service.get_alerts(
        db, acknowledged=acknowledged, product_id=product_id, limit=limit
    )
    return [CompetitorAlertResponse.model_validate(a) for a in alerts]


@router.put("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Mark an alert as acknowledged."""
    alert = competitor_service.acknowledge_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"message": f"Alert {alert_id} acknowledged."}
