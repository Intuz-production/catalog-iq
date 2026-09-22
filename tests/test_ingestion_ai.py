"""
CatalogIQ — Phase 2 AI ingest analysis tests.

Mocks Groq. Verifies pending rewrites and extra issues without applying them.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.schemas import (
    Product,
    ProductStatus,
    DataIssue,
    IngestionJob,
    IssueType,
    IssueSeverity,
    ReviewStatus,
    SuggestionSource,
)
from app.services import ingestion_service
from app.services.ingestion_ai_service import (
    analyze_product_with_payload,
    parse_ingest_payload,
    persist_product_analysis,
    run_ingestion_ai_job,
    sanitize_rewrite,
)


@pytest.fixture
def db_session():
    """Isolated in-memory database with one imported product and a job."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    job = IngestionJob(
        filename="sample.csv",
        status="analyzing",
        started_at=datetime.utcnow(),
        ai_analyzed_rows=0,
        ai_error_count=0,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    product = Product(
        sku="WALLET-001",
        title="lthr wlt",
        description="blk leather",
        category="bags",
        brand="acme",
        price=19.0,
        currency="USD",
        status=ProductStatus.FLAGGED,
        attributes={"color": "blk"},
        raw_data={"sku": "WALLET-001", "title": "lthr wlt", "price": "19"},
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    yield session, product, job
    session.close()


SAMPLE_REWRITE = {
    "rewrite": {
        "title": "Leather Wallet",
        "description": "Black leather wallet.",
        "category": "Bags",
        "brand": "Acme",
        "price": "19",
        "attributes": {"color": "Black"},
    },
    "field_reasons": {"title": "Expanded abbreviation"},
    "extra_issues": [
        {
            "issue_type": "missing_attributes",
            "field_name": "material",
            "severity": "low",
            "description": "Material is not listed as its own attribute.",
            "actual_value": None,
            "suggested_value": "Leather",
        }
    ],
}


class TestParseAndSanitize:
    """Prompt JSON parsing and hallucination guards."""

    def test_parse_ingest_payload(self):
        raw = (
            '{"rewrite": {"title": "Leather Wallet", "description": "x", '
            '"category": "Bags", "brand": "Acme", "price": "19", '
            '"attributes": {"color": "Black"}}, "extra_issues": []}'
        )
        parsed = parse_ingest_payload(raw)
        assert parsed["rewrite"]["title"] == "Leather Wallet"
        assert parsed["extra_issues"] == []

    def test_sanitize_drops_invented_price(self, db_session):
        _session, product, _job = db_session
        rewrite = {
            "title": "Leather Wallet",
            "description": "Black leather wallet.",
            "category": "Bags",
            "brand": "Acme",
            "price": "9999",
            "attributes": {"color": "Black"},
        }
        sanitized = sanitize_rewrite(product, rewrite)
        assert sanitized["price"] == "19"
        assert sanitized["title"] == "Leather Wallet"

    def test_sanitize_keeps_equivalent_price_tokens(self, db_session):
        _session, product, _job = db_session
        rewrite = {
            "title": "Leather Wallet",
            "description": "Black leather wallet.",
            "category": "Bags",
            "brand": "Acme",
            "price": "19.00",
            "attributes": {"color": "Black"},
        }
        sanitized = sanitize_rewrite(product, rewrite)
        assert sanitized["price"] == "19.00"


class TestPersistAnalysis:
    """AI field changes are stored as issues; live product fields stay unchanged."""

    def test_persist_does_not_mutate_product(self, db_session):
        session, product, job = db_session
        original_title = product.title
        analyze_product_with_payload(session, product, job.id, SAMPLE_REWRITE)
        session.refresh(product)

        assert product.title == original_title
        material = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "material",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
            DataIssue.resolved == False,  # noqa: E712
        ).one()
        assert material.suggested_value == "Leather"
        title = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "title",
            DataIssue.issue_type == IssueType.AI_INFERRED,
            DataIssue.resolved == False,  # noqa: E712
        ).one()
        assert title.suggested_value == "Leather Wallet"
        assert title.severity == IssueSeverity.LOW

    def test_unchanged_fields_are_not_stored(self, db_session):
        session, product, job = db_session
        analyze_product_with_payload(session, product, job.id, SAMPLE_REWRITE)

        stored_fields = {
            item.field_name
            for item in session.query(DataIssue).filter(
                DataIssue.product_id == product.id,
                DataIssue.resolved == False,  # noqa: E712
            )
        }

        # price 19.0 was returned unchanged as "19", so it needs no review.
        assert "price" not in stored_fields
        # Polish-only improvements are stored as reviewable suggestions.
        assert "title" in stored_fields
        assert "attributes.color" in stored_fields
        # Typed/extra findings still land.
        assert "material" in stored_fields

    def test_extra_issue_is_ai_sourced(self, db_session):
        session, product, job = db_session
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            SAMPLE_REWRITE["extra_issues"],
        )
        issue = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "material",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).first()
        assert issue is not None
        assert issue.issue_type == IssueType.MISSING_ATTRIBUTES
        assert issue.resolved is False

    def test_attaches_suggestion_to_rule_issue(self, db_session):
        session, product, job = db_session
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.THIN_CONTENT,
            severity=IssueSeverity.MEDIUM,
            description="Thin content",
            field_name="description",
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(issue)
        session.commit()

        analyze_product_with_payload(session, product, job.id, SAMPLE_REWRITE)
        session.refresh(issue)
        assert issue.suggested_value == "Black leather wallet."
        assert issue.suggestion_source == SuggestionSource.RULE.value
        # No duplicate AI_INFERRED issue for the same field.
        duplicates = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "description",
            DataIssue.issue_type == IssueType.AI_INFERRED,
        ).all()
        assert duplicates == []

    def test_does_not_delete_rule_issue_mislabeled_as_ai(self, db_session):
        session, product, job = db_session
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description="Missing description",
            field_name="description",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(issue)
        session.commit()

        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            SAMPLE_REWRITE["extra_issues"],
        )
        session.refresh(issue)
        assert issue.resolved is False
        assert issue.issue_type == IssueType.MISSING_DESCRIPTION

    def test_duplicate_extra_issue_does_not_relabel_rule(self, db_session):
        session, product, job = db_session
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.THIN_CONTENT,
            severity=IssueSeverity.MEDIUM,
            description="Thin content",
            field_name="description",
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(issue)
        session.commit()

        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "thin_content",
                    "field_name": "description",
                    "severity": "medium",
                    "description": "AI restating the same thin-content rule.",
                    "actual_value": "3 words",
                    "suggested_value": "Black leather wallet.",
                }
            ],
        )
        session.refresh(issue)
        assert issue.suggestion_source == SuggestionSource.RULE.value
        extras = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "description",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).all()
        assert extras == []

    def test_invented_size_suggestion_is_stripped(self, db_session):
        session, product, job = db_session
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "missing_attributes",
                    "field_name": "size",
                    "severity": "low",
                    "description": "Size attribute is missing.",
                    "actual_value": None,
                    "suggested_value": "e.g., Standard",
                }
            ],
        )
        extras = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "size",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).all()
        assert len(extras) == 1
        assert extras[0].suggested_value is None

    def test_hyphen_only_title_rewrite_is_ignored(self, db_session):
        session, product, job = db_session
        product.title = "Le Creuset Dutch Oven 5.5-Qt"
        session.commit()
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(
                product,
                {
                    **SAMPLE_REWRITE["rewrite"],
                    "title": "Le Creuset Dutch Oven 5.5‑Qt",
                },
            ),
            {"title": "Normalized hyphen"},
            [],
        )
        titles = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "title",
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        assert titles == []

    def test_prior_ai_extras_are_replaced(self, db_session):
        session, product, job = db_session
        session.add(DataIssue(
            product_id=product.id,
            issue_type=IssueType.AI_INFERRED,
            severity=IssueSeverity.LOW,
            description="Old leftover extra issue.",
            field_name="category",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        ))
        session.commit()

        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            SAMPLE_REWRITE["extra_issues"],
        )
        # Old leftover text is gone; category may return as a polish rewrite.
        leftovers = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "category",
            DataIssue.resolved == False,  # noqa: E712
            DataIssue.description == "Old leftover extra issue.",
        ).all()
        assert leftovers == []
        material = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "material",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        assert len(material) == 1

    def test_attaches_attribute_suggestion_to_legacy_rule_field(self, db_session):
        session, product, job = db_session
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.ATTRIBUTE_CONTRADICTION,
            severity=IssueSeverity.MEDIUM,
            description="Color is inconsistent",
            field_name="color",
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(issue)
        session.commit()

        analyze_product_with_payload(session, product, job.id, SAMPLE_REWRITE)
        session.refresh(issue)
        assert issue.suggested_value == "Black"

    def test_reingest_clears_pending_polish_without_recreating(self, db_session):
        session, product, job = db_session
        session.add(DataIssue(
            product_id=product.id,
            issue_type=IssueType.AI_INFERRED,
            severity=IssueSeverity.LOW,
            description="Old pending title rewrite",
            field_name="title",
            actual_value="lthr wlt",
            suggested_value="Old Pending Title",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        ))
        session.commit()

        analyze_product_with_payload(session, product, job.id, SAMPLE_REWRITE)

        pending = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "title",
            DataIssue.resolved == False,  # noqa: E712
            DataIssue.review_status == ReviewStatus.PENDING.value,
        ).all()
        assert len(pending) == 1
        assert pending[0].suggested_value == "Leather Wallet"
        assert pending[0].suggested_value != "Old Pending Title"

    def test_invented_number_suggestion_is_stripped(self, db_session):
        session, product, job = db_session
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "ai_inferred",
                    "field_name": "weight",
                    "severity": "low",
                    "description": "Invented a weight that is not in the row.",
                    "actual_value": None,
                    "suggested_value": "12.5kg",
                }
            ],
        )
        issue = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "weight",
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).first()
        assert issue is not None
        assert issue.suggested_value is None

    def test_thin_content_backfills_suggested_from_rewrite(self, db_session):
        session, product, job = db_session
        sanitized = sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"])
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitized,
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "thin_content",
                    "field_name": "description",
                    "severity": "medium",
                    "description": "Description is too short.",
                    "actual_value": product.description,
                    "suggested_value": None,
                }
            ],
        )
        thin = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.THIN_CONTENT,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).one()
        assert thin.suggested_value == sanitized["description"]

    def test_polish_only_rewrite_creates_ai_inferred_suggestions(self, db_session):
        session, product, job = db_session
        analyze_product_with_payload(session, product, job.id, {
            **SAMPLE_REWRITE,
            "extra_issues": [],
        })
        title_issue = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.field_name == "title",
            DataIssue.issue_type == IssueType.AI_INFERRED,
            DataIssue.resolved == False,  # noqa: E712
        ).one()
        assert title_issue.suggested_value == "Leather Wallet"
        assert title_issue.description == "Expanded abbreviation"
        assert title_issue.severity == IssueSeverity.LOW
        polish_issues = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.AI_INFERRED,
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        assert len(polish_issues) >= 1
        assert all(issue.suggested_value for issue in polish_issues)

    def test_typed_soft_extra_issues_are_persisted(self, db_session):
        session, product, job = db_session
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "thin_content",
                    "field_name": "description",
                    "severity": "medium",
                    "description": "Description is too short for catalog use.",
                    "actual_value": "blk leather",
                    "suggested_value": "Black leather wallet.",
                },
                {
                    "issue_type": "attribute_contradiction",
                    "field_name": "color",
                    "severity": "high",
                    "description": "Title implies black but attribute is abbreviated inconsistently.",
                    "actual_value": "blk",
                    "suggested_value": "blk",
                },
                {
                    "issue_type": "missing_attributes",
                    "field_name": "attributes",
                    "severity": "low",
                    "description": "Size and material attributes are missing.",
                    "actual_value": None,
                    "suggested_value": None,
                },
            ],
        )
        thin = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.THIN_CONTENT,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).one()
        assert thin.severity == IssueSeverity.MEDIUM
        contradiction = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.ATTRIBUTE_CONTRADICTION,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).one()
        assert contradiction.severity == IssueSeverity.HIGH
        missing = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.MISSING_ATTRIBUTES,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
        ).one()
        assert missing.severity == IssueSeverity.LOW

    def test_rerun_replaces_typed_ai_soft_issues_without_stacking(self, db_session):
        session, product, job = db_session
        session.add(DataIssue(
            product_id=product.id,
            issue_type=IssueType.THIN_CONTENT,
            severity=IssueSeverity.MEDIUM,
            description="Old AI thin content finding.",
            field_name="description",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        ))
        session.add(DataIssue(
            product_id=product.id,
            issue_type=IssueType.ATTRIBUTE_NOT_IN_COPY,
            severity=IssueSeverity.LOW,
            description="Old AI omission finding.",
            field_name="color",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        ))
        session.commit()

        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "thin_content",
                    "field_name": "description",
                    "severity": "medium",
                    "description": "Updated thin content finding.",
                    "actual_value": "blk leather",
                    "suggested_value": "Black leather wallet.",
                },
            ],
        )
        thin_rows = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.THIN_CONTENT,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        assert len(thin_rows) == 1
        assert thin_rows[0].description == "Updated thin content finding."
        omissions = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.ATTRIBUTE_NOT_IN_COPY,
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        assert omissions == []

    def test_hard_rule_issue_with_attached_suggestion_survives_rerun(self, db_session):
        session, product, job = db_session
        rule_issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description="Missing description",
            field_name="description",
            suggested_value="Black leather wallet.",
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(rule_issue)
        session.commit()

        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "thin_content",
                    "field_name": "description",
                    "severity": "medium",
                    "description": "Description copy is weak.",
                    "actual_value": "blk leather",
                    "suggested_value": "Black leather wallet.",
                },
            ],
        )
        session.refresh(rule_issue)
        assert rule_issue.resolved is False
        assert rule_issue.suggested_value == "Black leather wallet."
        assert rule_issue.suggestion_source == SuggestionSource.RULE.value

    def test_attribute_not_in_copy_extra_issue_is_dropped(self, db_session):
        session, product, job = db_session
        persist_product_analysis(
            session,
            product,
            job.id,
            sanitize_rewrite(product, SAMPLE_REWRITE["rewrite"]),
            SAMPLE_REWRITE["field_reasons"],
            [
                {
                    "issue_type": "attribute_not_in_copy",
                    "field_name": "weight",
                    "severity": "low",
                    "description": "Weight is not mentioned in title or description.",
                    "actual_value": "598g",
                    "suggested_value": "598g",
                },
                {
                    "issue_type": "ai_inferred",
                    "field_name": "brand",
                    "severity": "low",
                    "description": "Brand could be polished.",
                    "actual_value": "acme",
                    "suggested_value": "Acme",
                },
                {
                    "issue_type": "catalog_noise",
                    "field_name": "title",
                    "severity": "low",
                    "description": "Title abbreviation should be expanded.",
                    "actual_value": "lthr wlt",
                    "suggested_value": "Leather Wallet",
                },
            ],
        )
        soft = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.suggestion_source == SuggestionSource.AI.value,
            DataIssue.resolved == False,  # noqa: E712
        ).all()
        by_field = {issue.field_name: issue for issue in soft}
        assert "brand" in by_field
        assert "title" in by_field
        assert by_field["brand"].issue_type == IssueType.AI_INFERRED
        assert by_field["title"].issue_type == IssueType.AI_INFERRED
        assert by_field["title"].suggested_value == "Leather Wallet"
        omissions = session.query(DataIssue).filter(
            DataIssue.product_id == product.id,
            DataIssue.issue_type == IssueType.ATTRIBUTE_NOT_IN_COPY,
        ).all()
        assert omissions == []
        assert "weight" not in by_field or by_field["weight"].issue_type != IssueType.ATTRIBUTE_NOT_IN_COPY
        assert all(
            issue.issue_type != IssueType.ATTRIBUTE_NOT_IN_COPY for issue in soft
        )


