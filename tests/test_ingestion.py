"""
CatalogIQ — Ingestion Pipeline Tests

Tests for CSV parsing, data normalization, and quality detection.
"""

import pytest
from app.utils.helpers import (
    normalize_text,
    normalize_attribute_value,
    is_placeholder_value,
    clean_text_field,
    parse_catalog_price,
)


class TestNormalizeText:
    """Tests for text normalization."""

    def test_strips_whitespace(self):
        assert normalize_text("  hello world  ") == "hello world"

    def test_collapses_multiple_spaces(self):
        assert normalize_text("hello   world") == "hello world"

    def test_handles_empty_string(self):
        assert normalize_text("") == ""

    def test_handles_none(self):
        assert normalize_text(None) == ""

    def test_handles_tabs_and_newlines(self):
        assert normalize_text("hello\t\nworld") == "hello world"


class TestNormalizeAttributeValue:
    """Tests for product attribute normalization."""

    def test_size_normalization(self):
        assert normalize_attribute_value("size", "extra small") == "XS"
        assert normalize_attribute_value("size", "sm") == "S"
        assert normalize_attribute_value("size", "medium") == "M"
        assert normalize_attribute_value("size", "lg") == "L"
        assert normalize_attribute_value("size", "extra large") == "XL"

    def test_color_normalization(self):
        assert normalize_attribute_value("color", "blk") == "Black"
        assert normalize_attribute_value("color", "wht") == "White"
        assert normalize_attribute_value("color", "blu") == "Blue"

    def test_material_normalization(self):
        assert normalize_attribute_value("material", "ss") == "Stainless Steel"
        assert normalize_attribute_value("material", "ctn") == "Cotton"
        assert normalize_attribute_value("material", "nyl") == "Nylon"

    def test_unknown_values_title_cased(self):
        assert normalize_attribute_value("color", "midnight blue") == "Midnight Blue"

    def test_empty_value(self):
        assert normalize_attribute_value("size", "") == ""


class TestPlaceholderValues:
    """Tests for placeholder supplier value handling."""

    def test_detects_common_placeholders(self):
        assert is_placeholder_value("n/a") is True
        assert is_placeholder_value("N/A") is True
        assert is_placeholder_value("tbd") is True
        assert is_placeholder_value("-") is True

    def test_keeps_real_values(self):
        assert is_placeholder_value("Black") is False
        assert is_placeholder_value("Premium leather wallet") is False

    def test_clean_text_field_drops_placeholder(self):
        assert clean_text_field("n/a") is None
        assert clean_text_field("  Real description  ") == "Real description"


class TestParseCatalogPrice:
    """Tests for supplier price parsing."""

    def test_currency_symbols_and_commas(self):
        assert parse_catalog_price("$1,299.00") == 1299.00
        assert parse_catalog_price("USD 12.50") == 12.50

    def test_empty_and_unreadable(self):
        assert parse_catalog_price("n/a") is None
        assert parse_catalog_price("ask") is None


class TestParseSupplierCsv:
    """Tests for encoding, delimiter detection, and preview mapping."""

    def test_semicolon_delimited(self):
        from app.services.ingestion_service import parse_supplier_csv

        parsed = parse_supplier_csv(b"sku;title;price\nSEMI-1;Widget;9.99\n")
        assert parsed.delimiter == ";"
        assert list(parsed.dataframe.columns) == ["sku", "title", "price"]
        assert len(parsed.dataframe) == 1

    def test_utf8_bom(self):
        from app.services.ingestion_service import parse_supplier_csv

        parsed = parse_supplier_csv(b"\xef\xbb\xbfsku,title\nBOM-1,Shoes\n")
        assert parsed.encoding.startswith("utf-8")
        assert "sku" in parsed.dataframe.columns
        assert parsed.dataframe.iloc[0]["sku"] == "BOM-1"

    def test_latin1_bytes(self):
        from app.services.ingestion_service import parse_supplier_csv

        raw = "sku,title\nLAT-1,Caf\u00e9 Table\n".encode("latin-1")
        parsed = parse_supplier_csv(raw)
        assert "Caf" in str(parsed.dataframe.iloc[0]["title"])

    def test_preview_suggests_sku_and_specs(self):
        from app.services.ingestion_service import preview_csv

        preview = preview_csv(
            b"item_id,name,specs,price\nA1,Lamp,metal,12\n",
            filename="feed.csv",
        )
        assert preview.suggested_mapping["sku"] == "item_id"
        assert preview.suggested_mapping["title"] == "name"
        assert preview.suggested_mapping["specifications"] == "specs"
        assert preview.total_rows == 1
        assert preview.sample_rows[0]["item_id"] == "A1"

    def test_preview_empty_file_raises(self):
        from app.services.ingestion_service import CsvParseError, preview_csv

        with pytest.raises(CsvParseError):
            preview_csv(b"sku,title\n", filename="empty.csv")


