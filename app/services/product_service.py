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
    Product, DataIssue, CompetitorAlert, IngestionJob,
    ProductStatus, ProductCreate, ProductUpdate, ProductResponse, DashboardStats,
)

logger = logging.getLogger("catalogiq.product_service")


def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
) -> list[Product]:
    """Retrieve products with optional filtering and pagination.

    Args:
        db: Database session.
        skip: Number of records to skip.
        limit: Maximum records to return.
        status: Filter by product status.
        search: Search term for title/SKU matching.
        category: Filter by category.

    Returns:
        List of matching Product records.
    """
    query = db.query(Product)

    if status:
        query = query.filter(Product.status == status)
    if category:
        query = query.filter(Product.category == category)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.title.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.brand.ilike(search_term),
            )
        )

    query = query.order_by(Product.updated_at.desc())
    return query.offset(skip).limit(limit).all()


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

    recent_alerts = db.query(func.count(CompetitorAlert.id)).filter(
        CompetitorAlert.acknowledged == False
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