class TestBuildIngestPrompt:
    """Prompt lets the model decide soft quality findings."""

    def test_prompt_lets_ai_decide_soft_quality(self, db_session):
        from app.services.ingestion_ai_service import build_ingest_prompt

        _session, product, _job = db_session
        prompt = build_ingest_prompt(product, [])
        assert "ready-to-use catalog product" in prompt
        assert "Review EVERY field" in prompt
        assert "FULL product JSON" in prompt
        assert "ONLY when" in prompt
        assert "ready-to-use listing rewrite" in prompt or "ALWAYS provide suggested_value" in prompt
        assert "Do not complain about missing warranty" in prompt
        assert "ai_inferred" in prompt
        assert "attribute_not_in_copy" not in prompt
        assert "Do NOT flag an attribute merely because it is absent" in prompt
        assert "Soft quality" in prompt


class TestRunIngestionAiJob:
    """Background job uses a mocked Groq call."""

    def test_mocked_job_writes_suggestions(self, db_session):
        session, product, job = db_session
        engine = session.get_bind()
        product_id = product.id
        job_id = job.id
        original_title = product.title

        with patch(
            "app.services.ingestion_ai_service.SessionLocal",
            sessionmaker(bind=engine),
        ), patch(
            "app.services.ingestion_ai_service.request_product_rewrite",
            return_value=SAMPLE_REWRITE,
        ):
            run_ingestion_ai_job(job_id, [product_id])

        verify = sessionmaker(bind=engine)()
        stored_job = verify.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert stored_job.status == "completed"
        assert stored_job.ai_analyzed_rows == 1
        open_count = verify.query(DataIssue).filter(
            DataIssue.product_id == product_id,
            DataIssue.resolved == False,
        ).count()
        assert stored_job.issues_found == open_count
        count = verify.query(DataIssue).filter(
            DataIssue.product_id == product_id,
            DataIssue.resolved == False,  # noqa: E712
            DataIssue.suggested_value.isnot(None),
        ).count()
        # SAMPLE_REWRITE stores polish rewrites plus the material soft finding.
        assert count >= 2
        material = verify.query(DataIssue).filter(
            DataIssue.product_id == product_id,
            DataIssue.field_name == "material",
            DataIssue.resolved == False,  # noqa: E712
        ).one()
        assert material.suggested_value == "Leather"
        title = verify.query(DataIssue).filter(
            DataIssue.product_id == product_id,
            DataIssue.field_name == "title",
            DataIssue.issue_type == IssueType.AI_INFERRED,
            DataIssue.resolved == False,  # noqa: E712
        ).one()
        assert title.suggested_value == "Leather Wallet"
        live = verify.query(Product).filter(Product.id == product_id).first()
        assert live.title == original_title
        assert live.ai_analysis_status == "done"
        verify.close()

    def test_missing_llm_key_fails_job_once(self, db_session):
        session, product, job = db_session
        engine = session.get_bind()
        product_id = product.id
        job_id = job.id

        with patch(
            "app.services.ingestion_ai_service.SessionLocal",
            sessionmaker(bind=engine),
        ), patch(
            "app.services.ingestion_ai_service.settings.LLM_PROVIDER",
            "groq",
        ), patch(
            "app.services.ingestion_ai_service.settings.GROQ_API_KEY",
            "",
        ), patch(
            "app.services.ingestion_ai_service.request_product_rewrite",
        ) as mock_rewrite:
            run_ingestion_ai_job(job_id, [product_id])

        mock_rewrite.assert_not_called()
        verify = sessionmaker(bind=engine)()
        stored_job = verify.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert stored_job.status == "completed_with_ai_errors"
        assert stored_job.ai_analyzed_rows == 0
        assert stored_job.error_message
        assert "GROQ_API_KEY" in stored_job.error_message
        live = verify.query(Product).filter(Product.id == product_id).first()
        assert live.ai_analysis_status == "failed"
        verify.close()

    def test_product_failure_records_sku(self, db_session):
        session, product, job = db_session
        engine = session.get_bind()
        product_id = product.id
        job_id = job.id

        with patch(
            "app.services.ingestion_ai_service.SessionLocal",
            sessionmaker(bind=engine),
        ), patch(
            "app.services.ingestion_ai_service.request_product_rewrite",
            side_effect=RuntimeError("timeout"),
        ):
            run_ingestion_ai_job(job_id, [product_id])

        verify = sessionmaker(bind=engine)()
        stored_job = verify.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert stored_job.status == "completed_with_ai_errors"
        assert stored_job.ai_error_count == 1
        assert product.sku in (stored_job.error_message or "")
        verify.close()


