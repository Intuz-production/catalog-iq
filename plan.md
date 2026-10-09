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
                           |  +-------------------+  |       +----------------+
                           |  | Content Generator |--+-----> | LLM (Groq /    |
                           |  | (SEO Descriptions)|  |       | OpenAI / Gemini)|
                           |  +-------------------+  |       +----------------+
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
| AI/ML | Groq / OpenAI / Gemini via `LLM_PROVIDER` | Product descriptions and AI ingest analysis |
| Storage | PostgreSQL + SQLAlchemy | Structured storage for products, users, normalized attributes, competitor snapshots, and flagged issues |
| Frontend | React (Vite) | Modern SPA dashboard for product management, content review, and competitor monitoring |
| Scraping | httpx + BeautifulSoup4 | Lightweight async HTTP client and HTML parser for competitor marketplace scraping |
| Data Processing | Pandas | CSV parsing, data transformation, and attribute normalization |
| Task Scheduling | APScheduler | Periodic competitor scraping jobs without external infrastructure |

---

## Deliverables

- [x] User authentication with JWT login and default admin seeder
- [x] Complete runnable Python backend in `catalog-iq/app/`
- [x] React frontend dashboard in `catalog-iq/ui/`
- [x] CSV ingestion and data normalization pipeline with contradiction flagging
- [x] LLM-powered SEO product description generator (pluggable providers)
- [x] AI ingest analysis and issue review (feature branch enhancements)
- [x] Custom CSV column mapping and WooCommerce export (feature branch)
- [x] Competitor price and stock scraper for Amazon, Walmart, and Flipkart
- [x] PostgreSQL database schema with migrations (startup migrations; Alembic pending)
- [x] Sample CSV product data for demo
- [x] `.env.example`, `setup.sh`, tests, and `README.md`

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
│   │   ├── product_service.py        # Product CRUD operations
│   │   ├── product_field_utils.py    # Shared catalog field apply helpers
│   │   ├── user_service.py           # User account helpers
│   │   ├── auth_service.py           # Login and JWT issuance
│   │   └── seed_service.py           # Default admin user seeder
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth.py                   # JWT auth dependency for protected routes
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py                   # Login and current-user endpoints
│   │   ├── products.py               # Product management endpoints
│   │   ├── ingestion.py              # CSV upload and normalization endpoints
│   │   ├── content.py                # Content generation endpoints
│   │   └── competitors.py            # Competitor monitoring endpoints
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py                # Shared utility functions
│       ├── scraper.py                # Base scraping utilities
│       └── security.py               # Password hashing and JWT helpers
├── ui/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.jsx                  # React entry point
│   │   ├── App.jsx                   # Root component with routing
│   │   ├── api/
│   │   │   ├── http.js               # Shared fetch wrapper with auth headers
│   │   │   ├── auth.js               # Login and current-user API calls
│   │   │   └── client.js             # Domain API functions
│   │   ├── lib/
│   │   │   ├── auth-context.js       # Shared auth React context
│   │   │   ├── auth-storage.js       # JWT token storage helpers
│   │   │   └── use-auth.js           # Auth state hook
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   ├── auth-provider.jsx # Auth state provider component
│   │   │   │   └── protected-route.jsx # Route guard for authenticated pages
│   │   │   ├── Layout.jsx            # App shell with navigation
│   │   │   ├── ProductTable.jsx      # Product listing (default sort: title)
│   │   │   ├── ProductDetailDialog.jsx
│   │   │   ├── AiThoughtPanel.jsx    # Give a Thought AI edits
│   │   │   ├── DataIssueCard.jsx     # Issue accept / ignore / edit
│   │   │   ├── ContentPreview.jsx    # Generated description preview
│   │   │   └── CompetitorChart.jsx   # Price trend visualization
│   │   ├── lib/
│   │   │   ├── product-update-map.js
│   │   │   └── issue-fields.js
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Ingestion.jsx         # Job list (/products)
│   │   │   ├── Products.jsx          # Job catalog (/products/:jobId)
│   │   │   └── Competitors.jsx       # Optional; not in default nav
│   │   └── index.css
├── data/
│   └── sample_products.csv           # Demo product data
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py
│   ├── test_ingestion_review.py      # Issue accept / reject
│   ├── test_product_field_utils.py
│   ├── test_content.py
│   ├── test_competitors.py
│   └── test_auth.py
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
| `LLM_PROVIDER` | No | `groq` | Active LLM backend: `groq`, `openai`, or `gemini` |
| `LLM_MODEL` | No | `openai/gpt-oss-120b` | Model id for the active provider |
| `GROQ_API_KEY` | If groq | -- | Groq API key |
| `OPENAI_API_KEY` | If openai | -- | OpenAI API key |
| `GEMINI_API_KEY` | If gemini | -- | Google Gemini API key |
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string |
| `FASTAPI_HOST` | No | `0.0.0.0` | Host for the FastAPI server |
| `FASTAPI_PORT` | No | `8000` | Port for the FastAPI server |
| `SCRAPE_REGION` | No | `us` | Competitor region: `us` or `in` |
| `SCRAPE_INTERVAL_HOURS` | No | `6` | How often competitor scraping runs (in hours) |
| `JWT_SECRET_KEY` | No | `change-me-in-production` | Secret used to sign JWT access tokens |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | No | `1440` | JWT token lifetime in minutes (24 hours) |
| `DEFAULT_ADMIN_EMAIL` | No | `admin@catalogiq.local` | Email for the default admin user seeded on startup |
| `DEFAULT_ADMIN_PASSWORD` | No | `admin123` | Password for the default admin user seeded on startup |
| `DEFAULT_ADMIN_NAME` | No | `Admin` | Display name for the default admin user |
| `VITE_API_URL` | No | `http://localhost:8000` | Backend API URL (`ui/.env`) |

See `.env.example` and [README.md](./README.md) for the full variable list.

---

## Requirements Summary

- Domain: Generative AI Development
- Industry: E-Commerce (small-to-mid sized stores, 500-5,000 SKUs)
- LLM Provider: Groq API with `openai/gpt-oss-120b` (replaces retired `llama-3.3-70b-versatile`)
- Frontend: React (Vite) -- separate from backend
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Data Ingestion: CSV upload (supplier feeds)
- Content Generation: SEO product descriptions grounded in structured attributes
- Competitor Monitoring: Scrape Amazon, Walmart, Flipkart for prices and stock
- Authentication: JWT login, protected API routes, default admin user seeder
- Alerting: Dashboard-based alerts only (no SMTP email for now)
- Three core pipelines: Data Cleanup, Content Generation, Competitor Monitoring

---

## Out of Scope

- Shopify/WooCommerce API integration (CSV only for this version)
- SMTP email notifications (dashboard alerts only)
- Multi-tenant support and role-based access control beyond a single admin user
- Real-time WebSocket updates
- Payment processing or order management
- Mobile application
- Keyword research API integration (will use pattern-based SEO targeting)

---

## Approval

| Decision | Date | Notes |
|----------|------|-------|
| Approved | 2026-06-19 | User approved — proceeding to Phase 4 |
