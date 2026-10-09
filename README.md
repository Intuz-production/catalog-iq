## About Intuz

This library is maintained by [Intuz](https://www.intuz.com) — an AI-first software development company specializing in [Agentic AI Development](https://www.intuz.com/ai-agents-for-business-automation)
and [Generative AI Development](https://www.intuz.com/generative-ai-development).
  
  
INTUZ is presenting an AI-powered catalog intelligence and content automation platform for e-commerce businesses, automating product data cleanup, SEO description generation, and competitor price monitoring.

---

# CatalogIQ - AI Catalog Intelligence Platform

> Automate product data cleanup, SEO content generation, and competitor price monitoring for e-commerce stores with 500-5,000 SKUs.

## What This App Does

### 1. Product Data Cleanup from Supplier Feeds

- **Problem:** Small-to-mid e-commerce stores receive messy, inconsistent product data from multiple suppliers — abbreviated sizes, varying color names, contradictory specs between title and description.
- **Solution:** CatalogIQ ingests CSV supplier feeds and automatically normalizes attributes (sizes, colors, materials) into standardized values, then flags contradictions between title, description, and spec fields for human review.
- **Outcome:** Clean, structured product data stored in PostgreSQL with quality issues surfaced on a dashboard, reducing manual data entry by 80%.

### 2. SEO Product Description Generation

- **Problem:** Products with missing or thin descriptions hurt search rankings. Writing unique descriptions for hundreds of products is time-consuming and expensive.
- **Solution:** The platform generates unique, fact-grounded SEO descriptions using a configurable LLM provider (Groq, OpenAI, or Gemini), strictly using structured product attributes as the source of truth so no specs are invented.
- **Outcome:** Every product gets a compelling, SEO-optimized description with meta title and keywords, improving search visibility without hiring copywriters.

### 3. Competitor Price Monitoring

- **Problem:** E-commerce owners have no visibility into competitor pricing on major marketplaces (US: Amazon, Walmart; India: Amazon, Flipkart), missing opportunities when competitors go out of stock or undercut their prices.
- **Solution:** CatalogIQ periodically scrapes competitor marketplaces for matching products and generates alerts when a competitor undercuts your price by 5%+ or goes out of stock (a buying opportunity).
- **Outcome:** Dashboard alerts enable data-driven pricing decisions, helping businesses stay competitive and capitalize on market gaps.

---

## Description

CatalogIQ is an AI-powered catalog intelligence platform built for small-to-mid sized e-commerce businesses. It addresses three critical pain points: messy product data from suppliers, weak SEO content, and blind spots in competitor pricing.

This application enables users to:

- Upload CSV supplier feeds and automatically normalize, clean, and validate product data
- Generate unique, fact-grounded SEO product descriptions using a configurable LLM (Groq, OpenAI, or Gemini) with structured attributes as the source of truth
- Monitor competitor prices and stock status across region-configured marketplaces with automated alerting (`SCRAPE_REGION=us` or `in`)

Built with FastAPI, React, PostgreSQL, and pluggable LLM providers (default Groq `openai/gpt-oss-120b`), the system provides a complete catalog management pipeline from raw supplier data to market-ready product listings.

---

## Features


| Feature                   | Description                                                                               |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| CSV Data Ingestion        | Upload supplier feeds with preview, custom column mapping, and attribute normalization    |
| AI Ingest Analysis        | LLM review of products with actionable issue suggestions and accept/reject workflow       |
| WooCommerce Export        | Export normalized catalog to WooCommerce-compatible CSV                                   |
| Contradiction Detection   | Flags mismatches between product title, description, and attribute specifications         |
| Content Quality Scoring   | Evaluates existing descriptions and identifies thin or missing content                    |
| AI Description Generation | Creates SEO-optimized descriptions grounded in structured product attributes via configurable LLM |
| SEO Metadata              | Generates search-optimized titles and keyword tags for each product                       |
| Competitor Scraping       | Monitors prices and stock on US (Amazon, Walmart) or India (Amazon, Flipkart) marketplaces |
| Smart Alerts              | Notifies on competitor undercuts (5%+), stockouts, and significant price changes (10%+)   |
| Scheduled Monitoring      | Automatic periodic competitor scraping via APScheduler                                    |
| React Dashboard           | Dark-mode UI: dashboard, product feeds, per-job catalog review, issue and AI panels       |
| User Authentication       | JWT-based login with protected API routes and a default admin user seeded on startup      |
| Configurable              | Environment-based configuration via `.env`                                                |
| Modular                   | Clean separation of concerns with dedicated services for each pipeline                    |
| Tested                    | Includes test suites for ingestion, content generation, and competitor monitoring         |


---

## Architecture

```
+------------------+       +-------------------------+       +------------+
|  React Frontend  | <---> |    FastAPI Backend       | <---> | PostgreSQL |
|  (Dashboard)     |       |                         |       |            |
+------------------+       |  +-------------------+  |       +------------+
                           |  | CSV Ingestion &   |  |
                           |  | Data Normalizer   |  |
                           |  +-------------------+  |
                           |                         |
                           |  | Content + AI Ingest |--+-----> | LLM Provider   |
                           |  | (SEO + analysis)    |  |       | Groq/OpenAI/   |
                           |  +-------------------+  |       | Gemini         |
                           |                         |       +----------------+
                           |                         |
                           |  +-------------------+  |       +------------------+
                           |  | Competitor Monitor|--+-----> | US: Amazon,      |
                           |  | (Price Scraper)   |  |       | Walmart          |
                           |  +-------------------+  |       | IN: Amazon,      |
                           |                         |       | Flipkart         |
                           +-------------------------+       +------------------+
```

---

## Project Structure

```
catalog-iq/
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application entry point
│   ├── config/
│   │   ├── __init__.py               # Centralized settings and validation
│   │   ├── settings.py               # Settings re-export
│   │   └── marketplaces.py           # Region-specific marketplace URLs and sources
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy engine and session
│   │   └── schemas.py                # ORM models and Pydantic schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion_service.py      # CSV parsing, mapping, normalization
│   │   ├── ingestion_ai_service.py   # LLM product analysis and issue suggestions
│   │   ├── content_service.py        # LLM-powered description generation
│   │   ├── competitor_service.py     # Marketplace scraping and monitoring
│   │   ├── product_service.py        # Product CRUD operations
│   │   ├── product_field_utils.py    # Shared field apply rules (description, attributes)
│   │   ├── woocommerce_export_service.py  # WooCommerce CSV export
│   │   ├── user_service.py           # User account helpers
│   │   ├── auth_service.py           # Login and JWT issuance
│   │   ├── seed_service.py           # Default admin user seeder
│   │   └── llm/                      # Groq, OpenAI, Gemini adapters
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
│       ├── product_match.py          # Competitor listing match helpers
│       ├── scraper.py                # Web scraping utilities
│       └── security.py               # Password hashing and JWT helpers
├── ui/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx                  # React entry point
│       ├── App.jsx                   # Root component with routing
│       ├── api/
│       │   ├── http.js               # Shared fetch wrapper with auth headers
│       │   ├── auth.js               # Login and current-user API calls
│       │   └── client.js             # Domain API functions
│       ├── lib/
│       │   ├── auth-context.js       # Shared auth React context
│       │   ├── auth-storage.js       # JWT token storage helpers
│       │   ├── use-auth.js           # Auth state hook
│       │   ├── issue-fields.js       # Issue field keys for product UI
│       │   └── product-update-map.js # Product save / Give a Thought field mapping
│       ├── components/
│       │   ├── auth/                 # Auth provider and protected routes
│       │   ├── Layout.jsx            # App shell with navigation
│       │   ├── UploadProductFeedDialog.jsx  # CSV upload + column mapping
│       │   ├── CsvColumnMapper.jsx   # Map supplier columns to catalog fields
│       │   ├── ProductTable.jsx      # Product listing with filters
│       │   ├── ProductDetailDialog.jsx     # Detail, edit, AI, issues
│       │   ├── AiThoughtPanel.jsx    # AI analysis and actions
│       │   ├── DataIssueCard.jsx     # Flagged issue display + review
│       │   ├── ContentPreview.jsx    # Generated description preview
│       │   └── CompetitorChart.jsx   # Price trend visualization (Competitors page)
│       ├── lib/                      # Auth, toast, confirm, currency hooks
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── Ingestion.jsx         # Ingestion job list (route: /products)
│       │   ├── Products.jsx          # Products for a job (route: /products/:jobId)
│       │   └── Competitors.jsx       # Present but not linked in nav (optional)
│       └── index.css                 # Global styles
├── data/
│   └── sample_products.csv           # Demo product data (17 SKUs, AI test cases)
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py
│   ├── test_ingestion_ai.py
│   ├── test_ingestion_review.py
│   ├── test_product_field_utils.py
│   ├── test_content.py
│   ├── test_competitors.py
│   ├── test_competitor_service.py
│   ├── test_woocommerce_export.py
│   └── test_auth.py
├── docs/superpowers/                 # Design specs and implementation plans
├── .env.example
├── .gitignore
├── requirements.txt
├── setup.sh
├── plan.md
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Node.js 18+ and npm
- PostgreSQL 14+
- API key for your chosen LLM provider (default Groq — free tier at [console.groq.com/keys](https://console.groq.com/keys))

### Quick Setup (Recommended)

```bash
git clone <repository-url>
cd catalog-iq

# One-command setup
chmod +x setup.sh
./setup.sh
```

### Manual Setup

```bash
git clone <repository-url>
cd catalog-iq

# Create virtual environment
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install React frontend dependencies
cd ui && npm install && cd ..

# Configure environment
cp .env.example .env
cp ui/.env.example ui/.env
# Edit .env (backend) and ui/.env (VITE_API_URL)

# Create the database
createdb catalogiq
```

### Running the Application

```bash
# Terminal 1 — Start the backend
source venv/bin/activate
python -m app.main

# Terminal 2 — Start the frontend
cd ui
npm run dev
```

Backend API: `http://localhost:8000`
API Documentation: `http://localhost:8000/docs`
Frontend Dashboard: `http://localhost:5173`

On first backend startup, a default admin user is seeded automatically if it does not already exist:

| Field    | Default Value            |
| -------- | ------------------------ |
| Email    | `admin@catalogiq.local`  |
| Password | `admin123`               |

Sign in at `http://localhost:5173/login` before using the dashboard. All `/api/*` routes except `/api/auth/login` require a valid JWT bearer token.

---

## Configuration


| Variable                | Required | Default                   | Description                                                                            |
| ----------------------- | -------- | ------------------------- | -------------------------------------------------------------------------------------- |
| `LLM_PROVIDER`          | No       | `groq`                    | Active LLM backend: `groq`, `openai`, or `gemini`                                      |
| `LLM_MODEL`             | No       | `openai/gpt-oss-120b`     | Model id for the active provider (falls back to `GROQ_MODEL` if unset)                 |
| `GROQ_API_KEY`          | If groq  | --                        | Required when `LLM_PROVIDER=groq` ([console.groq.com/keys](https://console.groq.com/keys)) |
| `OPENAI_API_KEY`        | If openai| --                        | Required when `LLM_PROVIDER=openai`                                                    |
| `GEMINI_API_KEY`        | If gemini| --                        | Required when `LLM_PROVIDER=gemini`                                                    |
| `GROQ_MODEL`            | No       | `openai/gpt-oss-120b`     | Legacy alias used only when `LLM_MODEL` is unset                                       |
| `GROQ_MAX_RETRIES`      | No       | `3`                       | Retry count for transient LLM API failures                                             |
| `GROQ_MIN_DESCRIPTION_WORDS` | No  | `20`                      | Minimum accepted words in a generated description                                      |
| `SEO_TITLE_MAX_LENGTH`  | No       | `60`                      | Maximum stored SEO title length                                                        |
| `DATABASE_URL`          | Yes      | --                        | PostgreSQL connection string (e.g., `postgresql://user:pass@localhost:5432/catalogiq`) |
| `FASTAPI_HOST`          | No       | `0.0.0.0`                 | Backend server host                                                                    |
| `FASTAPI_PORT`          | No       | `8000`                    | Backend server port                                                                    |
| `SCRAPE_INTERVAL_HOURS` | No       | `6`                       | How often competitor scraping runs                                                     |
| `SCRAPE_REGION`         | No       | `us`                      | Marketplace region: `us` (Amazon, Walmart) or `in` (Amazon, Flipkart)                   |
| `JWT_SECRET_KEY`        | No       | `change-me-in-production` | Secret used to sign JWT access tokens                                                  |
| `JWT_ALGORITHM`         | No       | `HS256`                   | JWT signing algorithm                                                                  |
| `JWT_EXPIRE_MINUTES`    | No       | `1440`                    | JWT token lifetime in minutes (24 hours)                                               |
| `DEFAULT_ADMIN_EMAIL`   | No       | `admin@catalogiq.local`   | Email for the default admin user seeded on startup                                     |
| `DEFAULT_ADMIN_PASSWORD`| No       | `admin123`                | Password for the default admin user seeded on startup                                  |
| `DEFAULT_ADMIN_NAME`    | No       | `Admin`                   | Display name for the default admin user                                                |
| `LOG_LEVEL`             | No       | `INFO`                    | Logging level (DEBUG, INFO, WARNING, ERROR)                                            |

Additional variables (CORS, DB pool, scrape tuning, alert thresholds, ingest LLM tuning) are documented inline in `.env.example`.

### Frontend (`ui/.env`)

| Variable       | Required | Default                 | Description              |
| -------------- | -------- | ----------------------- | ------------------------ |
| `VITE_API_URL` | No       | `http://localhost:8000` | FastAPI base URL for API |

---

## Usage

1. Start the backend and frontend servers (see Running the Application above)
2. Open `http://localhost:5173/login` and sign in with the default admin credentials
3. Open **Products**, upload a CSV (sample: `data/sample_products.csv`), and map columns if prompted
4. Open the ingestion job — the product table defaults to **title (A→Z)**. In the product detail dialog:
   - **Apply this fix** / **Edit fix** on a data issue updates the product; **Ignore** closes the issue without changing fields
   - **Give a Thought** proposes field changes; only accepted rows are applied on **Apply N Changes**
   - Description edits apply to **generated** copy when present (what you see in the preview), not a hidden raw column
5. Use the **Dashboard** for catalog stats and recent issues
6. Export WooCommerce-ready CSV via the products API (`GET /api/products/export/woocommerce`) or integrate from your client
7. **Competitor monitoring** — call `POST /api/competitors/scrape` and related endpoints (Competitors UI page is optional/disabled in default nav; set `SCRAPE_REGION=us` or `in` in `.env`)

### Authentication

- `POST /api/auth/login` accepts `username` (email) and `password` as form data and returns a JWT
- The React app stores the token in `localStorage` and sends `Authorization: Bearer <token>` on API requests
- `GET /api/auth/me` returns the currently authenticated user profile
- Change `JWT_SECRET_KEY` and `DEFAULT_ADMIN_PASSWORD` before deploying to production

### API Endpoints


| Method   | Endpoint                              | Auth | Description                                      |
| -------- | ------------------------------------- | ---- | ------------------------------------------------ |
| `POST`   | `/api/auth/login`                     | No   | Sign in with email and password                  |
| `GET`    | `/api/auth/me`                        | Yes  | Current user profile                             |
| `GET`    | `/api/products/`                      | Yes  | List products (filter, sort, paginate; default sort: title ascending) |
| `GET`    | `/api/products/stats`                 | Yes  | Dashboard statistics                             |
| `GET`    | `/api/products/categories`            | Yes  | Distinct product categories                      |
| `GET`    | `/api/products/statuses`              | Yes  | Distinct product statuses                        |
| `GET`    | `/api/products/export/woocommerce`    | Yes  | Download WooCommerce CSV export                  |
| `GET`    | `/api/products/{id}`                  | Yes  | Product detail                                   |
| `POST`   | `/api/products/`                      | Yes  | Create product                                   |
| `PUT`    | `/api/products/{id}`                  | Yes  | Update product                                   |
| `DELETE` | `/api/products/{id}`                  | Yes  | Delete product                                   |
| `GET`    | `/api/products/{id}/issues`             | Yes  | Issues for one product                           |
| `POST`   | `/api/products/{id}/ai-thought`       | Yes  | Free-text AI field proposals (merchant accepts per field in UI) |
| `GET`    | `/api/ingestion/sample-csv`           | Yes  | Download sample CSV template                     |
| `POST`   | `/api/ingestion/preview`              | Yes  | Preview CSV mapping before upload                |
| `POST`   | `/api/ingestion/upload`               | Yes  | Upload and process a CSV feed                    |
| `GET`    | `/api/ingestion/jobs`                   | Yes  | List ingestion jobs                              |
| `GET`    | `/api/ingestion/jobs/{id}`            | Yes  | Ingestion job detail                             |
| `PATCH`  | `/api/ingestion/jobs/{id}`            | Yes  | Rename / update job metadata                     |
| `DELETE` | `/api/ingestion/jobs/{id}`            | Yes  | Delete ingestion job                             |
| `GET`    | `/api/ingestion/issues`               | Yes  | List data quality issues                         |
| `PUT`    | `/api/ingestion/issues/{id}/resolve`  | Yes  | Resolve an issue                                 |
| `PUT`    | `/api/ingestion/issues/{id}/review`   | Yes  | Accept/reject AI or rule suggestion              |
| `POST`   | `/api/ingestion/issues/accept-bulk`   | Yes  | Bulk accept issues                               |
| `GET`    | `/api/content/needs-content`            | Yes  | Products missing generated content (default sort: title ascending) |
| `POST`   | `/api/content/generate`               | Yes  | Batch SEO description generation                 |
| `POST`   | `/api/content/generate/{id}`          | Yes  | Generate content for one product                 |
| `GET`    | `/api/competitors/config`             | Yes  | Region, exchange rate, alert thresholds          |
| `POST`   | `/api/competitors/scrape`             | Yes  | Trigger competitor scrape                        |
| `GET`    | `/api/competitors/prices`             | Yes  | Latest competitor price snapshots                |
| `GET`    | `/api/competitors/alerts`             | Yes  | Competitor alerts                                |
| `PUT`    | `/api/competitors/alerts/{id}/acknowledge` | Yes | Acknowledge alert                           |


Full interactive API documentation is available at `http://localhost:8000/docs`.

---

## Dependencies


| Package        | Purpose                                               |
| -------------- | ----------------------------------------------------- |
| FastAPI        | High-performance async REST API framework             |
| Groq / OpenAI / google-genai | LLM clients selected via `LLM_PROVIDER` |
| SQLAlchemy     | ORM for PostgreSQL database operations                |
| Pandas         | CSV parsing and data transformation                   |
| httpx          | Async HTTP client for competitor scraping             |
| BeautifulSoup4 | HTML parsing for marketplace page scraping            |
| APScheduler    | Periodic task scheduling for competitor monitoring    |
| bcrypt         | Password hashing for user authentication              |
| python-jose    | JWT creation and validation for API auth              |
| Pydantic       | Data validation and serialization                     |
| React          | Frontend dashboard framework                          |
| Recharts       | Price comparison chart visualization                  |
| React Router   | Client-side routing for dashboard pages               |
| python-dotenv  | Environment variable management                       |


---

## Testing

```bash
source venv/bin/activate   # or: source .venv/bin/activate
pytest tests/ -v
```

As of the latest feature branch, the suite includes **152** tests (ingestion, AI ingest, content, competitors, auth, WooCommerce export).

---

# License

Copyright (c) 2026 Intuz Solutions Pvt Ltd.
  
 Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

<h1></h1>
<a href="http://www.intuz.com">
<img src="screenshots/logo.jpg">
</a>