class TestProcessCsvAnalyzing:
    """Parse+rules leaves the job in analyzing for the AI pass."""

    def test_successful_parse_sets_analyzing(self, db_session):
        session, _product, _job = db_session
        csv_bytes = (
            b"sku,title,description,category,brand,price\n"
            b"CSV-001,Test Item,A short desc,Home,BrandX,12.5\n"
        )
        result, product_ids = ingestion_service.process_csv(
            session, csv_bytes, "feed.csv"
        )
        assert result.status == "analyzing"
        assert len(product_ids) == 1
        assert result.completed_at is None

    def test_empty_csv_fails_job(self, db_session):
        session, _product, _job = db_session
        result, product_ids = ingestion_service.process_csv(
            session, b"sku,title\n", "empty.csv"
        )
        assert result.status == "failed"
        assert product_ids == []
        assert result.error_message

    def test_custom_column_mapping(self, db_session):
        session, _product, _job = db_session
        csv_bytes = (
            b"code,label,notes\n"
            b"MAP-001,Mapped Lamp,desk lamp\n"
        )
        result, product_ids = ingestion_service.process_csv(
            session,
            csv_bytes,
            "mapped.csv",
            column_mapping={"sku": "code", "title": "label", "description": "notes"},
        )
        assert result.status == "analyzing"
        assert len(product_ids) == 1
        stored = session.query(Product).filter(Product.sku == "MAP-001").first()
        assert stored is not None
        assert stored.title == "Mapped Lamp"
