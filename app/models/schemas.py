"""
CatalogIQ — Data Models and Schemas

SQLAlchemy ORM models for database tables and Pydantic schemas
for API request/response validation.
"""

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Enum, Boolean, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base


# =============================================================================
# Enums
# =============================================================================


class ProductStatus(str, enum.Enum):
    """Status of a product in the catalog."""
    DRAFT = "draft"
    ACTIVE = "active"
    FLAGGED = "flagged"
    ARCHIVED = "archived"


class IssueType(str, enum.Enum):
    """Type of data quality issue detected."""
    MISSING_DESCRIPTION = "missing_description"
    THIN_CONTENT = "thin_content"
    ATTRIBUTE_CONTRADICTION = "attribute_contradiction"
    MISSING_ATTRIBUTES = "missing_attributes"
    DUPLICATE_TITLE = "duplicate_title"
    PRICE_ANOMALY = "price_anomaly"


class IssueSeverity(str, enum.Enum):
    """Severity level of a data quality issue."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CompetitorSource(str, enum.Enum):
    """Supported competitor marketplace sources."""
    AMAZON = "amazon"
    WALMART = "walmart"
    FLIPKART = "flipkart"


class AlertType(str, enum.Enum):
    """Type of competitor monitoring alert."""
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    OUT_OF_STOCK = "out_of_stock"
    BACK_IN_STOCK = "back_in_stock"
    UNDERCUT = "undercut"


# =============================================================================
# SQLAlchemy ORM Models
# =============================================================================


class Product(Base):
    """Product catalog entry with normalized attributes."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    generated_description = Column(Text, nullable=True)
    category = Column(String(200), nullable=True)
    brand = Column(String(200), nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    status = Column(Enum(ProductStatus), default=ProductStatus.DRAFT)

    # Normalized attributes stored as JSON
    attributes = Column(JSON, default=dict)
    raw_data = Column(JSON, default=dict)

    # SEO metadata
    seo_title = Column(String(200), nullable=True)
    seo_keywords = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    issues = relationship("DataIssue", back_populates="product", cascade="all, delete-orphan")
    competitor_prices = relationship("CompetitorPrice", back_populates="product", cascade="all, delete-orphan")
    competitor_alerts = relationship("CompetitorAlert", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Product(sku='{self.sku}', title='{self.title[:50]}')>"


class DataIssue(Base):
    """Data quality issue flagged during ingestion or analysis."""
    __tablename__ = "data_issues"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    issue_type = Column(Enum(IssueType), nullable=False)
    severity = Column(Enum(IssueSeverity), default=IssueSeverity.MEDIUM)
    description = Column(Text, nullable=False)
    field_name = Column(String(100), nullable=True)
    expected_value = Column(Text, nullable=True)
    actual_value = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="issues")

    def __repr__(self) -> str:
        return f"<DataIssue(product_id={self.product_id}, type='{self.issue_type}')>"


class CompetitorPrice(Base):
    """Competitor price and stock snapshot for a product."""
    __tablename__ = "competitor_prices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    source = Column(Enum(CompetitorSource), nullable=False)
    competitor_title = Column(String(500), nullable=True)
    competitor_url = Column(Text, nullable=True)
    competitor_price = Column(Float, nullable=True)
    competitor_currency = Column(String(10), default="USD")
    in_stock = Column(Boolean, default=True)
    scraped_at = Column(DateTime, server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="competitor_prices")

    def __repr__(self) -> str:
        return f"<CompetitorPrice(product_id={self.product_id}, source='{self.source}', price={self.competitor_price})>"


class CompetitorAlert(Base):
    """Alert generated from competitor monitoring analysis."""
    __tablename__ = "competitor_alerts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    alert_type = Column(Enum(AlertType), nullable=False)
    source = Column(Enum(CompetitorSource), nullable=False)
    message = Column(Text, nullable=False)
    our_price = Column(Float, nullable=True)
    competitor_price = Column(Float, nullable=True)
    price_difference = Column(Float, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="competitor_alerts")

    def __repr__(self) -> str:
        return f"<CompetitorAlert(product_id={self.product_id}, type='{self.alert_type}')>"


class IngestionJob(Base):
    """Record of a CSV ingestion job run."""
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    new_products = Column(Integer, default=0)
    updated_products = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, filename='{self.filename}', status='{self.status}')>"


# =============================================================================
# Pydantic Schemas (API Request/Response)
# =============================================================================


class ProductBase(BaseModel):
    """Base schema for product data."""
    sku: str = Field(..., description="Unique product SKU identifier")
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Original product description")
    category: Optional[str] = Field(None, description="Product category")
    brand: Optional[str] = Field(None, description="Product brand name")
    price: Optional[float] = Field(None, description="Product price")
    currency: str = Field(default="USD", description="Price currency code")


class ProductCreate(ProductBase):
    """Schema for creating a new product."""
    attributes: dict = Field(default_factory=dict, description="Normalized product attributes")


class ProductUpdate(BaseModel):
    """Schema for updating an existing product."""
    title: Optional[str] = None
    description: Optional[str] = None
    generated_description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    status: Optional[ProductStatus] = None
    attributes: Optional[dict] = None
    seo_title: Optional[str] = None
    seo_keywords: Optional[str] = None


class ProductResponse(ProductBase):
    """Schema for product API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    generated_description: Optional[str] = None
    status: ProductStatus
    attributes: dict = {}
    seo_title: Optional[str] = None
    seo_keywords: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    issue_count: Optional[int] = 0


class DataIssueResponse(BaseModel):
    """Schema for data issue API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    resolved: bool
    created_at: datetime


class CompetitorPriceResponse(BaseModel):
    """Schema for competitor price API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    source: CompetitorSource
    competitor_title: Optional[str] = None
    competitor_url: Optional[str] = None
    competitor_price: Optional[float] = None
    in_stock: bool
    scraped_at: datetime


class CompetitorAlertResponse(BaseModel):
    """Schema for competitor alert API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    alert_type: AlertType
    source: CompetitorSource
    message: str
    our_price: Optional[float] = None
    competitor_price: Optional[float] = None
    price_difference: Optional[float] = None
    acknowledged: bool
    created_at: datetime


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    total_rows: int
    processed_rows: int
    new_products: int
    updated_products: int
    issues_found: int
    status: str
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class ContentGenerationRequest(BaseModel):
    """Schema for requesting content generation."""
    product_ids: list[int] = Field(..., description="List of product IDs to generate content for")
    tone: str = Field(default="professional", description="Tone of the generated content")
    include_seo: bool = Field(default=True, description="Whether to generate SEO metadata")


class ContentGenerationResponse(BaseModel):
    """Schema for content generation results."""
    product_id: int
    generated_description: str
    seo_title: Optional[str] = None
    seo_keywords: Optional[str] = None
    success: bool
    error: Optional[str] = None


class CompetitorScrapeRequest(BaseModel):
    """Schema for triggering competitor scraping."""
    product_ids: Optional[list[int]] = Field(None, description="Specific products to scrape (None = all)")
    sources: list[CompetitorSource] = Field(
        default=[CompetitorSource.AMAZON, CompetitorSource.WALMART, CompetitorSource.FLIPKART],
        description="Marketplace sources to scrape"
    )


class DashboardStats(BaseModel):
    """Schema for dashboard overview statistics."""
    total_products: int = 0
    active_products: int = 0
    flagged_products: int = 0
    open_issues: int = 0
    products_without_description: int = 0
    recent_alerts: int = 0
    last_ingestion: Optional[datetime] = None
    last_scrape: Optional[datetime] = None
