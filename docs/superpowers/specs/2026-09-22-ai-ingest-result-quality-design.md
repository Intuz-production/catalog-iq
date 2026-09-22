# AI Ingest Result Quality (Meaningful Polish)

**Date:** 2026-09-22  
**Status:** Approved for implementation planning  
**Branch:** `feature/catalogiq-platform-enhancements`  
**Related:** [soft-quality-standard](./2026-09-21-soft-quality-standard-design.md), [collapse-ai-rewrites-into-issues](./2026-09-21-collapse-ai-rewrites-into-issues-design.md)

## Problem

Ingest AI stores a low-severity polish issue for **every** field the rewrite changes, including case-only / punctuation-only / tiny description rephrases. Merchants see noisy Apply suggestions on already publish-ready rows (`CTRL-*` in the sample CSV), which lowers trust in Accept.

Soft `extra_issues` and rule-issue suggestion attach already work well. The noise is concentrated in the **polish-only** path.

## Goal

Raise Accept usefulness: keep actionable rewrites (abbreviation expansion, thin/missing copy, contradictions via soft findings) and **drop trivial polish-only** suggestions.

## Non-goals

- No UI / route / schema changes
- No AI job speed, concurrency, or progress UX
- No file-level bulk review or raising the 50-issue fetch cap
- No SEO content-generation flow changes
- No change to invent-guards for attributes/numbers (keep existing sanitizers)

## Design

### Core rule

| Path | Behavior |
|------|----------|
| Attach rewrite to overlapping **rule** issue | Unchanged |
| Soft **`extra_issues`** (sanitized) | Unchanged — still create even if rewrite was trivial |
| Polish-only `AI_INFERRED` / `LOW` | **Only if meaningful** (see filters below) |

### Persist filters

**File:** `app/services/ingestion_ai_service.py`

Add helpers used only by the polish-only loop in `persist_product_analysis`:

1. **`_is_trivial_change(original, suggested) -> bool`**  
   True when normalized forms match after lowercasing and stripping whitespace/punctuation (treat as non-reviewable polish).  
   Reuse the spirit of `_values_match` but stricter for “cosmetic only” (case / space / punct). Numeric equivalence already handled by `_values_match` earlier in the changed-fields loop.

2. **`_is_meaningful_polish(field_name, original, suggested, reason) -> bool`**  
   Returns **false** (drop polish) when any of:
   - `reason` is missing/blank after strip
   - `_is_trivial_change(original, suggested)` is true
   - For `description` and `title`: change is near-identical — high token overlap **and** small length delta (exact thresholds set in the implementation plan; err toward dropping weak rephrases)

   Returns **true** otherwise (abbrev expansions, real casing+content fixes with a reason, substantial description fills).

**Polish-only loop change:** before creating the `DataIssue`, require `_is_meaningful_polish(...)`. Soft extras and rule attach skip this gate.

### Prompt tweak (same file)

In `REWRITE_SYSTEM_PROMPT` / `build_ingest_prompt`:

- Strengthen: if a field is already publish-ready, return it **unchanged** (no cosmetic-only edits).
- Soften conflicting “polish every improved field” wording so it does not encourage casing-only churn.
- Add 2–3 short few-shot sketches inline:
  1. Good row → rewrite equals source, `extra_issues: []`
  2. Thin description → ready-to-use description from known facts + soft finding
  3. Abbreviated attribute (`Grn` / `lg`) → expanded attribute + reason

No new providers, models, or env knobs.

### Soft-quality doc note

Update `2026-09-21-soft-quality-standard-design.md` one bullet: polish-only improvements appear **only when non-trivial and reasoned**, not for every rewrite diff.

## Data flow (after)

```
CSV upload → rule issues
          → AI rewrite + extra_issues
          → sanitize (existing)
          → attach suggestions to rule issues (existing)
          → persist soft extra_issues (existing)
          → polish-only IF meaningful (new gate)
          → merchant Review Issues (unchanged UI)
```

## Error handling

- Unchanged: invented numbers/attrs still stripped; invalid soft extras still dropped.
- Dropped polish is silent (no issue row) — not an error.
- Re-analysis still deletes prior pending AI soft/polish rows before rewrite (existing behavior).

## Testing

**File:** `tests/test_ingestion_ai.py`

| Case | Expect |
|------|--------|
| Case-only title (`bags` → `Bags`) | No polish issue |
| Abbr expand (`Grn` → `Green`) + reason | Polish (or soft) issue with suggestion |
| Thin description + reason | Suggestion created / attached |
| Soft `extra_issues` with trivial rewrite on another field | Soft issue still persisted |
| Polish-only field with empty `field_reasons` | No polish row |

Run full suite; keep existing invent-guard and attach tests green.

## Success criteria

- Sample `CTRL-*` rows produce little/no polish noise
- `THIN-*`, `ABBR-*`, `MISS-*`, `CONTR-*` still get actionable Apply suggestions
- No frontend or API contract changes

## Out of scope / follow-ups

- Progressive review while AI runs; file-level bulk; issue pagination beyond 50
- Stronger title/description anti-fluff sanitizer (marketing claims)
- Optional “show cosmetic polish” merchant toggle
