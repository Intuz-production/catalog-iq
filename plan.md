# Project Plan: CatalogIQ - AI Catalog Intelligence Platform

> Status: **Approved**
> Created: 2026-06-19
> Domain: Generative AI Development

---

## Overview

| Field | Value |
|-------|-------|
| **Name** | CatalogIQ - AI Catalog Intelligence Platform |
| **Domain** | Generative AI Development |
| **Use Case** | Automate product data cleanup, SEO content generation, and competitor price monitoring for e-commerce stores |
| **Industry / Context** | E-Commerce (Shopify / WooCommerce stores with 500-5,000 SKUs) |
| **Setup Time** | ~10-15 minutes |
| **Manual Step** | Configure API keys in `.env` |

---

## What It Does

- Ingests raw product data from CSV supplier feeds, normalizes inconsistent attributes (sizes, materials, colors) into structured fields in PostgreSQL, and flags contradictions between title, description, and spec sheet for human review
- Generates unique, fact-grounded SEO product descriptions using structured attributes as the source of truth, ensuring no specs are invented, and targets real search query patterns
- Periodically scrapes competitor prices and stock status from Amazon, Walmart, and Flipkart for matched products, and alerts the business owner via dashboard when pricing opportunities or competitor stockouts are detected
- Provides a React dashboard for managing products, reviewing flagged issues, triggering content generation, and monitoring competitor intelligence

---

## Architecture

**Type:** Hybrid (Pipeline + API + Generative AI)

The platform uses a FastAPI backend exposing REST APIs consumed by a React frontend. Product data flows through three automated pipelines: (1) CSV ingestion and normalization pipeline that cleans supplier data and stores structured attributes in PostgreSQL, (2) an LLM-powered content generation engine that reads structured attributes and produces SEO descriptions via Groq API, and (3) a competitor monitoring pipeline that scrapes marketplace listings and stores price/stock snapshots for trend analysis. All three pipelines are triggered via API endpoints and report results to the React dashboard.

