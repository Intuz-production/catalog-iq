# Soft Quality Standard

**Date:** 2026-09-21  
**Status:** Implemented (AI-decided soft issues → ready-to-use catalog data)  
**Related:** [collapse-ai-rewrites-into-issues design](./2026-09-21-collapse-ai-rewrites-into-issues-design.md)

## Goal

Given **one product row**, AI returns **ready-to-use catalog fields** a merchant can Accept. Hard structural checks stay in code. Soft judgment is AI-decided — report problems only when needed, with apply-ready suggestions from known facts.

## Hard rules (code)

Owned by `_collect_pending_issues` in `app/services/ingestion_service.py`, source `rule`:

| Type | Field | Trigger |
|------|-------|---------|
| `missing_description` | `description` | Empty / placeholder description |
| `duplicate_title` | `title` | Same title as another product |
| `price_anomaly` | `price` | Missing, unreadable, `<= 0`, or `> 50000` |

## Soft findings (AI decides)

Owned by ingest AI `extra_issues`, source `ai`.

- Goal: one product in → ready-to-use listing fields out (Accept to publish).
- AI **reviews every field** against the **full product JSON** (cross-field).
- Opens a card for **problems** (soft findings) and for **improvements** (polish
  rewrites stored as low-severity `ai_inferred` with Apply-ready `suggested_value`).
- Empty soft `extra_issues` is fine when there is no problem; polish suggestions
  still appear for fields the rewrite improved.
- Title/description fixes **must** include a ready-to-use `suggested_value` built only from known facts (title, brand, category, attributes, raw_data).
- Weave known attributes (color, size, material, weight) into description rewrites when present.
- Do not invent or demand warranty/capacity/etc. absent from the row.
- If `suggested_value` is omitted, persist backfills from the AI rewrite when fact-safe.
- Invented numeric/attribute suggestions are stripped; Ignore / Write my own still available.
- Unknown `issue_type` labels store as `ai_inferred`.

**Retired from creation:** `attribute_not_in_copy`. Legacy rows: Ignore only; cleared on re-analysis.

## Review contract

Accept / Edit apply `suggested_value` or the edited value to `field_name` via `review_data_issue`. Ignore resolves without changing the product.

## Persist guards

`persist_product_analysis` drops soft extras that lack an actionable `field_name` or use a retired type; anti-invention checks strip unsafe suggestions (with rewrite backfill when possible).
