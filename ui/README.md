# CatalogIQ Frontend

React 19 + Vite dashboard for the CatalogIQ FastAPI backend.

## Setup

From the repository root (recommended):

```bash
./setup.sh
```

Or manually:

```bash
cd ui
cp .env.example .env   # set VITE_API_URL (default http://localhost:8000)
npm install
```

## Development

```bash
npm run dev
```

Open `http://localhost:5173/login`. The app expects the backend at `VITE_API_URL` with JWT auth.

## Routes

| Path | Page | Notes |
|------|------|--------|
| `/login` | Sign in | |
| `/` | Dashboard | Stats and recent activity |
| `/products` | Product feeds | Upload CSV, manage ingestion jobs |
| `/products/:jobId` | Job catalog | Sortable product table (default: title A→Z), issues, **Give a Thought**, edit |
| `/ingestion`, `/content` | Redirect | Legacy paths → `/products` |

The **Competitors** page exists in source but is not wired in `App.jsx` / sidebar nav (API still available on the backend).

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build |
| `npm run lint` | ESLint |

## Product updates (UI)

- **`lib/product-update-map.js`** — Maps accepted AI/edit saves to the correct API fields (e.g. visible description → `generated_description` when SEO copy exists).
- **`lib/issue-fields.js`** — Normalizes issue `field_name` values for flags in the detail dialog.
- Issue **Apply** / **Give a Thought Apply** call `PUT /api/products/{id}`; issue **Ignore** calls review reject only (no product PATCH).

## Project docs

Backend setup, environment variables, and API reference: [../README.md](../README.md). Install script: [../setup.sh](../setup.sh).