```
+------------------+       +-------------------------+       +------------+
|  React Frontend  | <---> |    FastAPI Backend       | <---> | PostgreSQL |
|  (Dashboard)     |       |                         |       |            |
+------------------+       |  +-------------------+  |       +------------+
                           |  | CSV Ingestion &   |  |
                           |  | Data Normalizer   |  |
                           |  +-------------------+  |
                           |                         |
                           |  +-------------------+  |       +----------+
                           |  | Content Generator |--+-----> | Groq API |
                           |  | (SEO Descriptions)|  |       | (LLaMA)  |
                           |  +-------------------+  |       +----------+
                           |                         |
                           |  +-------------------+  |       +------------------+
                           |  | Competitor Monitor|--+-----> | Amazon / Walmart |
                           |  | (Price Scraper)   |  |       | / Flipkart       |
                           |  +-------------------+  |       +------------------+
                           +-------------------------+
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Backend | FastAPI (Python) | High-performance async REST API for all three pipelines and frontend communication |
| AI/ML | Groq API + LLaMA 3.3 70B Versatile | Fast inference for product description generation and attribute normalization |
| Storage | PostgreSQL + SQLAlchemy | Structured storage for products, normalized attributes, competitor snapshots, and flagged issues |
| Frontend | React (Vite) | Modern SPA dashboard for product management, content review, and competitor monitoring |
| Scraping | httpx + BeautifulSoup4 | Lightweight async HTTP client and HTML parser for competitor marketplace scraping |
| Data Processing | Pandas | CSV parsing, data transformation, and attribute normalization |
| Task Scheduling | APScheduler | Periodic competitor scraping jobs without external infrastructure |

---

## Deliverables

- [ ] Complete runnable Python backend in `catalog-iq/app/`
- [ ] React frontend dashboard in `catalog-iq/ui/`
- [ ] CSV ingestion and data normalization pipeline with contradiction flagging
- [ ] LLM-powered SEO product description generator using Groq
- [ ] Competitor price and stock scraper for Amazon, Walmart, and Flipkart
- [ ] PostgreSQL database schema with migrations
- [ ] Sample CSV product data for demo
- [ ] `.env.example`, `setup.sh`, tests, and `README.md`

---

## Project Structure (Planned)

```
catalog-iq/
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py               # All env-based configuration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy engine and session
│   │   └── schemas.py                # Pydantic models and DB models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion_service.py      # CSV parsing and data normalization
│   │   ├── content_service.py        # LLM-powered description generation
│   │   ├── competitor_service.py     # Marketplace scraping and monitoring
│   │   └── product_service.py        # Product CRUD operations
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── products.py               # Product management endpoints
│   │   ├── ingestion.py              # CSV upload and normalization endpoints
│   │   ├── content.py                # Content generation endpoints
│   │   └── competitors.py            # Competitor monitoring endpoints
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py                # Shared utility functions
│       └── scraper.py                # Base scraping utilities
├── ui/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.jsx                  # React entry point
│   │   ├── App.jsx                   # Root component with routing
│   │   ├── api/
│   │   │   └── client.js             # API client for FastAPI backend
│   │   ├── components/
│   │   │   ├── Layout.jsx            # App shell with navigation
│   │   │   ├── ProductTable.jsx      # Product listing with filters
│   │   │   ├── DataIssueCard.jsx     # Flagged contradiction display
│   │   │   ├── ContentPreview.jsx    # Generated description preview
│   │   │   └── CompetitorChart.jsx   # Price trend visualization
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx         # Overview with key metrics
│   │   │   ├── Products.jsx          # Product catalog management
│   │   │   ├── Ingestion.jsx         # CSV upload and normalization
│   │   │   ├── ContentGen.jsx        # Content generation interface
│   │   │   └── Competitors.jsx       # Competitor monitoring view
│   │   └── styles/
│   │       └── index.css             # Global styles
│   └── public/
├── data/
│   └── sample_products.csv           # Demo product data
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py             # Ingestion pipeline tests
│   ├── test_content.py               # Content generation tests
│   └── test_competitors.py           # Competitor scraping tests
├── .env.example
├── .gitignore
├── requirements.txt
├── setup.sh
├── plan.md
└── README.md
```

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | -- | API key from https://console.groq.com/keys |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model to use for content generation |
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string (e.g., `postgresql://user:pass@localhost:5432/catalogiq`) |
| `FASTAPI_HOST` | No | `0.0.0.0` | Host for the FastAPI server |
| `FASTAPI_PORT` | No | `8000` | Port for the FastAPI server |
| `SCRAPE_INTERVAL_HOURS` | No | `6` | How often competitor scraping runs (in hours) |
| `REACT_APP_API_URL` | No | `http://localhost:8000` | Backend API URL for the React frontend |

---

## Requirements Summary

- Domain: Generative AI Development
- Industry: E-Commerce (small-to-mid sized stores, 500-5,000 SKUs)
- LLM Provider: Groq API with LLaMA 3.3 70B Versatile model
- Frontend: React (Vite) -- separate from backend
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Data Ingestion: CSV upload (supplier feeds)
- Content Generation: SEO product descriptions grounded in structured attributes
- Competitor Monitoring: Scrape Amazon, Walmart, Flipkart for prices and stock
- Alerting: Dashboard-based alerts only (no SMTP email for now)
- Three core pipelines: Data Cleanup, Content Generation, Competitor Monitoring

---

## Out of Scope

- Shopify/WooCommerce API integration (CSV only for this version)
- SMTP email notifications (dashboard alerts only)
- User authentication and multi-tenant support
- Real-time WebSocket updates
- Payment processing or order management
- Mobile application
- Keyword research API integration (will use pattern-based SEO targeting)

---

## Approval

| Decision | Date | Notes |
|----------|------|-------|
| Approved | 2026-06-19 | User approved — proceeding to Phase 4 |
