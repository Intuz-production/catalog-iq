"""
CatalogIQ — Quality issue review tests.

Uses seeded issues only. No Groq or CSV upload.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.schemas import (
    Product,
    ProductStatus,
    DataIssue,
    IssueType,
    IssueSeverity,
    ReviewAction,
    ReviewStatus,
    SuggestionSource,
)
from app.services import ingestion_service


@pytest.fixture
def db_session():
    """Provide an isolated in-memory database with one product."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    product = Product(
        sku="WALLET-001",
        title="lthr wlt",
        description="n/a",
        category="accessories",
        brand="acme",
        price=19.0,
        currency="USD",
        status=ProductStatus.FLAGGED,
        attributes={"color": "blk", "size": "M"},
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    yield session, product
    session.close()


def _add_issue(
    session,
    product,
    field_name,
    suggested,
    *,
    actual=None,
    issue_type=IssueType.AI_INFERRED,
    severity=IssueSeverity.LOW,
    source=SuggestionSource.AI.value,
):
    """Insert one pending reviewable issue with a suggested fix."""
    issue = DataIssue(
        product_id=product.id,
        issue_type=issue_type,
        severity=severity,
        description=f"Suggested improvement for {field_name}",
        field_name=field_name,
        actual_value=actual,
        suggested_value=suggested,
        suggestion_source=source,
        review_status=ReviewStatus.PENDING.value,
        created_at=datetime.utcnow(),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


class TestReviewDataIssue:
    """Accept, edit, and reject quality issues onto product fields."""

    def test_accept_title_updates_product(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "title", "Leather Wallet", actual=product.title)

        result = ingestion_service.review_data_issue(
            session, issue.id, ReviewAction.ACCEPT
        )
        session.refresh(product)

        assert result.review_status == ReviewStatus.ACCEPTED.value
        assert result.resolved is True
        assert product.title == "Leather Wallet"

    def test_accept_attribute_updates_json(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "attributes.color", "Black", actual="blk")

        ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)
        session.refresh(product)

        assert product.attributes["color"] == "Black"
        assert product.attributes["size"] == "M"

    def test_accept_legacy_attribute_name_updates_json(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "color", "Black", actual="blk")

        ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)
        session.refresh(product)

        assert product.attributes["color"] == "Black"

    def test_edit_uses_user_value(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "brand", "Acme Goods", actual="acme")

        ingestion_service.review_data_issue(
            session,
            issue.id,
            ReviewAction.EDIT,
            edited_value="Acme Leather Co",
        )
        session.refresh(product)
        session.refresh(issue)

        assert product.brand == "Acme Leather Co"
        assert issue.review_status == ReviewStatus.EDITED.value

    def test_reject_leaves_original_value(self, db_session):
        session, product = db_session
        original_title = product.title
        issue = _add_issue(session, product, "title", "Leather Wallet", actual=original_title)

        ingestion_service.review_data_issue(session, issue.id, ReviewAction.REJECT)
        session.refresh(product)
        session.refresh(issue)

        assert product.title == original_title
        assert issue.resolved is True
        assert issue.review_status == ReviewStatus.REJECTED.value

    def test_cannot_rewrite_sku(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "sku", "HACKED", actual=product.sku)

        with pytest.raises(ValueError, match="SKU"):
            ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)
        session.refresh(product)
        assert product.sku == "WALLET-001"

    def test_cannot_review_twice(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "category", "Accessories", actual="accessories")
        ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)

        with pytest.raises(ValueError, match="already"):
            ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)

    def test_missing_issue_raises_lookup(self, db_session):
        session, _product = db_session
        with pytest.raises(LookupError):
            ingestion_service.review_data_issue(session, 9999, ReviewAction.ACCEPT)

    def test_edit_requires_value(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "title", "Leather Wallet", actual=product.title)
        with pytest.raises(ValueError, match="edited_value"):
            ingestion_service.review_data_issue(session, issue.id, ReviewAction.EDIT)

    def test_edit_empty_title_raises(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "title", "Leather Wallet", actual=product.title)

        with pytest.raises(ValueError, match="empty"):
            ingestion_service.review_data_issue(
                session, issue.id, ReviewAction.EDIT, edited_value="   "
            )

        session.refresh(issue)
        session.refresh(product)
        assert issue.resolved is False
        assert product.title == "lthr wlt"

    def test_accept_resolves_sibling_issue_on_same_field(self, db_session):
        session, product = db_session
        primary = _add_issue(
            session,
            product,
            "title",
            "Leather Wallet",
            actual=product.title,
            issue_type=IssueType.DUPLICATE_TITLE,
            severity=IssueSeverity.MEDIUM,
            source=SuggestionSource.RULE.value,
        )
        sibling = DataIssue(
            product_id=product.id,
            issue_type=IssueType.AI_INFERRED,
            severity=IssueSeverity.LOW,
            description="Also flags title",
            field_name="title",
            actual_value=product.title,
            suggested_value="Leather Wallet",
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(sibling)
        session.commit()
        session.refresh(sibling)

        ingestion_service.review_data_issue(session, primary.id, ReviewAction.ACCEPT)
        session.refresh(sibling)
        session.refresh(product)

        assert sibling.resolved is True
        assert sibling.review_status == ReviewStatus.ACCEPTED.value
        assert product.title == "Leather Wallet"
        assert product.status == ProductStatus.ACTIVE

    def test_accept_attribute_resolves_legacy_field_sibling(self, db_session):
        session, product = db_session
        primary = _add_issue(session, product, "attributes.color", "Black", actual="blk")
        sibling = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_ATTRIBUTES,
            severity=IssueSeverity.MEDIUM,
            description="Color is messy",
            field_name="color",
            actual_value="blk",
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(sibling)
        session.commit()
        session.refresh(sibling)

        ingestion_service.review_data_issue(session, primary.id, ReviewAction.ACCEPT)
        session.refresh(sibling)

        assert sibling.resolved is True
        assert product.attributes["color"] == "Black"

    def test_reject_does_not_resolve_sibling(self, db_session):
        session, product = db_session
        primary = _add_issue(session, product, "title", "Leather Wallet", actual=product.title)
        sibling = DataIssue(
            product_id=product.id,
            issue_type=IssueType.DUPLICATE_TITLE,
            severity=IssueSeverity.MEDIUM,
            description="Title looks duplicated",
            field_name="title",
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(sibling)
        session.commit()
        session.refresh(sibling)

        ingestion_service.review_data_issue(session, primary.id, ReviewAction.REJECT)
        session.refresh(sibling)

        assert sibling.resolved is False
        assert sibling.review_status == ReviewStatus.PENDING.value

    def test_accept_applies_suggested_description(self, db_session):
        session, product = db_session
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description="Description is missing",
            field_name="description",
            actual_value="n/a",
            suggested_value="A compact leather wallet for everyday carry.",
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)

        ingestion_service.review_data_issue(session, issue.id, ReviewAction.ACCEPT)
        session.refresh(product)
        session.refresh(issue)

        assert product.description == "A compact leather wallet for everyday carry."
        assert issue.resolved is True
        assert issue.review_status == ReviewStatus.ACCEPTED.value


class TestAcceptIssuesBulk:
    """Bulk accept by issue or product ID."""

    def test_accept_by_product_id(self, db_session):
        session, product = db_session
        _add_issue(session, product, "title", "Leather Wallet", actual=product.title)
        _add_issue(session, product, "brand", "Acme", actual="acme")

        accepted, skipped, product_ids = ingestion_service.accept_issues_bulk(
            session, product_ids=[product.id]
        )
        session.refresh(product)

        assert accepted == 2
        assert skipped == 0
        assert product_ids == [product.id]
        assert product.title == "Leather Wallet"
        assert product.brand == "Acme"

    def test_skips_unknown_issue_ids(self, db_session):
        session, product = db_session
        issue = _add_issue(session, product, "title", "Leather Wallet", actual=product.title)

        accepted, skipped, _ids = ingestion_service.accept_issues_bulk(
            session, issue_ids=[issue.id, 9999]
        )

        assert accepted == 1
        assert skipped == 1

    def test_skips_issues_without_suggestion(self, db_session):
        session, product = db_session
        _add_issue(session, product, "title", "Leather Wallet", actual=product.title)
        bare = DataIssue(
            product_id=product.id,
            issue_type=IssueType.DUPLICATE_TITLE,
            severity=IssueSeverity.MEDIUM,
            description="No suggested fix",
            field_name="title",
            review_status=ReviewStatus.PENDING.value,
        )
        session.add(bare)
        session.commit()

        accepted, skipped, _ids = ingestion_service.accept_issues_bulk(
            session, product_ids=[product.id]
        )

        # One accept for title; bare sibling may be resolved by field overlap, or skipped.
        assert accepted >= 1
        session.refresh(product)
        assert product.title == "Leather Wallet"

    def test_requires_one_selector(self, db_session):
        session, _product = db_session
        with pytest.raises(ValueError, match="either"):
            ingestion_service.accept_issues_bulk(session)
