"""
CatalogIQ — Data Models and Schemas

SQLAlchemy ORM models for database tables and Pydantic schemas
for API request/response validation.
"""

import enum
import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Enum, Boolean, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base


# =============================================================================
# Enums
# =============================================================================


class AiAnalysisStatus(str, enum.Enum):
    """Per-product AI analysis progress during ingestion."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


class ProductStatus(str, enum.Enum):
    """Status of a product in the catalog."""
    DRAFT = "draft"
    ACTIVE = "active"
    FLAGGED = "flagged"
    ARCHIVED = "archived"


class ProductSortField(str, enum.Enum):
    """Allowed sort columns for product listing."""
    SKU = "sku"
    TITLE = "title"
    CATEGORY = "category"
    BRAND = "brand"
    PRICE = "price"
    STATUS = "status"
    UPDATED_AT = "updated_at"


class SortOrder(str, enum.Enum):
    """Sort direction for list endpoints."""
    ASC = "asc"
    DESC = "desc"


class IngestionJobSortField(str, enum.Enum):
    """Allowed sort columns for ingestion job listing."""
    ID = "id"
    FILENAME = "filename"
    GROUP_NAME = "group_name"
    STATUS = "status"
    PROCESSED_ROWS = "processed_rows"
    NEW_PRODUCTS = "new_products"
    UPDATED_PRODUCTS = "updated_products"
    ISSUES_FOUND = "issues_found"
    STARTED_AT = "started_at"


class DataIssueSortField(str, enum.Enum):
    """Allowed sort columns for data issue listing."""
    CREATED_AT = "created_at"
    SEVERITY = "severity"
    ISSUE_TYPE = "issue_type"
    PRODUCT_ID = "product_id"


class IssueType(str, enum.Enum):
    """Type of data quality issue detected."""
    MISSING_DESCRIPTION = "missing_description"
    THIN_CONTENT = "thin_content"
    ATTRIBUTE_CONTRADICTION = "attribute_contradiction"
    MISSING_ATTRIBUTES = "missing_attributes"
    DUPLICATE_TITLE = "duplicate_title"
    PRICE_ANOMALY = "price_anomaly"
    ATTRIBUTE_NOT_IN_COPY = "attribute_not_in_copy"
    AI_INFERRED = "ai_inferred"


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
    EBAY = "ebay"
    TARGET = "target"
    FLIPKART = "flipkart"


class AlertType(str, enum.Enum):
    """Type of competitor monitoring alert."""
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    OUT_OF_STOCK = "out_of_stock"
    BACK_IN_STOCK = "back_in_stock"
    UNDERCUT = "undercut"


class ContentTone(str, enum.Enum):
    """Supported writing tones for SEO content generation."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    LUXURY = "luxury"
    TECHNICAL = "technical"


class ReviewStatus(str, enum.Enum):
    """Human review state for a suggested field rewrite or quality issue."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class ReviewAction(str, enum.Enum):
    """User action on a pending suggestion or quality issue."""
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class SuggestionSource(str, enum.Enum):
    """How a quality issue or rewrite suggestion was produced."""
    RULE = "rule"
    AI = "ai"


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

    last_ingestion_job_id = Column(Integer, ForeignKey("ingestion_jobs.id"), nullable=True, index=True)
    ai_analysis_status = Column(String(20), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    issues = relationship("DataIssue", back_populates="product", cascade="all, delete-orphan")
    ingestion_links = relationship(
        "IngestionJobProduct",
        back_populates="product",
        cascade="all, delete-orphan",
    )
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
    suggested_value = Column(Text, nullable=True)
    suggestion_source = Column(String(20), nullable=True)
    review_status = Column(String(20), default=ReviewStatus.PENDING.value, nullable=False)
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
    is_simulated = Column(Boolean, default=False, nullable=False)
    match_score = Column(Float, nullable=True)
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


class User(Base):
    """Application user account for authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User(email='{self.email}')>"


