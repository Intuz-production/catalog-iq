# CatalogIQ — Project Status Update

> Last updated: 2026-09-17  
> For: TL / stakeholder review

---

## Implemented

- JWT auth with login, protected API routes, default admin seeder
- React login + protected dashboard routes
- CSV ingestion with flexible column mapping and attribute normalization
- Data quality checks: contradictions, thin/missing content, duplicates, price anomalies
- Ingestion job tracking with issue list and resolve flow
- Groq LLM SEO content generation (`openai/gpt-oss-120b`)
- SEO title + keywords, multiple tones, batch + single generation
- Reasoning model support with retries and validation
- Competitor scraping: Amazon, Walmart, Flipkart
- Region config: `SCRAPE_REGION=us` or `in`
- Smart product matching for competitor listings
- Price/stock alerts: undercut, price change, stockout
- APScheduler for periodic scraping
- Product CRUD with search, filter, sort, pagination
- Dashboard with stats, recent issues, and alerts
- UI pages: Products, Ingestion, Content Gen, Competitors
- Reusable UI: pagination, sorting, toasts, confirm dialogs, product detail/edit
- Expanded config via `.env.example` (LLM, scraping, auth, alerts)
- Updated `setup.sh`, README, and sample CSV
- 79 tests passing (auth, ingestion, content, scrapers, competitor service)
- `plan.md` deliverables marked complete

---

## Recently Fixed

- Scheduled scrape import bug (`CompetitorScrapeRequest` in `app/main.py`)
- USD/INR exchange rate synced — UI reads `usd_inr_exchange_rate` from `/api/competitors/config` (no hardcoded `83.0`)
- Shared `ui/src/lib/currency.js` + `use-competitor-config` hook for consistent config across pages

---

## Remaining Concerns

- ~5,000 lines still uncommitted on `main`
- **Default credentials (dev-only, not a code bug)** — see [Auth defaults](#auth-defaults-dev-vs-production) below
- No Alembic migrations — schema changes via startup `ALTER TABLE` only
- HTML scraping is brittle — may fail on Amazon/Walmart/Flipkart without browser/API
- eBay/Target scrapers exist but disabled
- No API rate limiting
- No CI/CD or E2E tests
- Single admin user only (no RBAC)

---

## Auth Defaults (Dev vs Production)

The app seeds a default admin on first startup from `.env`:

| Variable | Default | Risk if unchanged in production |
|----------|---------|-------------------------------|
| `DEFAULT_ADMIN_EMAIL` | `admin@catalogiq.local` | Predictable login |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Anyone can sign in as admin |
| `JWT_SECRET_KEY` | `change-me-in-production` | Tokens can be forged |

**Safe for local development.** Before production deploy, set strong values in `.env`:

```env
JWT_SECRET_KEY=<random-32+-char-string>
DEFAULT_ADMIN_EMAIL=admin@yourcompany.com
DEFAULT_ADMIN_PASSWORD=<strong-unique-password>
```

Generate a secret: `openssl rand -hex 32`

---

## Future Improvements

- Commit changes and open PR
- Add Alembic migrations
- Harden production auth (enforce strong secrets on startup in prod mode)
- Add API rate limiting
- Use Playwright or official marketplace APIs for scraping
- Add Docker Compose + CI pipeline
- Email/Slack alerts
- Multi-user RBAC
- Shopify/WooCommerce integration
- Product image support
- Bulk export and bulk actions

---

## Summary

| Category | Status |
|----------|--------|
| Core pipelines | Complete (ingestion, content, competitors) |
| Auth & dashboard | Complete |
| Tests | 79 passing |
| Production readiness | Pending — commit, migrations, auth hardening, scraping reliability |
