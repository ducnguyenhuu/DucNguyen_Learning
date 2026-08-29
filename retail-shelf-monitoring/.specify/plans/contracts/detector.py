"""
Contract: Product Detector Module
Module: src/shelf_monitor/core/detector.py
Purpose: Object detection and gap detection for Challenge 1 (Out-of-Stock Detection)

This contract defines the interface for the ProductDetector class, which:
1. Detects products in shelf images using Azure Custom Vision
2. Identifies empty shelf spaces (gaps) using geometric analysis
3. Returns structured detection results for database persistence

Related:
- Challenge 1: Out-of-Stock Detection (T025-T045)
- Data Model: Detection and GapRegion dataclasses
- Azure Service: azure_custom_vision.py wrapper
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional


# ============================================
# Data Classes
# ============================================

@dataclass
class Detection:
    """
    Represents a single product detection from object detection model.
    
    Attributes:
        bbox: Bounding box as (x, y, width, height) in pixels
        confidence: Model confidence score (0.0-1.0)
        label: Detection label (SKU or "product")
        product_id: Product ID if recognized, None otherwise
    
    Validation:
        - confidence must be in range [0.0, 1.0]
        - bbox width and height must be positive
    
    Example:
        >>> detection = Detection(
        ...     bbox=(120, 50, 80, 150),
        ...     confidence=0.92,
        ...     label="COKE-500ML",
        ...     product_id=1
        ... )
    """
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    label: str
    product_id: Optional[int] = None


@dataclass
class GapRegion:
    """
    Represents an empty shelf space detected by gap detection algorithm.
    
    Attributes:
        bbox: Gap bounding box as (x, y, width, height) in pixels
        gap_width: Gap width in pixels
        is_significant: True if gap_width exceeds threshold (100px)
    
    Validation:
        - gap_width must be positive
        - bbox width and height must be positive
    
    Example:
        >>> gap = GapRegion(
        ...     bbox=(450, 60, 120, 180),
        ...     gap_width=120,
        ...     is_significant=True
        ... )
    """
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    gap_width: int
    is_significant: bool


# ============================================
# Product Detector Interface
# ============================================

class ProductDetector:
    """
    Detects products and gaps in retail shelf images.
    
    This class combines Azure Custom Vision for product detection with
    geometric analysis for gap detection (out-of-stock areas).
    
    Responsibilities:
        1. Initialize Azure Custom Vision prediction client
        2. Detect products with bounding boxes and confidence scores
        3. Analyze product positions to identify empty shelf spaces
        4. Handle API errors with retry logic (exponential backoff)
    
    Configuration:
        - CUSTOM_VISION_PREDICTION_KEY: Azure prediction API key
        - CUSTOM_VISION_PREDICTION_ENDPOINT: Azure endpoint URL
        - CUSTOM_VISION_PREDICTION_RESOURCE_ID: Azure resource ID
        - GAP_THRESHOLD: Minimum gap width in pixels (default: 100)
    
    Usage:
        >>> detector = ProductDetector()
        >>> detections = detector.detect_products("shelf_image.jpg")
        >>> gaps = detector.detect_gaps(detections, image_width=1920)
    """
    
    def __init__(
        self,
        prediction_key: Optional[str] = None,
        prediction_endpoint: Optional[str] = None,
        prediction_resource_id: Optional[str] = None,
        gap_threshold: int = 100
    ) -> None:
        """
        Initialize ProductDetector with Azure Custom Vision credentials.
        
        Args:
            prediction_key: Azure Custom Vision prediction key (from .env if None)
            prediction_endpoint: Azure endpoint URL (from .env if None)
            prediction_resource_id: Azure resource ID (from .env if None)
            gap_threshold: Minimum gap width to flag as significant (pixels)
        
        Raises:
            ValueError: If credentials are missing or invalid
            ConnectionError: If cannot connect to Azure Custom Vision
        
        Implementation Notes:
            - Load credentials from environment variables if not provided
            - Initialize CustomVisionPredictionClient from Azure SDK
            - Validate endpoint URL format
            - Test connection with a simple API call
        """
        pass
    
    def detect_products(
        self,
        image_path: str,
        confidence_threshold: float = 0.5
    ) -> List[Detection]:
        """
        Detect products in shelf image using Azure Custom Vision.
        
        Args:
            image_path: Path to shelf image file
            confidence_threshold: Minimum confidence to include detection (0.0-1.0)
        
        Returns:
            List of Detection objects with bounding boxes and confidence scores
        
        Raises:
            FileNotFoundError: If image_path does not exist
            ValueError: If confidence_threshold not in [0.0, 1.0]
            AzureError: If API call fails after retries
        
        Implementation Notes:
            - Read image file as binary
            - Call CustomVisionPredictionClient.detect_image()
            - Filter detections by confidence_threshold
            - Convert Azure format to Detection dataclass
            - Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
            - Log API response time for monitoring
        
        Example:
            >>> detector = ProductDetector()
            >>> detections = detector.detect_products("shelf.jpg", confidence_threshold=0.7)
            >>> print(f"Found {len(detections)} products")
            Found 24 products
        """
        pass
    
    def detect_gaps(
        self,
        detections: List[Detection],
        image_width: int,
        image_height: int = 800
    ) -> List[GapRegion]:
        """
        Identify empty shelf spaces (gaps) between detected products.
        
        Algorithm:
            1. Sort detections by x-coordinate (left to right)
            2. For each adjacent pair of detections:
               - Calculate horizontal gap: gap_width = next_x - (current_x + current_width)
               - If gap_width > threshold (100px), create GapRegion
            3. Check left edge: gap from 0 to first detection
            4. Check right edge: gap from last detection to image_width
        
        Args:
            detections: List of Detection objects from detect_products()
            image_width: Image width in pixels (for edge detection)
            image_height: Image height in pixels (for gap bbox height)
        
        Returns:
            List of GapRegion objects representing empty shelf spaces
        
        Raises:
            ValueError: If detections list is empty or image dimensions invalid
        
        Implementation Notes:
            - Sort by detection.bbox[0] (x-coordinate)
            - Use vectorized operations if performance becomes an issue
            - Gap bbox height = average detection height (or fixed value)
            - Flag is_significant if gap_width > self.gap_threshold
        
        Example:
            >>> detections = [
            ...     Detection(bbox=(10, 50, 80, 150), confidence=0.9, label="SKU1"),
            ...     Detection(bbox=(300, 50, 80, 150), confidence=0.85, label="SKU2")
            ... ]
            >>> gaps = detector.detect_gaps(detections, image_width=1920)
            >>> significant_gaps = [g for g in gaps if g.is_significant]
            >>> print(f"Found {len(significant_gaps)} significant gaps")
            Found 1 significant gaps
        """
        pass
    
    def process_image(
        self,
        image_path: str,
        confidence_threshold: float = 0.5
    ) -> Tuple[List[Detection], List[GapRegion]]:
        """
        Complete pipeline: detect products and identify gaps in one call.
        
        This is a convenience method that combines detect_products() and
        detect_gaps() for end-to-end processing.
        
        Args:
            image_path: Path to shelf image file
            confidence_threshold: Minimum confidence for product detection
        
        Returns:
            Tuple of (detections, gaps) lists
        
        Raises:
            Same exceptions as detect_products() and detect_gaps()
        
        Example:
            >>> detector = ProductDetector()
            >>> detections, gaps = detector.process_image("shelf.jpg")
            >>> print(f"Products: {len(detections)}, Gaps: {len(gaps)}")
            Products: 24, Gaps: 3
        """
        pass


# ============================================
# Helper Functions
# ============================================

def calculate_iou(bbox1: Tuple[int, int, int, int], 
                  bbox2: Tuple[int, int, int, int]) -> float:
    """
    Calculate Intersection over Union (IoU) for two bounding boxes.
    
    IoU is used for:
    - Non-Maximum Suppression (NMS) to remove duplicate detections
    - Evaluating detection accuracy against ground truth
    
    Args:
        bbox1: First bounding box as (x, y, width, height)
        bbox2: Second bounding box as (x, y, width, height)
    
    Returns:
        IoU score in range [0.0, 1.0]
    
    Formula:
        IoU = Area(Intersection) / Area(Union)
    
    Example:
        >>> bbox1 = (10, 10, 100, 100)
        >>> bbox2 = (50, 50, 100, 100)
        >>> iou = calculate_iou(bbox1, bbox2)
        >>> print(f"IoU: {iou:.2f}")
        IoU: 0.14
    """
    pass


def non_max_suppression(
    detections: List[Detection],
    iou_threshold: float = 0.5
) -> List[Detection]:
    """
    Remove duplicate detections using Non-Maximum Suppression.
    
    NMS keeps the detection with highest confidence when multiple
    detections overlap significantly (IoU > threshold).
    
    Args:
        detections: List of Detection objects
        iou_threshold: IoU threshold for considering detections as duplicates
    
    Returns:
        Filtered list of Detection objects (no duplicates)
    
    Algorithm:
        1. Sort detections by confidence (descending)
        2. For each detection:
           - If IoU with any kept detection > threshold, discard
           - Otherwise, keep detection
    
    Example:
        >>> detections = [...]  # Multiple overlapping detections
        >>> filtered = non_max_suppression(detections, iou_threshold=0.5)
        >>> print(f"Reduced from {len(detections)} to {len(filtered)}")
        Reduced from 45 to 28
    """
    pass


# ============================================
# Testing Interface
# ============================================

def test_detector_with_sample_image() -> None:
    """
    Integration test for ProductDetector with sample shelf image.
    
    This function is called by T040 (unit tests) to verify:
    - Azure Custom Vision API connection
    - Product detection accuracy
    - Gap detection algorithm correctness
    
    Test Data:
        - Sample image: tests/fixtures/shelf_sample.jpg
        - Expected: 20-30 product detections
        - Expected: 2-5 gap regions
    
    Assertions:
        - All detections have confidence >= 0.5
        - All gap widths > 100px
        - No duplicate detections (after NMS)
    
    Usage:
        >>> test_detector_with_sample_image()
        ✓ Detected 24 products (avg confidence: 0.87)
        ✓ Found 3 significant gaps
        ✓ All assertions passed
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T025: Create Detection dataclass
    - T026: Create GapRegion dataclass
    - T027: Implement ProductDetector.__init__()
    - T033: Implement ProductDetector.detect_products()
    - T034: Implement ProductDetector.detect_gaps()
    - T040: Create unit tests

Dependencies:
    - Azure Custom Vision SDK (azure-cognitiveservices-vision-customvision)
    - Python 3.10+ (for type hints)
    - PIL/OpenCV (for image loading)

Next Steps:
    1. Implement this contract in src/shelf_monitor/core/detector.py
    2. Create Azure Custom Vision service wrapper (T035)
    3. Write unit tests in tests/unit/test_detector.py (T040)
    4. Integrate with API endpoint (T036)
"""
