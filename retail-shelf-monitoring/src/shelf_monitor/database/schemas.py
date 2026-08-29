"""
Pydantic Schemas for API Request/Response Validation.

This module defines Pydantic models for validating API requests and responses.
Each schema corresponds to a database table and provides:
- Input validation for API requests (Create/Update schemas)
- Output serialization for API responses (Response schemas)
- Type safety with comprehensive field validation

Pydantic Features Used:
- Field(): Validation constraints (ge, le, min_length, max_length, regex)
- ConfigDict: ORM mode for SQLAlchemy compatibility
- computed_field: For derived fields
- field_validator: Custom validation logic

Usage:
    # Create a new product
    product_data = ProductCreate(
        sku="COKE-500ML",
        name="Coca-Cola 500ml",
        category_id=1,
        expected_price=1.99
    )
    
    # Validate API response
    product_response = ProductResponse.model_validate(db_product)
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Category Schemas
# ============================================================================


class CategoryBase(BaseModel):
    """Base schema for Category with shared fields."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Category name (e.g., 'Beverages', 'Snacks')",
        examples=["Beverages", "Snacks", "Dairy"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional category description",
        examples=["Soft drinks, juices, water"],
    )


class CategoryCreate(CategoryBase):
    """Schema for creating a new category.
    
    Example:
        {
            "name": "Beverages",
            "description": "Soft drinks, juices, water"
        }
    """

    pass


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category (all fields optional).
    
    Example:
        {
            "description": "Updated description"
        }
    """

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Updated category name"
    )
    description: Optional[str] = Field(None, description="Updated description")


class CategoryResponse(CategoryBase):
    """Schema for category API responses.
    
    Example:
        {
            "id": 1,
            "name": "Beverages",
            "description": "Soft drinks, juices, water",
            "created_at": "2024-01-15T10:30:00"
        }
    """

    id: int = Field(..., description="Unique category identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Product Schemas
# ============================================================================


class ProductBase(BaseModel):
    """Base schema for Product with shared fields."""

    sku: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Stock Keeping Unit (unique product code)",
        examples=["COKE-500ML", "PEPSI-330ML"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Product name",
        examples=["Coca-Cola 500ml", "Pepsi 330ml Can"],
    )
    category_id: int = Field(
        ..., gt=0, description="Category reference (foreign key to categories.id)"
    )
    expected_price: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Expected retail price (non-negative)",
        examples=[1.99, 2.49, 0.99],
    )
    barcode: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Product barcode (EAN/UPC)",
        examples=["5449000000996"],
    )
    image_url: Optional[str] = Field(
        None,
        description="Product reference image URL",
        examples=["https://example.com/products/coke-500ml.jpg"],
    )

    @field_validator("expected_price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Ensure price has at most 2 decimal places."""
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v.quantize(Decimal("0.01"))


class ProductCreate(ProductBase):
    """Schema for creating a new product.
    
    Example:
        {
            "sku": "COKE-500ML",
            "name": "Coca-Cola 500ml",
            "category_id": 1,
            "expected_price": 1.99,
            "barcode": "5449000000996",
            "image_url": "https://example.com/products/coke-500ml.jpg"
        }
    """

    pass


class ProductUpdate(BaseModel):
    """Schema for updating an existing product (all fields optional).
    
    Example:
        {
            "expected_price": 2.49,
            "image_url": "https://example.com/products/coke-500ml-new.jpg"
        }
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category_id: Optional[int] = Field(None, gt=0)
    expected_price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    barcode: Optional[str] = Field(None, min_length=1, max_length=50)
    image_url: Optional[str] = None

    @field_validator("expected_price")
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure price has at most 2 decimal places."""
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v.quantize(Decimal("0.01")) if v is not None else None


