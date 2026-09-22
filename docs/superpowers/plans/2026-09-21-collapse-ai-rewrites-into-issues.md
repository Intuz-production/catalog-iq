# Collapse AI Rewrites into Issue Reviewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the separate AI Rewrite review flow; store AI field changes as `DataIssue` rows and review them only in the Quality Issues card.

**Architecture:** `persist_product_analysis` writes/enriches `DataIssue` instead of `FieldSuggestion`. Delete rewrite list/review/bulk APIs; add `POST /issues/accept-bulk`. Frontend drops `RewriteReviewPanel` and adds Accept all / Ignore all on issue product groups.

**Tech Stack:** FastAPI, SQLAlchemy, React (Vite), pytest

## Global Constraints

- Minimal diff — only files required by the design spec
- No Alembic migration; orphaned `field_suggestions` table left unused
- Do not rename shared CSS `rewrite-review-card` / `rewrite-product*` used by issues UI
- Polish-only AI changes → `issue_type=AI_INFERRED`, `severity=LOW`
- User did not request commits during implementation (commit only if asked)

---

### Task 1: Persist AI changes as DataIssue

**Files:**
- Modify: `app/services/ingestion_ai_service.py` (`persist_product_analysis`)
- Modify: `tests/test_ingestion_ai.py`

**Produces:** Changed fields become `DataIssue` rows (or attach to overlapping open issues); no `FieldSuggestion` writes.

- [x] Rewrite `persist_product_analysis` to stop using `FieldSuggestion`
- [x] Update AI tests to assert `DataIssue` instead of `FieldSuggestion`
- [x] Run: `pytest tests/test_ingestion_ai.py -v`

### Task 2: Review service + schemas + routes

**Files:**
- Modify: `app/services/ingestion_service.py`
- Modify: `app/models/schemas.py`, `app/models/__init__.py`
- Modify: `app/routes/ingestion.py`
- Modify: `tests/test_ingestion_review.py`

**Produces:** `accept_issues_bulk`; sibling field resolve on issue accept/edit; rewrites APIs removed.

- [x] Remove field-suggestion helpers; add `accept_issues_bulk`; fix `review_data_issue`
- [x] Remove `FieldSuggestion` model/schemas; add `BulkAcceptIssues*`
- [x] Replace `/rewrites*` with `POST /issues/accept-bulk`
- [x] Rewrite review tests
- [x] Run: `pytest tests/test_ingestion_review.py tests/test_ingestion_ai.py -v`

### Task 3: Frontend — single issue reviewer

**Files:**
- Delete: `ui/src/components/RewriteReviewPanel.jsx`
- Modify: `ui/src/pages/Products.jsx`, `ui/src/api/client.js`, `ui/src/index.css`

**Produces:** One Quality Issues card with Accept all / Ignore all per product.

- [x] Swap client helpers; remove rewrite panel/card; add bulk actions
- [x] Prune unused rewrite-panel CSS

### Task 4: Full verification

- [x] Run: `pytest -q` → **149 passed**
- [x] Confirm no remaining `FieldSuggestion` / rewrite-panel references in app/ui
