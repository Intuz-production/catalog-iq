"""
CatalogIQ — Product CRUD Service

Handles product database operations: listing, filtering,
creating, updating, and deleting products.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.schemas import (
    Product, DataIssue, CompetitorAlert, IngestionJob, IngestionJobProduct,
    ProductStatus, ProductSortField, SortOrder,
    ProductCreate, ProductUpdate, ProductResponse, DashboardStats,
)

SORT_COLUMNS = {
    ProductSortField.SKU: Product.sku,
    ProductSortField.TITLE: Product.title,
    ProductSortField.CATEGORY: Product.category,
    ProductSortField.BRAND: Product.brand,
    ProductSortField.PRICE: Product.price,
    ProductSortField.STATUS: Product.status,
    ProductSortField.UPDATED_AT: Product.updated_at,
}

logger = logging.getLogger("catalogiq.product_service")


def _build_products_query(
    db: Session,
    status: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    ingestion_job_id: Optional[int] = None,
):
    """Build a filtered product query without pagination or sorting."""
    query = db.query(Product)

    if ingestion_job_id is not None:
        query = query.join(
            IngestionJobProduct,
            IngestionJobProduct.product_id == Product.id,
        ).filter(IngestionJobProduct.ingestion_job_id == ingestion_job_id)
    if status:
        query = query.filter(Product.status == status)
    if category:
        query = query.filter(Product.category == category)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.title.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.brand.ilike(search_term),
            )
        )

    return query


def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    ingestion_job_id: Optional[int] = None,
    sort_by: ProductSortField = ProductSortField.UPDATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> tuple[list[Product], int]:
    """Retrieve products with optional filtering, sorting, and pagination.

    Args:
        db: Database session.
        skip: Number of records to skip.
        limit: Maximum records to return.
        status: Filter by product status.
        search: Search term for title/SKU/brand matching.
        category: Filter by category.
        ingestion_job_id: Limit results to products from one uploaded file.
        sort_by: Column to sort by.
        sort_order: Sort direction.

    Returns:
        Tuple of matching Product records and total count before pagination.
    """
    query = _build_products_query(
        db,
        status=status,
        search=search,
        category=category,
        ingestion_job_id=ingestion_job_id,
    )
    total = query.count()

    sort_column = SORT_COLUMNS.get(sort_by, Product.updated_at)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    products = query.offset(skip).limit(limit).all()
    return products, total


def list_products_for_export(
    db: Session,
    status: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    ingestion_job_id: Optional[int] = None,
) -> list[Product]:
    """Return every product matching the current Products-page filters."""
    query = _build_products_query(
        db,
        status=status,
        search=search,
        category=category,
        ingestion_job_id=ingestion_job_id,
    )
    return query.order_by(Product.sku.asc()).all()


def get_product_by_id(db: Session, product_id: int) -> Optional[Product]:
    """Retrieve a single product by its ID.

    Args:
        db: Database session.
        product_id: Product primary key.

    Returns:
        Product record or None if not found.
    """
    return db.query(Product).filter(Product.id == product_id).first()


def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """Retrieve a product by its SKU.

    Args:
        db: Database session.
        sku: Unique product SKU.

    Returns:
        Product record or None if not found.
    """
    return db.query(Product).filter(Product.sku == sku).first()


def create_product(db: Session, product_data: ProductCreate) -> Product:
    """Create a new product in the database.

    Args:
        db: Database session.
        product_data: Product creation data.

    Returns:
        Newly created Product record.
    """
    product = Product(
        sku=product_data.sku,
        title=product_data.title,
        description=product_data.description,
        category=product_data.category,
        brand=product_data.brand,
        price=product_data.price,
        currency=product_data.currency,
        attributes=product_data.attributes,
        status=ProductStatus.DRAFT,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    logger.info(f"Created product: SKU={product.sku}, Title='{product.title[:50]}'")
    return product


def update_product(db: Session, product_id: int, updates: ProductUpdate) -> Optional[Product]:
    """Update an existing product.

    Args:
        db: Database session.
        product_id: Product primary key.
        updates: Fields to update.

    Returns:
        Updated Product record or None if not found.
    """
    product = get_product_by_id(db, product_id)
    if not product:
        return None

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    logger.info(f"Updated product {product_id}: fields={list(update_data.keys())}")
    return product


def delete_product(db: Session, product_id: int) -> bool:
    """Delete a product by its ID.

    Args:
        db: Database session.
        product_id: Product primary key.

    Returns:
        True if deleted, False if not found.
    """
    product = get_product_by_id(db, product_id)
    if not product:
        return False

    db.delete(product)
    db.commit()
    logger.info(f"Deleted product {product_id}: SKU={product.sku}")
    return True


def get_categories(db: Session) -> list[str]:
    """Get all distinct product categories.

    Args:
        db: Database session.

    Returns:
        List of unique category names.
    """
    results = db.query(Product.category).distinct().filter(Product.category.isnot(None)).all()
    return sorted([r[0] for r in results])


def get_dashboard_stats(db: Session) -> DashboardStats:
    """Calculate dashboard overview statistics.

    Args:
        db: Database session.

    Returns:
        DashboardStats with aggregated metrics.
    """
    total = db.query(func.count(Product.id)).scalar() or 0
    active = db.query(func.count(Product.id)).filter(Product.status == ProductStatus.ACTIVE).scalar() or 0
    flagged = db.query(func.count(Product.id)).filter(Product.status == ProductStatus.FLAGGED).scalar() or 0

    open_issues = db.query(func.count(DataIssue.id)).filter(DataIssue.resolved == False).scalar() or 0

    no_desc = db.query(func.count(Product.id)).filter(
        Product.description.is_(None) | (Product.description == ""),
        Product.generated_description.is_(None) | (Product.generated_description == ""),
    ).scalar() or 0

    from app.services.competitor_service import get_enabled_competitor_sources

    recent_alerts = db.query(func.count(CompetitorAlert.id)).filter(
        CompetitorAlert.acknowledged == False,
        CompetitorAlert.source.in_(get_enabled_competitor_sources()),
    ).scalar() or 0

    last_job = db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).first()

    return DashboardStats(
        total_products=total,
        active_products=active,
        flagged_products=flagged,
        open_issues=open_issues,
        products_without_description=no_desc,
        recent_alerts=recent_alerts,
        last_ingestion=last_job.started_at if last_job else None,
    )
