"""
CatalogIQ — Application Entry Point

Starts the FastAPI server with all routes, database initialization,
and scheduled competitor scraping.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings, setup_logging
from app.models.database import init_db, SessionLocal
from app.models.schemas import CompetitorScrapeRequest
from app.routes import products, ingestion, content, competitors, auth
from app.services.competitor_service import get_default_scrape_sources, run_competitor_scrape
from app.dependencies.auth import get_current_user
from app.services.seed_service import seed_default_user

logger = setup_logging()

# Scheduler for periodic competitor scraping
scheduler = AsyncIOScheduler()


async def scheduled_competitor_scrape() -> None:
    """Run competitor scraping on a schedule."""
    logger.info("Running scheduled competitor scrape...")
    db = SessionLocal()
    try:
        request = CompetitorScrapeRequest(sources=get_default_scrape_sources())
        result = await run_competitor_scrape(db, request)
        logger.info(f"Scheduled scrape complete: {result}")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {str(e)}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting CatalogIQ - AI Catalog Intelligence Platform")
    settings.validate()
    init_db()

    db = SessionLocal()
    try:
        seed_default_user(db)
    finally:
        db.close()

    # Start competitor scraping scheduler
    scheduler.add_job(
        scheduled_competitor_scrape,
        "interval",
        hours=settings.SCRAPE_INTERVAL_HOURS,
        id="competitor_scrape",
        name="Competitor Price Scraper",
    )
    scheduler.start()
    logger.info(
        f"Competitor scraping scheduled every {settings.SCRAPE_INTERVAL_HOURS} hours"
    )

    logger.info(
        f"Server running at http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}"
    )
    logger.info(f"API documentation at {settings.docs_url}")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("CatalogIQ server shut down.")


# Create FastAPI application
app = FastAPI(
    title="CatalogIQ",
    description=(
        "AI Catalog Intelligence Platform — Automates product data cleanup, "
        "SEO content generation, and competitor price monitoring for e-commerce stores."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(auth.router)
app.include_router(products.router, dependencies=[Depends(get_current_user)])
app.include_router(ingestion.router, dependencies=[Depends(get_current_user)])
app.include_router(content.router, dependencies=[Depends(get_current_user)])
app.include_router(competitors.router, dependencies=[Depends(get_current_user)])


@app.get("/", tags=["Health"])
def root() -> dict:
    """Health check endpoint."""
    return {
        "name": "CatalogIQ",
        "version": "1.0.0",
        "status": "running",
        "description": "AI Catalog Intelligence Platform",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "scrape_interval_hours": settings.SCRAPE_INTERVAL_HOURS,
        "scrape_region": settings.scrape_region,
        "scrape_sources": settings.scrape_source_ids,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        reload=settings.FASTAPI_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
