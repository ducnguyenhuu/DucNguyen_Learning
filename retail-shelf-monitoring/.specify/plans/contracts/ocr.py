"""
Contract: OCR (Optical Character Recognition) Module
Module: src/shelf_monitor/core/ocr.py
Purpose: Price tag extraction and parsing for Challenge 4 (Price Verification)

This contract defines the interface for the PriceOCR class, which:
1. Extracts text from price tags using Azure Document Intelligence
2. Parses prices in multiple formats ($X.XX, €X,XX, £X.XX)
3. Validates OCR confidence scores
4. Tracks price history for mismatch detection

Related:
- Challenge 4: Price Verification (T080-T094)
- Data Model: PriceHistory table
- Azure Service: azure_document_intelligence.py wrapper
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
import re


# ============================================
# Data Classes
# ============================================

@dataclass
class PriceTag:
    """
    Represents a price tag detected and parsed from shelf image.
    
    Attributes:
        text: Raw OCR text from price tag
        price: Parsed price as Decimal
        currency: Currency symbol ($, €, £)
        confidence: OCR confidence score (0.0-1.0)
        bbox: Bounding box as (x, y, width, height)
        product_id: Linked product ID (if matched)
    
    Validation:
        - confidence >= 0.8 (minimum threshold for acceptance)
        - price > 0 (no negative or zero prices)
        - bbox coordinates valid
    
    Example:
        >>> tag = PriceTag(
        ...     text="$1.99",
        ...     price=Decimal("1.99"),
        ...     currency="$",
        ...     confidence=0.94,
        ...     bbox=(200, 120, 60, 40),
        ...     product_id=1
        ... )
    """
    text: str
    price: Decimal
    currency: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    product_id: Optional[int] = None


@dataclass
class PriceVerificationResult:
    """
    Result of price verification comparing detected vs expected price.
    
    Attributes:
        product_id: Product identifier
        sku: Stock Keeping Unit
        detected_price: Price from OCR
        expected_price: Price from catalog
        difference: detected_price - expected_price
        mismatch: True if |difference| > tolerance
        confidence: OCR confidence score
        bbox: Price tag bounding box
    
    Usage:
        Used to identify pricing errors and compliance issues.
    
    Example:
        >>> result = PriceVerificationResult(
        ...     product_id=1,
        ...     sku="COKE-500ML",
        ...     detected_price=Decimal("2.49"),
        ...     expected_price=Decimal("1.99"),
        ...     difference=Decimal("0.50"),
        ...     mismatch=True,
        ...     confidence=0.92,
        ...     bbox=(200, 120, 60, 40)
        ... )
    """
    product_id: int
    sku: str
    detected_price: Decimal
    expected_price: Decimal
    difference: Decimal
    mismatch: bool
    confidence: float
    bbox: Tuple[int, int, int, int]


# ============================================
# Price OCR Interface
# ============================================

class PriceOCR:
    """
    Extracts and parses price information from shelf images using OCR.
    
    This class uses Azure Document Intelligence (formerly Form Recognizer)
    for text extraction and custom regex patterns for price parsing.
    
    Responsibilities:
        1. Initialize Azure Document Intelligence client
        2. Extract text from price tag regions
        3. Parse prices in multiple formats and currencies
        4. Validate OCR confidence scores
        5. Link prices to products via spatial analysis
        6. Handle API rate limits with retry logic
    
    Supported Price Formats:
        - US: $1.99, $12.50, $0.99
        - EU: €1,99, €12,50, 1.99€
        - UK: £1.99, £12.50
        - General: 1.99, 12.50 (assumes currency from context)
    
    OCR Confidence Threshold:
        - Minimum: 0.8 (80%) for price acceptance
        - Reject prices with confidence < 0.8
    
    Configuration:
        - DOCUMENT_INTELLIGENCE_KEY: Azure API key
        - DOCUMENT_INTELLIGENCE_ENDPOINT: Azure endpoint URL
        - CONFIDENCE_THRESHOLD: Minimum OCR confidence (default: 0.8)
        - PRICE_TOLERANCE: Mismatch tolerance in currency units (default: 0.10)
    
    Usage:
        >>> ocr = PriceOCR()
        >>> tags = ocr.extract_prices("shelf_image.jpg")
        >>> for tag in tags:
        ...     print(f"{tag.currency}{tag.price} (confidence: {tag.confidence:.2f})")
    """
    
    def __init__(
        self,
        key: Optional[str] = None,
        endpoint: Optional[str] = None,
        confidence_threshold: float = 0.8,
        price_tolerance: float = 0.10
    ) -> None:
        """
        Initialize PriceOCR with Azure Document Intelligence credentials.
        
        Args:
            key: Azure Document Intelligence key (from .env if None)
            endpoint: Azure endpoint URL (from .env if None)
            confidence_threshold: Minimum OCR confidence to accept
            price_tolerance: Price mismatch tolerance (dollars/euros/pounds)
        
        Raises:
            ValueError: If credentials missing or threshold invalid
            ConnectionError: If cannot connect to Azure
        
        Implementation Notes:
            - Load credentials from environment if not provided
            - Initialize DocumentAnalysisClient from Azure SDK
            - Validate endpoint URL format
            - Test connection with simple API call
        """
        pass
    
    def extract_prices(
        self,
        image_path: str,
        regions: Optional[List[Tuple[int, int, int, int]]] = None
    ) -> List[PriceTag]:
        """
        Extract price tags from shelf image using OCR.
        
        Process:
            1. Send image to Azure Document Intelligence Read API
            2. Wait for OCR processing (async operation)
            3. Parse OCR results to find text regions
            4. Filter regions containing price patterns
            5. Parse each price text to extract value and currency
            6. Return PriceTag objects with confidence scores
        
        Args:
            image_path: Path to shelf image file
            regions: Optional list of bounding boxes to search (for focused OCR)
        
        Returns:
            List of PriceTag objects with parsed prices
        
        Raises:
            FileNotFoundError: If image_path does not exist
            AzureError: If API call fails after retries
            ValueError: If no prices found in image
        
        Implementation Notes:
            - Use DocumentAnalysisClient.begin_analyze_document()
            - Model: "prebuilt-read" (general text extraction)
            - Retry logic: 3 attempts with exponential backoff
            - Rate limiting: Handle 429 errors with delay
            - Filter confidence: Only return tags with confidence >= threshold
        
        Example:
            >>> ocr = PriceOCR()
            >>> tags = ocr.extract_prices("shelf.jpg")
            >>> print(f"Found {len(tags)} price tags")
            Found 12 price tags
            >>> high_confidence = [t for t in tags if t.confidence > 0.9]
            >>> print(f"{len(high_confidence)} with confidence > 90%")
            8 with confidence > 90%
        """
        pass
    
    def parse_price(
        self,
        text: str,
        default_currency: str = "$"
    ) -> Optional[Tuple[Decimal, str]]:
        """
        Parse price from OCR text using regex patterns.
        
        Regex Patterns:
            - US: \\$\\s*(\\d+\\.\\d{2})
            - EU: €\\s*(\\d+,\\d{2}) or (\\d+\\.\\d{2})\\s*€
            - UK: £\\s*(\\d+\\.\\d{2})
            - Generic: (\\d+[\\.,]\\d{2})
        
        Args:
            text: OCR text containing price
            default_currency: Currency if not found in text
        
        Returns:
            Tuple of (price, currency) or None if no price found
        
        Implementation Notes:
            - Try each regex pattern in order
            - Convert comma to period for EU format (1,99 → 1.99)
            - Parse to Decimal for precision (avoid float errors)
            - Handle edge cases: $1.9 (invalid), $1.99$ (duplicate symbols)
        
        Example:
            >>> ocr = PriceOCR()
            >>> price, currency = ocr.parse_price("$1.99")
            >>> print(f"{currency}{price}")
            $1.99
            >>> price, currency = ocr.parse_price("€12,50")
            >>> print(f"{currency}{price}")
            €12.50
            >>> price, currency = ocr.parse_price("1.99", default_currency="$")
            >>> print(f"{currency}{price}")
            $1.99
        """
        pass
    
    def verify_prices(
        self,
        image_path: str,
        product_catalog: Dict[int, Decimal],
        detections: List[Dict]
    ) -> List[PriceVerificationResult]:
        """
        Complete price verification workflow: extract, link, compare.
        
        Process:
            1. Extract price tags from image (OCR)
            2. Link each tag to nearest product detection (spatial matching)
            3. Compare detected_price with expected_price from catalog
            4. Flag mismatches where |difference| > tolerance
            5. Return verification results for database storage
        
        Args:
            image_path: Path to shelf image
            product_catalog: Dict mapping product_id to expected_price
            detections: List of product detections with bbox and product_id
        
        Returns:
            List of PriceVerificationResult objects
        
        Raises:
            ValueError: If catalog or detections missing
        
        Implementation Notes:
            - Link tags to products: find nearest detection bbox (Euclidean distance)
            - Calculate difference: detected - expected
            - Flag mismatch: |difference| > self.price_tolerance
            - Handle unmatched tags (no nearby product)
        
        Example:
            >>> ocr = PriceOCR()
            >>> catalog = {1: Decimal("1.99"), 2: Decimal("2.49")}
            >>> detections = [
            ...     {"product_id": 1, "bbox": (120, 50, 80, 150)},
            ...     {"product_id": 2, "bbox": (300, 50, 70, 130)}
            ... ]
            >>> results = ocr.verify_prices("shelf.jpg", catalog, detections)
            >>> mismatches = [r for r in results if r.mismatch]
            >>> for r in mismatches:
            ...     print(f"{r.sku}: detected ${r.detected_price}, expected ${r.expected_price}")
        """
        pass
    
    def link_price_to_product(
        self,
        price_bbox: Tuple[int, int, int, int],
        detections: List[Dict],
        max_distance: int = 100
    ) -> Optional[int]:
        """
        Link price tag to nearest product detection using spatial proximity.
        
        Matching Strategy:
            - Calculate Euclidean distance between price bbox center and
              each product bbox center
            - Return product_id of nearest detection
            - If distance > max_distance, return None (no match)
        
        Args:
            price_bbox: Price tag bounding box (x, y, width, height)
            detections: List of product detections with bbox and product_id
            max_distance: Maximum distance for valid match (pixels)
        
        Returns:
            product_id of nearest detection, or None if no match
        
        Implementation Notes:
            - Calculate bbox center: (x + width/2, y + height/2)
            - Distance: sqrt((x1-x2)² + (y1-y2)²)
            - Prefer detections directly above or below price tag (y-axis proximity)
        
        Example:
            >>> price_bbox = (200, 180, 60, 40)  # Below product
            >>> detections = [
            ...     {"product_id": 1, "bbox": (120, 50, 80, 150)},
            ...     {"product_id": 2, "bbox": (190, 50, 80, 150)}  # Closer
            ... ]
            >>> product_id = ocr.link_price_to_product(price_bbox, detections)
            >>> print(product_id)
            2
        """
        pass
    
    def get_price_history(
        self,
        product_id: int,
        days: int,
        db_session: object
    ) -> List[Tuple[datetime, Decimal, Decimal]]:
        """
        Retrieve price history from database for trend analysis.
        
        Args:
            product_id: Product to query
            days: Number of days to look back
            db_session: SQLAlchemy database session
        
        Returns:
            List of (timestamp, detected_price, expected_price) tuples
        
        SQL Query:
            SELECT created_at, detected_price, expected_price
            FROM price_history
            WHERE product_id = ? AND created_at >= DATE('now', '-? days')
            ORDER BY created_at ASC
        
        Example:
            >>> history = ocr.get_price_history(product_id=1, days=7, db_session=session)
            >>> for timestamp, detected, expected in history:
            ...     if detected != expected:
            ...         print(f"{timestamp}: ${detected} vs ${expected}")
        """
        pass


# ============================================
# Helper Functions
# ============================================

def calculate_bbox_distance(
    bbox1: Tuple[int, int, int, int],
    bbox2: Tuple[int, int, int, int]
) -> float:
    """
    Calculate Euclidean distance between centers of two bounding boxes.
    
    Args:
        bbox1: First bounding box (x, y, width, height)
        bbox2: Second bounding box (x, y, width, height)
    
    Returns:
        Distance in pixels
    
    Formula:
        center1 = (x1 + w1/2, y1 + h1/2)
        center2 = (x2 + w2/2, y2 + h2/2)
        distance = sqrt((center1_x - center2_x)² + (center1_y - center2_y)²)
    
    Example:
        >>> bbox1 = (10, 10, 100, 100)  # Center: (60, 60)
        >>> bbox2 = (150, 10, 100, 100)  # Center: (200, 60)
        >>> dist = calculate_bbox_distance(bbox1, bbox2)
        >>> print(f"Distance: {dist:.1f}px")
        Distance: 140.0px
    """
    pass


def compile_price_regex_patterns() -> List[Tuple[str, str]]:
    """
    Compile regex patterns for price extraction in multiple formats.
    
    Returns:
        List of (pattern, currency) tuples
    
    Patterns:
        1. US Dollar: \\$\\s*(\\d+\\.\\d{2}) → "$"
        2. Euro (prefix): €\\s*(\\d+[\\.,]\\d{2}) → "€"
        3. Euro (suffix): (\\d+[\\.,]\\d{2})\\s*€ → "€"
        4. British Pound: £\\s*(\\d+\\.\\d{2}) → "£"
        5. Generic: (\\d+[\\.,]\\d{2}) → default currency
    
    Example:
        >>> patterns = compile_price_regex_patterns()
        >>> text = "$1.99"
        >>> for pattern, currency in patterns:
        ...     match = re.search(pattern, text)
        ...     if match:
        ...         print(f"Found: {currency}{match.group(1)}")
        Found: $1.99
    """
    pass


# ============================================
# Testing Interface
# ============================================

def test_ocr_with_sample_images() -> None:
    """
    Integration test for PriceOCR with sample price tag images.
    
    Test Cases:
        1. Extract prices from multi-product shelf image
        2. Parse various currency formats ($, €, £)
        3. Verify prices against catalog
        4. Calculate parsing accuracy
    
    Test Data:
        - Sample images: tests/fixtures/price_tags_*.jpg
        - Ground truth: tests/fixtures/price_tags_ground_truth.json
    
    Assertions:
        - OCR accuracy > 95%
        - Price extraction > 90%
        - All confidences >= 0.8
        - Currency detection 100% accurate
    
    Usage:
        >>> test_ocr_with_sample_images()
        ✓ Extracted 24 price tags from 3 images
        ✓ OCR accuracy: 96.7%
        ✓ Price parsing accuracy: 92.5%
        ✓ Currency detection: 100%
        ✓ All assertions passed
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T080: Create PriceTag dataclass
    - T081: Create PriceOCR class
    - T082: Implement __init__() with Azure client
    - T083: Implement extract_prices() with retry logic
    - T084: Implement parse_price() with regex patterns
    - T089: Create unit tests

Dependencies:
    - Azure Document Intelligence SDK (azure-ai-formrecognizer)
    - Python re module (regex)
    - Decimal module (price precision)
    - Database (price_history table)

Performance Targets:
    - OCR accuracy > 95%
    - Price extraction > 90%
    - Latency < 500ms per image
    - API cost < $0.01 per 100 images (F0 tier: 500/month free)

Supported Currencies:
    - US Dollar ($)
    - Euro (€)
    - British Pound (£)
    - Extensible to other currencies via regex

Next Steps:
    1. Implement this contract in src/shelf_monitor/core/ocr.py
    2. Create Azure Document Intelligence wrapper (T085)
    3. Write unit tests in tests/unit/test_ocr.py (T089)
    4. Create Jupyter notebook for demos (T091)
"""
