"""
Contract: Products API Router
Module: src/shelf_monitor/api/routers/products.py
Purpose: REST API endpoints for product catalog management

This contract defines the FastAPI router for product CRUD operations:
- Create new products
- List products with pagination
- Get product by SKU
- Update product information
- Delete products

Related:
- Data Model: Product table, Category table
- Database: CRUD operations in crud.py
- API Task: T095-T100 (Product endpoints)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from decimal import Decimal


# ============================================
# Pydantic Schemas (Request/Response)
# ============================================

class ProductBase(BaseModel):
    """Base schema with common product fields."""
    sku: str = Field(..., min_length=1, max_length=50, description="Stock Keeping Unit")
    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    category_id: int = Field(..., gt=0, description="Category identifier")
    expected_price: Decimal = Field(..., ge=0, description="Expected retail price")
    barcode: Optional[str] = Field(None, max_length=50, description="Product barcode (EAN/UPC)")
    image_url: Optional[str] = Field(None, description="Product image URL")


class ProductCreate(ProductBase):
    """Schema for creating new product."""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating product (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category_id: Optional[int] = Field(None, gt=0)
    expected_price: Optional[Decimal] = Field(None, ge=0)
    barcode: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = None


class ProductResponse(ProductBase):
    """Schema for product response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy


class ProductListResponse(BaseModel):
    """Schema for paginated product list."""
    total: int
    page: int
    page_size: int
    products: List[ProductResponse]


# ============================================
# Router Definition
# ============================================

router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
    responses={404: {"description": "Product not found"}}
)


# ============================================
# Endpoint Contracts
# ============================================

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new product",
    description="Add a new product to the catalog"
)
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
) -> ProductResponse:
    """
    Create new product in catalog.
    
    Request Body:
        {
            "sku": "COKE-500ML",
            "name": "Coca-Cola 500ml",
            "category_id": 1,
            "expected_price": 1.99,
            "barcode": "5449000000996",
            "image_url": "https://example.com/products/coke-500ml.jpg"
        }
    
    Response: 201 Created
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
    
    Errors:
        - 400: Invalid input (duplicate SKU, invalid category_id, negative price)
        - 422: Validation error
    
    Implementation:
        1. Validate category_id exists
        2. Check for duplicate SKU
        3. Call crud.create_product(db, product)
        4. Return created product with 201 status
    
    Example:
        >>> import httpx
        >>> response = httpx.post(
        ...     "http://localhost:8000/api/v1/products/",
        ...     json={"sku": "COKE-500ML", "name": "Coca-Cola 500ml", "category_id": 1, "expected_price": 1.99}
        ... )
        >>> print(response.status_code)
        201
        >>> print(response.json()["id"])
        1
    """
    pass


@router.get(
    "/",
    response_model=ProductListResponse,
    summary="List all products",
    description="Get paginated list of products with optional filtering"
)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name or SKU"),
    db: Session = Depends(get_db)
) -> ProductListResponse:
    """
    List products with pagination and filtering.
    
    Query Parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 50, max: 100)
        - category_id: Filter by category
        - search: Search in name or SKU (case-insensitive)
    
    Response: 200 OK
        {
            "total": 150,
            "page": 1,
            "page_size": 50,
            "products": [
                {
                    "id": 1,
                    "sku": "COKE-500ML",
                    "name": "Coca-Cola 500ml",
                    ...
                },
                ...
            ]
        }
    
    Implementation:
        1. Build query with filters (category_id, search)
        2. Count total matching products
        3. Apply pagination: offset = (page - 1) * page_size
        4. Return ProductListResponse with metadata
    
    Example:
        >>> response = httpx.get(
        ...     "http://localhost:8000/api/v1/products/",
        ...     params={"page": 1, "page_size": 10, "search": "coke"}
        ... )
        >>> data = response.json()
        >>> print(f"Found {data['total']} products")
        Found 5 products
    """
    pass


@router.get(
    "/{sku}",
    response_model=ProductResponse,
    summary="Get product by SKU",
    description="Retrieve product details by Stock Keeping Unit"
)
async def get_product_by_sku(
    sku: str,
    db: Session = Depends(get_db)
) -> ProductResponse:
    """
    Get product by SKU.
    
    Path Parameters:
        - sku: Stock Keeping Unit (e.g., "COKE-500ML")
    
    Response: 200 OK
        {
            "id": 1,
            "sku": "COKE-500ML",
            "name": "Coca-Cola 500ml",
            ...
        }
    
    Errors:
        - 404: Product not found with given SKU
    
    Implementation:
        1. Call crud.get_product_by_sku(db, sku)
        2. If not found, raise HTTPException(404)
        3. Return product
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/products/COKE-500ML")
        >>> print(response.status_code)
        200
        >>> print(response.json()["name"])
        Coca-Cola 500ml
    """
    pass