class IngestionJob(Base):
    """Record of a CSV ingestion job run."""
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    group_name = Column(String(255), nullable=True)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    new_products = Column(Integer, default=0)
    updated_products = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
    skipped_rows = Column(Integer, default=0)
    skip_summary = Column(Text, nullable=True)
    ai_analyzed_rows = Column(Integer, default=0)
    ai_error_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    product_links = relationship(
        "IngestionJobProduct",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class IngestionJobProduct(Base):
    """Product that was created or updated by a specific CSV upload."""
    __tablename__ = "ingestion_job_products"

    ingestion_job_id = Column(Integer, ForeignKey("ingestion_jobs.id"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)

    job = relationship("IngestionJob", back_populates="product_links")
    product = relationship("Product", back_populates="ingestion_links")

    def __repr__(self) -> str:
        return (
            f"<IngestionJobProduct(job_id={self.ingestion_job_id}, "
            f"product_id={self.product_id})>"
        )


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
    last_ingestion_job_id: Optional[int] = None
    ai_analysis_status: Optional[str] = None


class ProductListResponse(BaseModel):
    """Paginated product list API response."""
    items: list[ProductResponse]
    total: int
    skip: int
    limit: int


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
    suggested_value: Optional[str] = None
    suggestion_source: Optional[SuggestionSource] = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    resolved: bool
    created_at: datetime

    @field_validator("review_status", mode="before")
    @classmethod
    def default_review_status(cls, value: object) -> object:
        """Treat missing review_status as pending for rows created before the column existed."""
        return value or ReviewStatus.PENDING

    @field_validator("suggestion_source", mode="before")
    @classmethod
    def empty_source_to_none(cls, value: object) -> object:
        """Normalize blank suggestion_source values to None."""
        if value == "":
            return None
        return value


class DataIssueListResponse(BaseModel):
    """Paginated data issue list API response."""
    items: list[DataIssueResponse]
    total: int
    skip: int
    limit: int


class ReviewRequest(BaseModel):
    """Accept, edit, or reject a pending suggestion or quality issue."""
    action: ReviewAction = Field(..., description="accept, edit, or reject")
    edited_value: Optional[str] = Field(
        None,
        description="Required when action is edit; applied instead of suggested_value",
    )


class BulkAcceptIssuesRequest(BaseModel):
    """Accept pending quality issues for given issue or product IDs."""
    issue_ids: Optional[list[int]] = Field(None, description="Specific issue IDs to accept")
    product_ids: Optional[list[int]] = Field(
        None,
        description="Accept all pending applicable issues for these products",
    )


class IngestionJobUpdate(BaseModel):
    """Schema for renaming an ingestion group."""
    group_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Merchant-facing group name",
    )

    @field_validator("group_name")
    @classmethod
    def _strip_group_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Group name cannot be empty.")
        return cleaned


class ReviewResultResponse(BaseModel):
    """Result of reviewing one suggestion or quality issue."""
    id: int
    product_id: int
    review_status: ReviewStatus
    product_status: Optional[ProductStatus] = None
    message: str


class BulkAcceptIssuesResponse(BaseModel):
    """Summary of bulk-accepting quality issues."""
    accepted: int
    skipped: int
    product_ids: list[int]


class CompetitorPriceResponse(BaseModel):
    """Schema for competitor price API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    source: CompetitorSource
    competitor_title: Optional[str] = None
    competitor_url: Optional[str] = None
    competitor_price: Optional[float] = None
    competitor_currency: str = "USD"
    in_stock: bool
    is_simulated: bool = False
    match_score: Optional[float] = None
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


class IngestionPreviewResponse(BaseModel):
    """Parsed CSV preview used to confirm column mapping before ingest."""
    filename: str
    encoding: str
    delimiter: str
    total_rows: int
    columns: list[str]
    suggested_mapping: dict[str, str]
    sample_rows: list[dict[str, Optional[str]]]
    warnings: list[str] = []
    standard_fields: list[str]
    required_fields: list[str] = ["sku"]


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    group_name: Optional[str] = None
    total_rows: int
    processed_rows: int
    new_products: int
    updated_products: int
    issues_found: int
    skipped_rows: int = 0
    skip_summary: Optional[dict[str, object]] = None
    ai_analyzed_rows: int = 0
    ai_error_count: int = 0
    status: str
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("skip_summary", mode="before")
    @classmethod
    def _parse_skip_summary(cls, value: object) -> Optional[dict[str, object]]:
        """Accept ORM JSON text or an already-parsed mapping."""
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None


class IngestionJobListResponse(BaseModel):
    """Paginated ingestion job list API response."""
    items: list[IngestionJobResponse]
    total: int
    skip: int
    limit: int


class ContentGenerationRequest(BaseModel):
    """Schema for requesting content generation."""
    product_ids: list[int] = Field(..., description="List of product IDs to generate content for")
    tone: ContentTone = Field(
        default=ContentTone.PROFESSIONAL,
        description="Tone of the generated content",
    )
    include_seo: bool = Field(default=True, description="Whether to generate SEO metadata")


class ContentGenerationResponse(BaseModel):
    """Schema for content generation results."""
    product_id: int
    sku: Optional[str] = None
    title: Optional[str] = None
    generated_description: str
    seo_title: Optional[str] = None
    seo_keywords: Optional[str] = None
    word_count: Optional[int] = None
    warnings: list[str] = Field(default_factory=list)
    success: bool
    error: Optional[str] = None


def default_competitor_scrape_sources() -> list[CompetitorSource]:
    """Resolve default scrape sources from SCRAPE_REGION env."""
    from app.services.competitor_service import get_default_scrape_sources

    return get_default_scrape_sources()


class CompetitorMarketplaceResponse(BaseModel):
    """Schema for a configured competitor marketplace."""
    id: CompetitorSource
    platform: str
    region: str
    label: str
    currency: str
    base_url: str
    search_url_template: str


class CompetitorConfigResponse(BaseModel):
    """Schema for competitor monitoring configuration exposed to the UI."""
    region: str
    sources: list[CompetitorMarketplaceResponse]
    usd_inr_exchange_rate: float = Field(
        default=83.0,
        description="USD to INR rate used for cross-currency price comparison",
    )


class CompetitorScrapeRequest(BaseModel):
    """Schema for triggering competitor scraping."""
    product_ids: Optional[list[int]] = Field(None, description="Specific products to scrape (None = all)")
    sources: list[CompetitorSource] = Field(
        default_factory=default_competitor_scrape_sources,
        description="Marketplace sources to scrape",
    )


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Plain-text password")
    full_name: Optional[str] = Field(None, description="Display name")
    is_superuser: bool = Field(default=False, description="Whether user has admin access")


class UserResponse(BaseModel):
    """Schema for user API responses (no password)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Schema for JWT login responses."""
    access_token: str
    token_type: str = "bearer"


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