class ProductResponse(ProductBase):
    """Schema for product API responses.
    
    Example:
        {
            "id": 1,
            "sku": "COKE-500ML",
            "name": "Coca-Cola 500ml",
            "category_id": 1,
            "expected_price": 1.99,
            "barcode": "5449000000996",
            "image_url": "https://example.com/products/coke-500ml.jpg",
            "created_at": "2024-01-15T10:35:00",
            "updated_at": "2024-01-15T10:35:00"
        }
    """

    id: int = Field(..., description="Unique product identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# AnalysisJob Schemas
# ============================================================================


class AnalysisJobBase(BaseModel):
    """Base schema for AnalysisJob with shared fields."""

    image_path: str = Field(
        ...,
        min_length=1,
        description="Path to uploaded shelf image",
        examples=["data/uploads/shelf_20240115_103045.jpg"],
    )
    challenge_type: str = Field(
        ...,
        description="Challenge type",
        examples=["OUT_OF_STOCK", "PRODUCT_RECOGNITION", "STOCK_ESTIMATION", "PRICE_VERIFICATION"],
    )

    @field_validator("challenge_type")
    @classmethod
    def validate_challenge_type(cls, v: str) -> str:
        """Ensure challenge_type is valid."""
        allowed = {"OUT_OF_STOCK", "PRODUCT_RECOGNITION", "STOCK_ESTIMATION", "PRICE_VERIFICATION"}
        if v not in allowed:
            raise ValueError(
                f"Invalid challenge_type '{v}'. Must be one of: {', '.join(allowed)}"
            )
        return v


class AnalysisJobCreate(AnalysisJobBase):
    """Schema for creating a new analysis job.
    
    Example:
        {
            "image_path": "data/uploads/shelf_20240115_103045.jpg",
            "challenge_type": "OUT_OF_STOCK"
        }
    """

    pass


class AnalysisJobUpdate(BaseModel):
    """Schema for updating an existing analysis job (internal use).
    
    Example:
        {
            "status": "COMPLETED",
            "result_summary": {"total_products": 45, "gaps_detected": 3},
            "completed_at": "2024-01-15T10:31:12"
        }
    """

    status: Optional[str] = Field(None, description="Job status")
    result_summary: Optional[dict[str, Any]] = Field(None, description="JSON summary of results")
    error_message: Optional[str] = Field(None, description="Error details if status = FAILED")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Ensure status is valid."""
        if v is not None:
            allowed = {"PENDING", "PROCESSING", "COMPLETED", "FAILED"}
            if v not in allowed:
                raise ValueError(f"Invalid status '{v}'. Must be one of: {', '.join(allowed)}")
        return v


class AnalysisJobResponse(AnalysisJobBase):
    """Schema for analysis job API responses.
    
    Example:
        {
            "id": 1,
            "image_path": "data/uploads/shelf_20240115_103045.jpg",
            "challenge_type": "OUT_OF_STOCK",
            "status": "COMPLETED",
            "result_summary": {
                "total_products": 45,
                "gaps_detected": 3,
                "gap_regions": [
                    {"x": 120, "y": 50, "width": 150, "height": 200}
                ]
            },
            "error_message": null,
            "created_at": "2024-01-15T10:30:45",
            "completed_at": "2024-01-15T10:31:12"
        }
    """

    id: int = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    result_summary: Optional[dict[str, Any]] = Field(None, description="JSON summary of results")
    error_message: Optional[str] = Field(None, description="Error details if status = FAILED")
    created_at: datetime = Field(..., description="Job submission timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Detection Schemas
# ============================================================================


class DetectionBase(BaseModel):
    """Base schema for Detection with shared fields."""

    analysis_job_id: int = Field(
        ..., gt=0, description="Analysis job reference (foreign key to analysis_jobs.id)"
    )
    product_id: Optional[int] = Field(
        None, gt=0, description="Product reference (NULL for unrecognized)"
    )
    bbox_x: int = Field(..., ge=0, description="Bounding box top-left X coordinate (pixels)")
    bbox_y: int = Field(..., ge=0, description="Bounding box top-left Y coordinate (pixels)")
    bbox_width: int = Field(..., gt=0, description="Bounding box width (pixels)")
    bbox_height: int = Field(..., gt=0, description="Bounding box height (pixels)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence score (0.0-1.0)"
    )
    label: Optional[str] = Field(
        None, max_length=100, description="Detection label from model"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is in valid range [0, 1]."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v


class DetectionCreate(DetectionBase):
    """Schema for creating a new detection.
    
    Example:
        {
            "analysis_job_id": 1,
            "product_id": 1,
            "bbox_x": 120,
            "bbox_y": 50,
            "bbox_width": 80,
            "bbox_height": 150,
            "confidence": 0.92,
            "label": "COKE-500ML"
        }
    """

    pass


class DetectionResponse(DetectionBase):
    """Schema for detection API responses.
    
    Example:
        {
            "id": 1,
            "analysis_job_id": 1,
            "product_id": 1,
            "bbox_x": 120,
            "bbox_y": 50,
            "bbox_width": 80,
            "bbox_height": 150,
            "confidence": 0.92,
            "label": "COKE-500ML",
            "created_at": "2024-01-15T10:31:05"
        }
    """

    id: int = Field(..., description="Unique detection identifier")
    created_at: datetime = Field(..., description="Detection timestamp")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# PriceHistory Schemas
# ============================================================================


class PriceHistoryBase(BaseModel):
    """Base schema for PriceHistory with shared fields."""

    analysis_job_id: int = Field(
        ..., gt=0, description="Analysis job reference (foreign key to analysis_jobs.id)"
    )
    product_id: int = Field(
        ..., gt=0, description="Product reference (foreign key to products.id)"
    )
    detected_price: Decimal = Field(
        ..., ge=0, decimal_places=2, description="Price extracted via OCR"
    )
    expected_price: Decimal = Field(
        ..., ge=0, decimal_places=2, description="Expected price from product catalog"
    )
    ocr_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="OCR confidence score (0.0-1.0)"
    )
    bbox_x: int = Field(..., ge=0, description="Price tag bounding box X")
    bbox_y: int = Field(..., ge=0, description="Price tag bounding box Y")
    bbox_width: int = Field(..., gt=0, description="Price tag bounding box width")
    bbox_height: int = Field(..., gt=0, description="Price tag bounding box height")

    @field_validator("detected_price", "expected_price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Ensure price has at most 2 decimal places."""
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v.quantize(Decimal("0.01"))

    @field_validator("ocr_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure OCR confidence is in valid range [0, 1]."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"OCR confidence must be between 0.0 and 1.0, got {v}")
        return v


class PriceHistoryCreate(PriceHistoryBase):
    """Schema for creating a new price history record.
    
    Example:
        {
            "analysis_job_id": 5,
            "product_id": 1,
            "detected_price": 2.49,
            "expected_price": 1.99,
            "ocr_confidence": 0.88,
            "bbox_x": 200,
            "bbox_y": 120,
            "bbox_width": 60,
            "bbox_height": 40
        }
    """

    pass


class PriceHistoryResponse(PriceHistoryBase):
    """Schema for price history API responses.
    
    Note: price_difference is auto-computed by database (GENERATED column).
    
    Example:
        {
            "id": 1,
            "analysis_job_id": 5,
            "product_id": 1,
            "detected_price": 2.49,
            "expected_price": 1.99,
            "price_difference": 0.50,
            "ocr_confidence": 0.88,
            "bbox_x": 200,
            "bbox_y": 120,
            "bbox_width": 60,
            "bbox_height": 40,
            "created_at": "2024-01-15T14:20:30"
        }
    """

    id: int = Field(..., description="Unique price record identifier")
    price_difference: Decimal = Field(
        ...,
        decimal_places=2,
        description="Computed difference (detected_price - expected_price)",
    )
    created_at: datetime = Field(..., description="Price detection timestamp")

    model_config = ConfigDict(from_attributes=True)