@router.put(
    "/{sku}",
    response_model=ProductResponse,
    summary="Update product",
    description="Update product information by SKU"
)
async def update_product(
    sku: str,
    product_update: ProductUpdate,
    db: Session = Depends(get_db)
) -> ProductResponse:
    """
    Update product by SKU.
    
    Path Parameters:
        - sku: Stock Keeping Unit
    
    Request Body (all fields optional):
        {
            "name": "Coca-Cola 500ml (New Formula)",
            "expected_price": 2.29
        }
    
    Response: 200 OK
        {
            "id": 1,
            "sku": "COKE-500ML",
            "name": "Coca-Cola 500ml (New Formula)",
            "expected_price": 2.29,
            ...
        }
    
    Errors:
        - 404: Product not found
        - 400: Invalid update data
    
    Implementation:
        1. Get existing product by SKU
        2. Update only provided fields
        3. Call crud.update_product(db, product_id, update_data)
        4. Return updated product
    
    Example:
        >>> response = httpx.put(
        ...     "http://localhost:8000/api/v1/products/COKE-500ML",
        ...     json={"expected_price": 2.29}
        ... )
        >>> print(response.json()["expected_price"])
        2.29
    """
    pass


@router.delete(
    "/{sku}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product",
    description="Delete product from catalog by SKU"
)
async def delete_product(
    sku: str,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete product by SKU.
    
    Path Parameters:
        - sku: Stock Keeping Unit
    
    Response: 204 No Content (empty body on success)
    
    Errors:
        - 404: Product not found
        - 409: Cannot delete (foreign key constraint - has detections)
    
    Implementation:
        1. Get product by SKU
        2. Check for dependent records (detections, price_history)
        3. If dependencies exist, raise HTTPException(409, "Cannot delete product with existing detections")
        4. Call crud.delete_product(db, product_id)
        5. Return 204 No Content
    
    Example:
        >>> response = httpx.delete("http://localhost:8000/api/v1/products/COKE-500ML")
        >>> print(response.status_code)
        204
    """
    pass


# ============================================
# Additional Endpoints
# ============================================

@router.get(
    "/{sku}/detections",
    summary="Get product detections",
    description="Retrieve all detections for a specific product"
)
async def get_product_detections(
    sku: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get detection history for product.
    
    Returns list of detections with analysis job info.
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/products/COKE-500ML/detections")
        >>> print(len(response.json()["detections"]))
        247
    """
    pass


@router.get(
    "/{sku}/price-history",
    summary="Get price history",
    description="Retrieve price verification history for a product"
)
async def get_product_price_history(
    sku: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get price verification history.
    
    Returns time-series data of detected vs expected prices.
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/products/COKE-500ML/price-history?days=7")
        >>> history = response.json()["history"]
        >>> print(f"Found {len(history)} price records")
    """
    pass


# ============================================
# Dependency Functions
# ============================================

def get_db():
    """
    Dependency to get database session.
    
    Yields SQLAlchemy session, automatically closes after request.
    
    Usage:
        @router.get("/products")
        async def list_products(db: Session = Depends(get_db)):
            products = db.query(Product).all()
            return products
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T095: Create products router
    - T096: Implement POST /products (create)
    - T097: Implement GET /products (list)
    - T098: Implement GET /products/{sku} (get by SKU)
    - T099: Implement PUT /products/{sku} (update)
    - T100: Implement DELETE /products/{sku} (delete)
    - T101: Create integration tests

API Endpoints:
    - POST   /api/v1/products/              - Create product
    - GET    /api/v1/products/              - List products (paginated)
    - GET    /api/v1/products/{sku}         - Get product by SKU
    - PUT    /api/v1/products/{sku}         - Update product
    - DELETE /api/v1/products/{sku}         - Delete product
    - GET    /api/v1/products/{sku}/detections - Get detection history
    - GET    /api/v1/products/{sku}/price-history - Get price history

Dependencies:
    - FastAPI (routing, validation)
    - Pydantic (schema validation)
    - SQLAlchemy (database ORM)
    - CRUD module (database operations)

Response Formats:
    - Success: JSON with appropriate status codes (200, 201, 204)
    - Error: {"detail": "Error message"} with status codes (400, 404, 422, 500)

Next Steps:
    1. Implement this contract in src/shelf_monitor/api/routers/products.py
    2. Implement CRUD operations in crud.py (T096-T100)
    3. Write integration tests in tests/integration/test_api_products.py (T101)
    4. Test via Swagger UI at http://localhost:8000/docs
"""