@pytest.fixture
def ingestion_db():
    """Isolated in-memory database for row upsert tests."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestProcessCsvNormalizeAndUpsert:
    """Per-row normalize, skip handling, and create/update behavior."""

    def test_blank_sku_is_skipped_and_other_rows_ingest(self, ingestion_db):
        from app.models.schemas import Product
        from app.services.ingestion_service import process_csv

        csv_bytes = (
            b"sku,title,price\n"
            b",Missing Sku,9.99\n"
            b"GOOD-1,Keep Me,10\n"
            b"n/a,Placeholder Sku,11\n"
        )
        result, product_ids = process_csv(ingestion_db, csv_bytes, "skip.csv")
        assert result.status == "analyzing"
        assert result.processed_rows == 3
        assert result.new_products == 1
        assert len(product_ids) == 1
        assert result.skipped_rows == 2
        assert result.skip_summary is not None
        assert result.skip_summary["counts"]["blank_sku"] == 2
        assert len(result.skip_summary["samples"]["blank_sku"]) <= 5
        assert ingestion_db.query(Product).filter(Product.sku == "GOOD-1").one().title == "Keep Me"

    def test_all_blank_skus_fail_the_job(self, ingestion_db):
        from app.services.ingestion_service import process_csv

        result, product_ids = process_csv(
            ingestion_db,
            b"sku,title\n,No Sku\nN/A,Also None\n",
            "blank.csv",
        )
        assert result.status == "failed"
        assert product_ids == []
        assert "blank_sku" in (result.error_message or "")
        assert result.skipped_rows == 2
        assert result.skip_summary is not None
        assert result.skip_summary["counts"]["blank_sku"] == 2

    def test_missing_title_falls_back_to_sku(self, ingestion_db):
        from app.models.schemas import Product
        from app.services.ingestion_service import process_csv

        process_csv(ingestion_db, b"sku,title,price\nSKU-TITLE,,5\n", "title.csv")
        product = ingestion_db.query(Product).filter(Product.sku == "SKU-TITLE").one()
        assert product.title == "SKU-TITLE"

    def test_update_keeps_existing_fields_when_csv_is_blank(self, ingestion_db):
        from app.models.schemas import Product, ProductStatus
        from app.services.ingestion_service import process_csv

        existing = Product(
            sku="KEEP-1",
            title="Original Title",
            description="Keep this description",
            category="Bags",
            brand="Acme",
            price=19.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M"},
        )
        ingestion_db.add(existing)
        ingestion_db.commit()

        result, _ids = process_csv(
            ingestion_db,
            b"sku,title,description,color,price\nKEEP-1,,,Blue,24.5\n",
            "update.csv",
        )
        assert result.updated_products == 1
        product = ingestion_db.query(Product).filter(Product.sku == "KEEP-1").one()
        assert product.title == "Original Title"
        assert product.description == "Keep this description"
        assert product.price == 24.5
        assert product.attributes["color"] == "Blue"
        assert product.attributes["size"] == "M"

    def test_price_symbols_parse_and_unreadable_price_is_ignored(self, ingestion_db):
        from app.models.schemas import Product
        from app.services.ingestion_service import process_csv

        csv_bytes = (
            b"sku,title,price\n"
            b"P-1,Priced,\"$1,299.00\"\n"
            b"P-2,No Price,ask\n"
        )
        process_csv(ingestion_db, csv_bytes, "price.csv")
        priced = ingestion_db.query(Product).filter(Product.sku == "P-1").one()
        unpriced = ingestion_db.query(Product).filter(Product.sku == "P-2").one()
        assert priced.price == 1299.00
        assert unpriced.price is None

    def test_integer_sku_does_not_keep_decimal(self, ingestion_db):
        from app.models.schemas import Product
        from app.services.ingestion_service import process_csv

        process_csv(ingestion_db, b"sku,title\n1001,Numeric Sku\n", "intsku.csv")
        assert ingestion_db.query(Product).filter(Product.sku == "1001").one().title == "Numeric Sku"

    def test_products_are_listed_by_uploaded_file(self, ingestion_db):
        from app.models.schemas import IngestionJobProduct
        from app.services.ingestion_service import process_csv
        from app.services.product_service import get_products

        first, _ids = process_csv(
            ingestion_db,
            b"sku,title,price\nA-1,Alpha,10\n",
            "alpha.csv",
        )
        second, _ids = process_csv(
            ingestion_db,
            b"sku,title,price\nB-1,Beta,12\nA-1,Alpha Updated,11\n",
            "beta.csv",
        )

        first_products, first_total = get_products(
            ingestion_db, ingestion_job_id=first.id
        )
        second_products, second_total = get_products(
            ingestion_db, ingestion_job_id=second.id
        )

        assert first_total == 1
        assert {product.sku for product in first_products} == {"A-1"}
        assert second_total == 2
        assert {product.sku for product in second_products} == {"A-1", "B-1"}
        assert ingestion_db.query(IngestionJobProduct).count() == 3


def _issue_types(pending) -> set[str]:
    return {issue.issue_type.value for issue in pending}


class TestQualityRules:
    """Hard structural ingestion quality rules, issue sync, and job issue counts."""

    def test_placeholder_description_is_missing(self, ingestion_db):
        from app.models.schemas import IssueType, Product, ProductStatus
        from app.services.ingestion_service import _collect_pending_issues

        product = Product(
            sku="DESC-1",
            title="Leather Wallet",
            description="n/a",
            price=19.0,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Leather"},
        )
        pending = _collect_pending_issues(ingestion_db, product, product.attributes)
        assert IssueType.MISSING_DESCRIPTION.value in _issue_types(pending)
        assert IssueType.THIN_CONTENT.value not in _issue_types(pending)

    def test_soft_quality_types_are_not_emitted_by_rules(self, ingestion_db):
        from app.models.schemas import IssueType, Product, ProductStatus
        from app.services.ingestion_service import _collect_pending_issues

        product = Product(
            sku="SOFT-1",
            title="Nike Air Max 90 Running Shoes",
            description="Too short.",
            price=129.99,
            status=ProductStatus.ACTIVE,
            attributes={"color": "White", "size": "10"},
        )
        pending = _collect_pending_issues(ingestion_db, product, product.attributes)
        types = _issue_types(pending)
        assert IssueType.THIN_CONTENT.value not in types
        assert IssueType.ATTRIBUTE_CONTRADICTION.value not in types
        assert IssueType.ATTRIBUTE_NOT_IN_COPY.value not in types
        assert IssueType.MISSING_ATTRIBUTES.value not in types

    def test_missing_and_unreadable_prices_are_anomalies(self, ingestion_db):
        from app.models.schemas import IssueSeverity, IssueType, Product, ProductStatus
        from app.services.ingestion_service import _collect_pending_issues

        missing_price = Product(
            sku="PRICE-1",
            title="No Price Item",
            description=(
                "A complete product description with several sentences so "
                "quality scoring does not treat this listing as thin content. "
                "The only problem on this record is a missing catalog price."
            ),
            price=None,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        pending = _collect_pending_issues(ingestion_db, missing_price, missing_price.attributes)
        prices = [item for item in pending if item.issue_type == IssueType.PRICE_ANOMALY]
        assert len(prices) == 1
        assert prices[0].severity == IssueSeverity.MEDIUM

        unreadable = Product(
            sku="PRICE-2",
            title="Unreadable Price Item",
            description=missing_price.description,
            price=None,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        pending = _collect_pending_issues(
            ingestion_db,
            unreadable,
            unreadable.attributes,
            price_unreadable=True,
        )
        prices = [item for item in pending if item.issue_type == IssueType.PRICE_ANOMALY]
        assert len(prices) == 1
        assert "unreadable" in prices[0].description.lower()

    def test_zero_price_is_critical(self, ingestion_db):
        from app.models.schemas import IssueSeverity, IssueType, Product, ProductStatus
        from app.services.ingestion_service import _collect_pending_issues

        product = Product(
            sku="PRICE-0",
            title="Zero Dollar Item",
            description=(
                "This listing includes a full description so the only quality "
                "rule under test is an invalid zero price on the product record."
            ),
            price=0,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        pending = _collect_pending_issues(ingestion_db, product, product.attributes)
        prices = [item for item in pending if item.issue_type == IssueType.PRICE_ANOMALY]
        assert len(prices) == 1
        assert prices[0].severity == IssueSeverity.CRITICAL

    def test_duplicate_title_names_the_other_sku(self, ingestion_db):
        from app.models.schemas import (
            IngestionJob,
            IngestionJobProduct,
            IssueType,
            Product,
            ProductStatus,
        )
        from app.services.ingestion_service import _collect_pending_issues

        job = IngestionJob(
            filename="dupes.csv",
            status="completed",
            total_rows=2,
            processed_rows=2,
        )
        first = Product(
            sku="DUP-1",
            title="Shared Title",
            description="Enough words here to skip thin content with two sentences present.",
            price=10.0,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        second = Product(
            sku="DUP-2",
            title="shared title",
            description="Enough words here to skip thin content with two sentences present.",
            price=11.0,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        ingestion_db.add_all([job, first, second])
        ingestion_db.flush()
        first.last_ingestion_job_id = job.id
        second.last_ingestion_job_id = job.id
        ingestion_db.add_all([
            IngestionJobProduct(ingestion_job_id=job.id, product_id=first.id),
            IngestionJobProduct(ingestion_job_id=job.id, product_id=second.id),
        ])
        ingestion_db.commit()
        ingestion_db.refresh(second)

        pending = _collect_pending_issues(
            ingestion_db,
            second,
            second.attributes,
            ingestion_job_id=job.id,
        )
        duplicates = [item for item in pending if item.issue_type == IssueType.DUPLICATE_TITLE]
        assert len(duplicates) == 1
        assert "DUP-1" in duplicates[0].description

    def test_duplicate_title_ignores_other_upload_file(self, ingestion_db):
        from app.models.schemas import (
            IngestionJob,
            IngestionJobProduct,
            IssueType,
            Product,
            ProductStatus,
        )
        from app.services.ingestion_service import _collect_pending_issues

        old_job = IngestionJob(
            filename="old.csv",
            status="completed",
            total_rows=1,
            processed_rows=1,
        )
        new_job = IngestionJob(
            filename="new.csv",
            status="completed",
            total_rows=1,
            processed_rows=1,
        )
        older = Product(
            sku="SKU-001",
            title="Nike Air Max 90 Running Shoes",
            description="Classic shoes with enough words for a full sentence here.",
            price=129.99,
            status=ProductStatus.ACTIVE,
            attributes={},
        )
        newer = Product(
            sku="CTRL-001",
            title="Nike Air Max 90 Running Shoes",
            description="Classic shoes with enough words for a full sentence here.",
            price=129.99,
            status=ProductStatus.ACTIVE,
            attributes={},
        )
        ingestion_db.add_all([old_job, new_job, older, newer])
        ingestion_db.flush()
        older.last_ingestion_job_id = old_job.id
        newer.last_ingestion_job_id = new_job.id
        ingestion_db.add_all([
            IngestionJobProduct(ingestion_job_id=old_job.id, product_id=older.id),
            IngestionJobProduct(ingestion_job_id=new_job.id, product_id=newer.id),
        ])
        ingestion_db.commit()
        ingestion_db.refresh(newer)

        pending = _collect_pending_issues(
            ingestion_db,
            newer,
            newer.attributes,
            ingestion_job_id=new_job.id,
        )
        duplicates = [item for item in pending if item.issue_type == IssueType.DUPLICATE_TITLE]
        assert duplicates == []

    def test_reingest_does_not_duplicate_or_recount_open_issues(self, ingestion_db):
        from app.models.schemas import DataIssue, IssueType
        from app.services.ingestion_service import process_csv

        csv_bytes = (
            b"sku,title,description,color,size,material,price\n"
            b"Q-1,Quality Black Cotton Item,n/a,Black,M,Cotton,ask\n"
        )
        first, _ids = process_csv(ingestion_db, csv_bytes, "quality-1.csv")
        open_issues = ingestion_db.query(DataIssue).filter(DataIssue.resolved == False).all()
        types = {issue.issue_type for issue in open_issues}
        assert IssueType.MISSING_DESCRIPTION in types
        assert IssueType.PRICE_ANOMALY in types
        assert IssueType.THIN_CONTENT not in types
        assert IssueType.MISSING_ATTRIBUTES not in types
        assert first.issues_found == len(open_issues)

        second, _ids = process_csv(ingestion_db, csv_bytes, "quality-2.csv")
        after = ingestion_db.query(DataIssue).filter(DataIssue.resolved == False).count()
        assert after == len(open_issues)
        assert second.issues_found == after
        assert second.updated_products == 1

    def test_adequate_description_creates_no_hard_content_issue(self, ingestion_db):
        from app.models.schemas import DataIssue, IssueType, Product, ProductStatus
        from app.services.ingestion_service import _run_quality_checks

        product = Product(
            sku="OK-1",
            title="Short Copy Item",
            description="Too short.",
            price=15.0,
            status=ProductStatus.ACTIVE,
            attributes={"color": "Black", "size": "M", "material": "Steel"},
        )
        ingestion_db.add(product)
        ingestion_db.commit()
        ingestion_db.refresh(product)

        created = _run_quality_checks(ingestion_db, product, dict(product.attributes))
        soft_types = {
            IssueType.THIN_CONTENT,
            IssueType.ATTRIBUTE_CONTRADICTION,
            IssueType.ATTRIBUTE_NOT_IN_COPY,
            IssueType.MISSING_ATTRIBUTES,
        }
        assert all(issue.issue_type not in soft_types for issue in created)
        open_soft = (
            ingestion_db.query(DataIssue)
            .filter(
                DataIssue.product_id == product.id,
                DataIssue.issue_type.in_(list(soft_types)),
                DataIssue.resolved == False,
            )
            .count()
        )
        assert open_soft == 0


class TestIngestionGroups:
    """Append into an existing group and rename group_name."""

    def test_process_csv_sets_group_name(self, ingestion_db):
        from app.services.ingestion_service import process_csv

        result, _ids = process_csv(
            ingestion_db,
            b"sku,title,price\nG-1,Group Item,9.99\n",
            "feed.csv",
            group_name=" Spring Catalog ",
        )
        assert result.group_name == "Spring Catalog"
        assert result.filename == "feed.csv"

    def test_append_to_existing_job_reuses_job(self, ingestion_db):
        from app.models.schemas import IngestionJob, IngestionJobProduct, Product
        from app.services.ingestion_service import process_csv

        first, first_ids = process_csv(
            ingestion_db,
            b"sku,title,price\nA-1,Alpha Item,10\n",
            "batch-a.csv",
            group_name="Main Catalog",
        )
        job = ingestion_db.query(IngestionJob).filter_by(id=first.id).one()
        job.status = "completed"
        ingestion_db.commit()

        second, second_ids = process_csv(
            ingestion_db,
            b"sku,title,price\nB-1,Beta Item,12\n",
            "batch-b.csv",
            ingestion_job_id=first.id,
        )
        assert second.id == first.id
        assert second.filename == "batch-b.csv"
        assert second.group_name == "Main Catalog"
        assert second.new_products == 2
        assert second.total_rows == 2
        assert len(second_ids) == 1
        assert set(first_ids + second_ids) == {
            p.id for p in ingestion_db.query(Product).all()
        }
        links = (
            ingestion_db.query(IngestionJobProduct)
            .filter(IngestionJobProduct.ingestion_job_id == first.id)
            .count()
        )
        assert links == 2

    def test_append_rejects_failed_job(self, ingestion_db):
        from app.models.schemas import IngestionJob
        from app.services.ingestion_service import IngestionJobError, process_csv

        job = IngestionJob(filename="bad.csv", group_name="Broken", status="failed")
        ingestion_db.add(job)
        ingestion_db.commit()
        ingestion_db.refresh(job)

        with pytest.raises(IngestionJobError) as exc_info:
            process_csv(
                ingestion_db,
                b"sku,title,price\nC-1,Item,1\n",
                "retry.csv",
                ingestion_job_id=job.id,
            )
        assert exc_info.value.status_code == 400

    def test_append_renames_existing_group(self, ingestion_db):
        from app.models.schemas import IngestionJob
        from app.services.ingestion_service import process_csv

        first, _ids = process_csv(
            ingestion_db,
            b"sku,title,price\nN-1,Named Item,10\n",
            "old-name.csv",
            group_name="Old Group",
        )
        job = ingestion_db.query(IngestionJob).filter_by(id=first.id).one()
        job.status = "completed"
        ingestion_db.commit()

        second, _ids2 = process_csv(
            ingestion_db,
            b"sku,title,price\nN-2,Another Item,12\n",
            "more.csv",
            ingestion_job_id=first.id,
            group_name="Renamed Group",
        )
        assert second.id == first.id
        assert second.group_name == "Renamed Group"
        assert second.filename == "more.csv"

    def test_rename_group_name(self, ingestion_db):
        from app.services.ingestion_service import (
            process_csv,
            update_ingestion_job_group_name,
        )

        result, _ids = process_csv(
            ingestion_db,
            b"sku,title,price\nR-1,Rename Me,5\n",
            "rename.csv",
            group_name="Old Name",
        )
        updated = update_ingestion_job_group_name(
            ingestion_db, result.id, "  New Name  "
        )
        assert updated is not None
        assert updated.group_name == "New Name"
        assert updated.filename == "rename.csv"
