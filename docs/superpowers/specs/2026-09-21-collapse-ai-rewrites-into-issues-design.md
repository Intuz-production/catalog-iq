# Collapse AI Rewrites into Issue Reviewer

**Date:** 2026-09-21  
**Status:** Approved for implementation planning  
**Branch:** `feature/improvements`

## Problem

The file-detail page (`ui/src/pages/Products.jsx`) exposes two parallel review flows:

1. **AI Rewrite Review** — `RewriteReviewPanel`, `field_suggestions` table, `/api/ingestion/rewrites*`
2. **Quality Issues** — `DataIssueCard`, `data_issues` table, `/api/ingestion/issues/{id}/review`

They overlap: `persist_product_analysis` already copies AI rewrite values onto matching open `DataIssue` rows, so the same suggestion can appear in both cards. Users should review everything in one place — the issue reviewer.

## Goal

Remove the separate AI Rewrite section and its flow. Keep review with the issue reviewer only.

**Coverage decision:** every AI-changed field becomes a reviewable issue (including polish-only rewrites). Polish-only entries use severity `low` so real problems still sort above them.

## Non-goals

- No changes to CSV parse/ingestion, content generation, competitors, or `ProductDetailDialog`
- No Alembic migration (project has none). Orphaned `field_suggestions` table in existing SQLite DBs is left in place and unused
- No rename of shared CSS class names already used by the issues card (`rewrite-review-card`, `rewrite-product`, etc.)

## Design

### Core idea

Stop writing `FieldSuggestion` rows. Write (or enrich) `DataIssue` rows instead. `DataIssue` already has `field_name`, `actual_value`, `suggested_value`, `suggestion_source`, and `review_status` — no schema addition required.

One table → one review endpoint → one UI card.

### Backend: AI persist path

**File:** `app/services/ingestion_ai_service.py` — `persist_product_analysis`

For each field the AI changed:

1. If an open issue already covers that field (via existing `_fields_overlap`), attach `suggested_value` (and set `suggestion_source` if missing) instead of creating a duplicate.
2. Otherwise create a new `DataIssue` with:
   - `issue_type = AI_INFERRED`
   - `severity = LOW`
   - `actual_value` = imported value
   - `suggested_value` = rewrite
   - `suggestion_source = AI`
   - `review_status = PENDING`
   - `description` from the model's `field_reasons` entry (fallback: plain sentence like "Suggested improvement for {field}")

Existing `extra_issues` handling is unchanged.

On re-analysis, delete unresolved pending issues for the product where `suggestion_source = AI` and `issue_type = AI_INFERRED` (same role as clearing pending `FieldSuggestion` rows today). Do **not** delete rule-based issues that only received an attached `suggested_value`. Stop creating `FieldSuggestion` rows entirely.

### Backend: review service

**File:** `app/services/ingestion_service.py`

| Remove | Keep / add |
|--------|------------|
| `get_field_suggestions` | `review_data_issue` (existing) |
| `review_field_suggestion` | New `accept_issues_bulk` — mirrors old bulk accept over `DataIssue` |
| `accept_rewrites_bulk` | |

`accept_issues_bulk(db, issue_ids=None, product_ids=None)`:

- Exactly one of `issue_ids` or `product_ids` required
- Accepts pending unresolved issues that have both `field_name` and `suggested_value`
- Skips issues missing either (counts as skipped)
- Returns `(accepted, skipped, product_ids_touched)`

**Correctness fix:** move `_resolve_open_issues_for_field` into `review_data_issue` on accept/edit so accepting a fix for `description` also closes sibling open issues on the same field. Reject continues to resolve only the single issue without applying product changes.

Job delete cleanup: remove the `FieldSuggestion` delete-by-`ingestion_job_id` block (cascades via product delete already cover product-linked rows; job-scoped suggestions are no longer written).

### Backend: routes and schemas

**File:** `app/routes/ingestion.py`

| Remove | Add |
|--------|-----|
| `GET /rewrites` | `POST /issues/accept-bulk` |
| `PUT /rewrites/{id}/review` | |
| `POST /rewrites/accept-bulk` | |

`PUT /issues/{id}/review` already covers accept / edit / reject.

**File:** `app/models/schemas.py` (and exports in `app/models/__init__.py`)

- Remove `FieldSuggestion` ORM model and `Product.field_suggestions` relationship
- Remove `FieldSuggestionResponse` / `FieldSuggestionListResponse`
- Rename `BulkAcceptRewritesRequest` / `BulkAcceptRewritesResponse` → `BulkAcceptIssuesRequest` / `BulkAcceptIssuesResponse` (same shape: `suggestion_ids` becomes `issue_ids`, plus `product_ids`)

### Frontend

**Delete:** `ui/src/components/RewriteReviewPanel.jsx`

**`ui/src/pages/Products.jsx`:**

- Remove AI Rewrite Review card and rewrite state/handlers (`rewrites`, `rewritesLoading`, `rewriteTotal`, `loadRewrites`, `handleAcceptProductRewrites`, `handleRejectProductRewrites`, `handleRejectFieldRewrite`)
- Quality Issues card absorbs bulk actions: per-product **Accept all** and **Ignore all** on the existing group header (via `groupIssuesByProduct`)
- Accept all → `acceptProductIssues(productId)` (new client helper)
- Ignore all → loop `reviewIssue(id, "reject")` for that product's open issues (with confirm)
- Keep single-issue review via `DataIssueCard` / `handleReviewIssue`

**`ui/src/api/client.js`:**

- Remove `fetchFieldRewrites`, `reviewFieldRewrite`, `acceptProductRewrites`
- Add `acceptProductIssues(productId)` → `POST /api/ingestion/issues/accept-bulk` with `{ product_ids: [productId] }`

**`ui/src/index.css`:**

- Keep shared group styles (`rewrite-review-card`, `rewrite-product`, `rewrite-product-header`, etc.)
- Remove panel-only rules: `rewrite-fields`, `rewrite-field*`, `rewrite-comparison`, `rewrite-value-label`, `rewrite-product-toggle`, `rewrite-product-actions` only if unused after the merge (keep `rewrite-product-actions` if Accept all / Ignore all reuse it)

**`DataIssueCard`:** no structural change required — already supports Apply / Edit fix / Ignore. Optional copy tweak for polish-only AI issues is out of scope unless needed for clarity.

### Tests

- `tests/test_ingestion_ai.py` — assert `DataIssue` rows instead of `FieldSuggestion`; cover attach-to-existing-issue and polish-only `AI_INFERRED` + `LOW`
- `tests/test_ingestion_review.py` — rewrite against `review_data_issue` + new bulk accept; drop field-suggestion review cases
- Run full suite; keep baseline green (currently ~79 tests plus any new coverage)

## Data flow (after)

```
CSV upload → rule issues (DataIssue)
         → AI analyze → attach suggestion to matching open issue
                      → or create AI_INFERRED / LOW issue for each changed field
         → UI: one Quality Issues card, grouped by product
         → Accept / Edit / Ignore (single) or Accept all / Ignore all (product)
         → review_data_issue / accept_issues_bulk → product fields updated
```

## Error handling

- Bulk accept skips non-applicable issues; reports accepted + skipped counts to the toast
- Missing `field_name` / `suggested_value` on accept → same ValueError/400 behavior as today for issue review
- Confirm dialogs remain for Accept all / Ignore all

## Out of scope / known follow-ups

- Dropping the orphaned `field_suggestions` SQLite table (needs migrations later)
- Renaming CSS `rewrite-*` classes used by the issues card
