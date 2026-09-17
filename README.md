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
- **Solution:** The platform generates unique, fact-grounded SEO descriptions using Groq LLM (`openai/gpt-oss-120b`), strictly using structured product attributes as the source of truth so no specs are invented.
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
- Generate unique, fact-grounded SEO product descriptions using Groq LLM with structured attributes as the source of truth
- Monitor competitor prices and stock status across region-configured marketplaces with automated alerting (`SCRAPE_REGION=us` or `in`)

Built with FastAPI, React, PostgreSQL, and Groq API (`openai/gpt-oss-120b`), the system provides a complete catalog management pipeline from raw supplier data to market-ready product listings.

---

## Features


| Feature                   | Description                                                                               |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| CSV Data Ingestion        | Upload supplier feeds with flexible column mapping and automatic attribute normalization  |
| Contradiction Detection   | Flags mismatches between product title, description, and attribute specifications         |
| Content Quality Scoring   | Evaluates existing descriptions and identifies thin or missing content                    |
| AI Description Generation | Creates SEO-optimized descriptions grounded in structured product attributes via Groq LLM |
| SEO Metadata              | Generates search-optimized titles and keyword tags for each product                       |
| Competitor Scraping       | Monitors prices and stock on US (Amazon, Walmart) or India (Amazon, Flipkart) marketplaces |
| Smart Alerts              | Notifies on competitor undercuts (5%+), stockouts, and significant price changes (10%+)   |
| Scheduled Monitoring      | Automatic periodic competitor scraping via APScheduler                                    |
| React Dashboard           | Modern dark-mode UI with product management, issue tracking, and price comparison charts  |
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
                           |  +-------------------+  |       +----------+
                           |  | Content Generator |--+-----> | Groq API |
                           |  | (SEO Descriptions)|  |       | (LLaMA)  |
                           |  +-------------------+  |       +----------+
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
│   │   └── settings.py               # Settings re-export
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy engine and session
│   │   └── schemas.py                # ORM models and Pydantic schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion_service.py      # CSV parsing and data normalization
│   │   ├── content_service.py        # LLM-powered description generation
│   │   ├── competitor_service.py     # Marketplace scraping and monitoring
│   │   ├── product_service.py        # Product CRUD operations
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
│       │   └── use-auth.js           # Auth state hook
│       ├── components/
│       │   ├── auth/
│       │   │   ├── auth-provider.jsx # Auth state provider component
│       │   │   └── protected-route.jsx # Route guard for authenticated pages
│       │   ├── Layout.jsx            # App shell with navigation
│       │   ├── ProductTable.jsx      # Product listing with filters
│       │   ├── DataIssueCard.jsx     # Flagged contradiction display
│       │   ├── ContentPreview.jsx    # Generated description preview
│       │   └── CompetitorChart.jsx   # Price trend visualization
│       ├── pages/
│       │   ├── Login.jsx             # Email/password sign-in page
│       │   ├── Dashboard.jsx         # Overview with key metrics
│       │   ├── Products.jsx          # Product catalog management
│       │   ├── Ingestion.jsx         # CSV upload and normalization
│       │   ├── ContentGen.jsx        # Content generation interface
│       │   └── Competitors.jsx       # Competitor monitoring view
│       └── styles/
│           └── index.css             # Global styles
├── data/
│   └── sample_products.csv           # Demo product data (15 SKUs)
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py             # Ingestion pipeline tests
│   ├── test_content.py               # Content generation tests
│   ├── test_competitors.py           # Competitor scraping tests
│   └── test_auth.py                  # Password hashing and JWT tests
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

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 14+
- Groq API key (free at [https://console.groq.com/keys](https://console.groq.com/keys))

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
# Edit .env with your API keys and database URL

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
| `GROQ_API_KEY`          | Yes      | --                        | API key from [https://console.groq.com/keys](https://console.groq.com/keys)            |
| `GROQ_MODEL`            | No       | `openai/gpt-oss-120b`     | Groq model for content generation (Workflow 2)                                         |
| `GROQ_MAX_RETRIES`      | No       | `3`                       | Retry count for transient Groq API failures                                            |
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


---

## Usage

1. Start the backend and frontend servers (see Running the Application above)
2. Open the React dashboard at `http://localhost:5173` and sign in with the default admin credentials
3. Navigate to **Data Ingestion** and upload a CSV file (a sample is provided in `data/sample_products.csv`)
4. Review flagged issues on the **Dashboard** or in the ingestion results
5. Go to **Content Generator**, select products missing descriptions, and click Generate
6. Visit **Competitors** to trigger a marketplace scrape and view price comparison alerts (set `SCRAPE_REGION=us` or `in` in `.env`)

### Authentication

- `POST /api/auth/login` accepts `username` (email) and `password` as form data and returns a JWT
- The React app stores the token in `localStorage` and sends `Authorization: Bearer <token>` on API requests
- `GET /api/auth/me` returns the currently authenticated user profile
- Change `JWT_SECRET_KEY` and `DEFAULT_ADMIN_PASSWORD` before deploying to production

### API Endpoints


| Method | Endpoint                     | Auth | Description                                    |
| ------ | ---------------------------- | ---- | ---------------------------------------------- |
| `POST` | `/api/auth/login`            | No   | Sign in with email and password                |
| `GET`  | `/api/auth/me`               | Yes  | Get the current authenticated user             |
| `GET`  | `/api/products/`             | Yes  | List products with filtering and pagination    |
| `GET`  | `/api/products/stats`        | Yes  | Dashboard overview statistics                  |
| `POST` | `/api/ingestion/upload`      | Yes  | Upload and process a CSV supplier feed         |
| `GET`  | `/api/ingestion/issues`      | Yes  | List all data quality issues                   |
| `POST` | `/api/content/generate`      | Yes  | Generate SEO descriptions for products (batch) |
| `POST` | `/api/content/generate/{id}` | Yes  | Generate content for a single product          |
| `POST` | `/api/competitors/scrape`    | Yes  | Trigger competitor price scraping              |
| `GET`  | `/api/competitors/alerts`    | Yes  | List competitor monitoring alerts              |


Full interactive API documentation is available at `http://localhost:8000/docs`.

---

## Dependencies


| Package        | Purpose                                               |
| -------------- | ----------------------------------------------------- |
| FastAPI        | High-performance async REST API framework             |
| Groq           | LLM API client for content generation (`openai/gpt-oss-120b`) |
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
source venv/bin/activate
pytest tests/ -v
```

---

# License

Copyright (c) 2026 Intuz Solutions Pvt Ltd.
  
 Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

<h1></h1>
<a href="http://www.intuz.com">
<img src="screenshots/logo.jpg">
</a>
