"""
Product Detector Module
Module: src/shelf_monitor/core/detector.py
Purpose: Object detection and gap detection for Challenge 1 (Out-of-Stock Detection)

This module provides:
1. Detection dataclass - represents a single product detection
2. GapRegion dataclass - represents an empty shelf space (gap)
3. ProductDetector class - detects products and gaps in shelf images using YOLO

Related Tasks:
- T025: Create Detection dataclass
- T026: Create GapRegion dataclass
- T027: Implement ProductDetector.__init__()
- T031: Implement ProductDetector.detect_products()
- T032: Implement ProductDetector.detect_gaps()
- T033: Simplified - YOLO integrated directly (no separate wrapper)
"""

from dataclasses import dataclass
from typing import List, Optional


# ============================================
# Data Classes
# ============================================

@dataclass
class Detection:
    """
    Represents a single product detection from object detection model.
    
    Attributes:
        bbox: Bounding box as (x, y, width, height) in pixels
            - x: Left coordinate (horizontal position from left edge)
            - y: Top coordinate (vertical position from top edge)
            - width: Box width in pixels
            - height: Box height in pixels
        confidence: Model confidence score (0.0-1.0)
            - Higher values indicate greater certainty
            - Typically filter detections with confidence < 0.5
        label: Detection label (SKU code like "COKE-500ML" or generic "object")
        product_id: Product ID if recognized and matched to database, None otherwise
    
    Validation:
        - confidence must be in range [0.0, 1.0]
        - bbox width and height must be positive (> 0)
        - bbox x and y should be non-negative (>= 0)
    
    Example:
        >>> detection = Detection(
        ...     bbox=(120, 50, 80, 150),
        ...     confidence=0.92,
        ...     label="COKE-500ML",
        ...     product_id=1
        ... )
        >>> print(f"Product detected at x={detection.bbox[0]}, width={detection.bbox[2]}px")
        Product detected at x=120, width=80px
    
    Notes:
        - YOLO models return boxes in (x1, y1, x2, y2) format - convert to (x, y, w, h)
        - Azure Custom Vision returns boxes in (left, top, width, height) format - already compatible
        - Confidence threshold of 0.5 is common default, tune based on false positive/negative rate
    """
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    label: str
    product_id: Optional[int] = None
    
    def __post_init__(self):
        """
        Validate detection data after initialization.
        
        Raises:
            ValueError: If confidence is not in [0.0, 1.0] or bbox dimensions are invalid
        """
        # Validate confidence score
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}. "
                f"Check model output format and ensure proper normalization."
            )
        
        # Validate bbox dimensions
        x, y, width, height = self.bbox
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Bounding box dimensions must be positive. "
                f"Got width={width}, height={height}. "
                f"Full bbox: {self.bbox}"
            )
        
        if x < 0 or y < 0:
            raise ValueError(
                f"Bounding box coordinates must be non-negative. "
                f"Got x={x}, y={y}. "
                f"Full bbox: {self.bbox}"
            )


@dataclass
class GapRegion:
    """
    Represents an empty shelf space detected by gap detection algorithm.
    
    A gap region indicates a potential out-of-stock situation where products
    should be present but are missing. The gap detection algorithm analyzes
    horizontal spacing between detected products to identify these empty areas.
    
    Attributes:
        bbox: Gap bounding box as (x, y, width, height) in pixels
            - x: Left coordinate of gap (where empty space starts)
            - y: Top coordinate of gap (typically aligned with shelf row)
            - width: Gap width in pixels (horizontal empty space)
            - height: Gap height in pixels (typically matches product height)
        gap_width: Gap width in pixels (same as bbox[2], kept for convenience)
            - Used for severity classification
            - Typical thresholds: <100px (normal), 100-150px (medium), >150px (high)
        is_significant: Boolean flag indicating if gap exceeds threshold
            - True if gap_width > MIN_GAP_WIDTH (default 100px)
            - Significant gaps are flagged for restocking alerts
    
    Validation:
        - gap_width must be positive (> 0)
        - bbox width and height must be positive (> 0)
        - bbox x and y should be non-negative (>= 0)
        - gap_width should match bbox[2] for consistency
    
    Example:
        >>> gap = GapRegion(
        ...     bbox=(450, 60, 120, 180),
        ...     gap_width=120,
        ...     is_significant=True  # 120px > 100px threshold
        ... )
        >>> if gap.is_significant:
        ...     print(f"Alert: {gap.gap_width}px gap detected - restock needed!")
        Alert: 120px gap detected - restock needed!
    
    Usage in Gap Detection Algorithm:
        1. Sort product detections by x-coordinate (left to right)
        2. Calculate horizontal spacing between adjacent products
        3. If spacing > MIN_GAP_WIDTH, create GapRegion
        4. Set is_significant=True for gaps exceeding threshold
        5. Return list of GapRegion objects for database persistence
    
    Notes:
        - Gap width threshold (100px) is configurable via settings
        - Small gaps (<100px) might be intentional product spacing
        - Large gaps (>150px) typically indicate entire product row is missing
        - Gap height usually matches the height of surrounding products
    """
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    gap_width: int
    is_significant: bool
    
    def __post_init__(self):
        """
        Validate gap region data after initialization.
        
        Raises:
            ValueError: If gap_width is not positive or bbox dimensions are invalid
        """
        # Validate gap width
        if self.gap_width <= 0:
            raise ValueError(
                f"Gap width must be positive, got {self.gap_width}. "
                f"Gap width represents horizontal empty space and cannot be zero or negative."
            )
        
        # Validate bbox dimensions
        x, y, width, height = self.bbox
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Bounding box dimensions must be positive. "
                f"Got width={width}, height={height}. "
                f"Full bbox: {self.bbox}"
            )
        
        if x < 0 or y < 0:
            raise ValueError(
                f"Bounding box coordinates must be non-negative. "
                f"Got x={x}, y={y}. "
                f"Full bbox: {self.bbox}"
            )
        
        # Validate consistency between gap_width and bbox width
        if self.gap_width != width:
            raise ValueError(
                f"Gap width ({self.gap_width}) must match bbox width ({width}). "
                f"These should be the same value representing horizontal empty space."
            )


# ============================================
# Product Detector Class
# ============================================

class ProductDetector:
    """
    Detects products and gaps in retail shelf images using YOLO.
    
    This class combines YOLOv8 object detection with geometric gap analysis
    to identify products and empty shelf spaces (out-of-stock areas).
    
    The detector supports two main operations:
    1. Product Detection: Uses trained YOLO model to find products in shelf images
    2. Gap Detection: Analyzes spacing between products to identify empty areas
    
    Architecture:
        - YOLO Model: Detects products with bounding boxes and confidence scores
        - Gap Algorithm: Sorts detections horizontally and measures spacing
        - Configuration: Uses settings from config/settings.py for thresholds
    
    Typical Workflow:
        >>> detector = ProductDetector()
        >>> detections = detector.detect_products("shelf.jpg")
        >>> gaps = detector.detect_gaps(detections, image_width=1920)
        >>> print(f"Found {len(detections)} products and {len(gaps)} gaps")
    
    Performance:
        - Detection latency: ~300-400ms on M1/M2 Mac, ~150-200ms on NVIDIA GPU
        - Gap analysis: ~40-50ms (pure Python, no ML)
        - Total end-to-end: <500ms for typical shelf image (1920x1080)
    
    Configuration (from settings.py):
        - yolo_model_path: Path to trained YOLO checkpoint
        - confidence_threshold: Minimum confidence for detections (default: 0.5)
        - min_gap_width: Minimum gap width to flag (default: 100px)
    
    Attributes:
        model: Loaded YOLO model instance
        model_path: Path to YOLO checkpoint file
        confidence_threshold: Minimum confidence for including detections
        min_gap_width: Minimum gap width in pixels to consider significant
    
    Raises:
        FileNotFoundError: If YOLO model file doesn't exist
        ValueError: If configuration parameters are invalid
        RuntimeError: If YOLO model fails to load
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        min_gap_width: Optional[int] = None
    ) -> None:
        """
        Initialize ProductDetector with YOLO model and configuration.
        
        Loads the trained YOLO model from disk and sets detection parameters.
        If parameters are not provided, loads from application settings.
        
        Args:
            model_path: Path to YOLO model checkpoint (.pt file)
                - If None, uses settings.yolo_model_path (default: "models/yolo_sku110k_best.pt")
                - Can be relative (to project root) or absolute path
                - Must be a YOLOv8 model trained on shelf images
            
            confidence_threshold: Minimum confidence score for detections (0.0-1.0)
                - If None, uses settings.confidence_threshold (default: 0.5)
                - Lower values: More detections but more false positives
                - Higher values: Fewer detections but higher precision
                - Typical range: 0.4-0.7
            
            min_gap_width: Minimum gap width in pixels to flag as significant
                - If None, uses settings.min_gap_width (default: 100px)
                - Depends on camera distance and product size
                - Typical product width in 1920x1080 images: 50-100px
                - Gaps < threshold are considered normal spacing
        
        Raises:
            FileNotFoundError: If model_path doesn't exist
                - Check that YOLO model has been trained (T028-T030)
                - Verify path is correct in .env or function argument
            
            ValueError: If confidence_threshold not in [0.0, 1.0] or min_gap_width <= 0
                - Confidence must be a valid probability
                - Gap width must be positive pixel count
            
            RuntimeError: If YOLO model fails to load
                - Model file might be corrupted
                - Incompatible YOLOv8 version
                - Insufficient memory to load model
        
        Example:
            >>> # Use default settings from .env
            >>> detector = ProductDetector()
            
            >>> # Custom model and thresholds
            >>> detector = ProductDetector(
            ...     model_path="models/custom_yolo.pt",
            ...     confidence_threshold=0.7,
            ...     min_gap_width=120
            ... )
            
            >>> # Override just one parameter
            >>> detector = ProductDetector(confidence_threshold=0.6)
        
        Implementation Notes:
            - Model is loaded immediately (not lazy-loaded) for faster inference
            - YOLO automatically uses GPU if available (CUDA or MPS)
            - First inference may be slower due to CUDA initialization
            - Model is kept in memory for the lifetime of the detector object
        """
        from pathlib import Path
        from ultralytics import YOLO
        from src.shelf_monitor.config.settings import settings
        from src.shelf_monitor.utils.logging import get_logger
        
        # Initialize logger
        self.logger = get_logger(__name__)
        
        # Load configuration from settings if not provided
        self.model_path = model_path or settings.yolo_model_path
        self.confidence_threshold = (
            confidence_threshold 
            if confidence_threshold is not None 
            else settings.confidence_threshold
        )
        self.min_gap_width = (
            min_gap_width 
            if min_gap_width is not None 
            else settings.min_gap_width
        )
        
        # Validate configuration parameters
        self._validate_config()
        
        # Load YOLO model
        self.logger.info(
            f"Loading YOLO model from {self.model_path}",
            extra={
                "model_path": self.model_path,
                "confidence_threshold": self.confidence_threshold,
                "min_gap_width": self.min_gap_width
            }
        )
        
        try:
            # Check if model file exists
            model_file = Path(self.model_path)
            if not model_file.exists():
                raise FileNotFoundError(
                    f"YOLO model not found at: {self.model_path}\n"
                    f"Have you trained the model? Run tasks T028-T030:\n"
                    f"  python3 scripts/train_yolo.py --epochs 50 --batch 16\n"
                    f"Or check if model path in .env is correct."
                )
            
            # Load YOLO model (will use GPU if available)
            self.model = YOLO(str(model_file))
            
            # Log successful initialization
            device = "GPU" if self.model.device.type in ["cuda", "mps"] else "CPU"
            self.logger.info(
                f"YOLO model loaded successfully on {device}",
                extra={
                    "device": device,
                    "model_size": f"{model_file.stat().st_size / 1024 / 1024:.1f}MB"
                }
            )
            
        except FileNotFoundError:
            # Re-raise FileNotFoundError as-is
            raise
            
        except Exception as e:
            # Wrap other exceptions in RuntimeError with helpful context
            self.logger.error(
                f"Failed to load YOLO model: {str(e)}",
                extra={"model_path": self.model_path, "error_type": type(e).__name__}
            )
            raise RuntimeError(
                f"Failed to load YOLO model from {self.model_path}: {str(e)}\n"
                f"Possible causes:\n"
                f"  - Model file is corrupted (try re-training)\n"
                f"  - Incompatible ultralytics version (check requirements.txt)\n"
                f"  - Insufficient memory (try smaller model or close other apps)\n"
                f"Original error: {type(e).__name__}: {str(e)}"
            ) from e
    
    def _validate_config(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ValueError: If any configuration parameter is invalid
        """
        # Validate confidence threshold
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(
                f"Confidence threshold must be between 0.0 and 1.0, got {self.confidence_threshold}. "
                f"Typical values: 0.4 (more detections) to 0.7 (higher precision)."
            )
        
        # Validate minimum gap width
        if self.min_gap_width <= 0:
            raise ValueError(
                f"Minimum gap width must be positive, got {self.min_gap_width}. "
                f"Typical values: 50-200 pixels depending on camera setup and product size."
            )
    
    def detect_products(
        self, 
        image_path: str,
        confidence_threshold: Optional[float] = None
    ) -> list[Detection]:
        """
        Detect products in a retail shelf image using YOLO inference.
        
        Runs the trained YOLO model on the input image and returns a list of
        Detection objects with bounding boxes, confidence scores, and labels.
        
        The method performs the following steps:
        1. Load image from disk using YOLO's built-in loader
        2. Run YOLO inference with confidence filtering
        3. Convert YOLO predictions to Detection dataclass objects
        4. Sort detections left-to-right (by x-coordinate) for gap analysis
        
        Args:
            image_path: Path to shelf image file (JPG, PNG, etc.)
                - Can be relative or absolute path
                - Image should contain retail shelf with products
                - Supported formats: .jpg, .jpeg, .png, .bmp, .tiff
                - Recommended resolution: 640-1920px width
            
            confidence_threshold: Override default confidence threshold
                - If None, uses self.confidence_threshold from __init__
                - Range: 0.0-1.0
                - Lower = more detections (but more false positives)
                - Higher = fewer detections (but higher precision)
                - Typical: 0.5 for balanced results
        
        Returns:
            List of Detection objects sorted left-to-right (by x-coordinate).
            Each Detection contains:
                - bbox: (x, y, width, height) in pixels
                - confidence: Detection confidence score (0.0-1.0)
                - label: Class label (typically "object" for single-class model)
                - product_id: None (no product mapping in Challenge 1)
        
        Raises:
            FileNotFoundError: If image_path doesn't exist
            ValueError: If confidence_threshold invalid or image unreadable
            RuntimeError: If YOLO inference fails
        
        Example:
            >>> detector = ProductDetector()
            >>> detections = detector.detect_products("data/test/shelf_001.jpg")
            >>> print(f"Found {len(detections)} products")
            Found 47 products
            
            >>> # First detection (leftmost product)
            >>> det = detections[0]
            >>> print(f"Box: {det.bbox}, Confidence: {det.confidence:.2f}")
            Box: (120, 340, 85, 120), Confidence: 0.89
            
            >>> # Use custom confidence threshold
            >>> detections = detector.detect_products("shelf.jpg", confidence_threshold=0.7)
            >>> print(f"High-confidence detections: {len(detections)}")
            High-confidence detections: 35
        
        Performance:
            - Single image latency: 300-400ms (M1/M2 Mac), 150-200ms (NVIDIA GPU)
            - Batch processing: Use YOLO's batch inference for multiple images
            - First inference slower due to model initialization (~500ms)
        
        Implementation Notes:
            - YOLO returns predictions in (x1, y1, x2, y2) format
            - We convert to (x, y, width, height) for Detection dataclass
            - Detections are sorted by x-coordinate for gap analysis
            - Product IDs are set to None (Challenge 1 uses single "object" class)
        """
        from pathlib import Path
        
        # Use instance threshold if not overridden
        conf_threshold = confidence_threshold if confidence_threshold is not None else self.confidence_threshold
        
        # Validate confidence threshold
        if not (0.0 <= conf_threshold <= 1.0):
            raise ValueError(
                f"Confidence threshold must be between 0.0 and 1.0, got {conf_threshold}"
            )
        
        # Check if image exists
        img_path = Path(image_path)
        if not img_path.exists():
            raise FileNotFoundError(
                f"Image not found: {image_path}\n"
                f"Please provide a valid path to a shelf image."
            )
        
        self.logger.info(
            f"Running YOLO inference on {img_path.name}",
            extra={
                "image_path": str(img_path),
                "confidence_threshold": conf_threshold
            }
        )
        
        try:
            # Run YOLO inference
            # verbose=False: Suppress YOLO's progress output
            # conf=conf_threshold: Filter predictions by confidence
            results = self.model.predict(
                source=str(img_path),
                conf=conf_threshold,
                verbose=False
            )
            
            # YOLO returns a list of Results objects (one per image)
            # We only process one image, so take results[0]
            result = results[0]
            
            # Extract detections from YOLO results
            detections = []
            
            # result.boxes contains all detection boxes
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    # Extract bounding box coordinates (xyxy format)
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Convert to (x, y, width, height) format
                    x = int(x1)
                    y = int(y1)
                    width = int(x2 - x1)
                    height = int(y2 - y1)
                    
                    # Extract confidence score
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    # Extract class label (convert class_id to name)
                    class_id = int(box.cls[0].cpu().numpy())
                    label = self.model.names[class_id]
                    
                    # Create Detection object
                    detection = Detection(
                        bbox=(x, y, width, height),
                        confidence=confidence,
                        label=label,
                        product_id=None  # No product mapping in Challenge 1
                    )
                    detections.append(detection)
            
            # Sort detections left-to-right (by x-coordinate) for gap analysis
            detections.sort(key=lambda d: d.bbox[0])
            
            self.logger.info(
                f"Detected {len(detections)} products in {img_path.name}",
                extra={
                    "detection_count": len(detections),
                    "confidence_threshold": conf_threshold,
                    "image_path": str(img_path)
                }
            )
            
            return detections
            
        except FileNotFoundError:
            # Re-raise FileNotFoundError as-is
            raise
            
        except Exception as e:
            # Wrap other exceptions in RuntimeError with context
            self.logger.error(
                f"YOLO inference failed: {str(e)}",
                extra={
                    "image_path": str(img_path),
                    "error_type": type(e).__name__
                }
            )
            raise RuntimeError(
                f"Failed to run YOLO inference on {img_path.name}: {str(e)}\n"
                f"Possible causes:\n"
                f"  - Image file is corrupted or invalid format\n"
                f"  - Insufficient memory (try smaller image or close other apps)\n"
                f"  - YOLO model issue (try reloading detector)\n"
                f"Original error: {type(e).__name__}: {str(e)}"
            ) from e
    
    def detect_gaps(
        self,
        detections: list[Detection],
        image_width: int,
        min_gap_width: Optional[int] = None
    ) -> list[GapRegion]:
        """
        Detect empty shelf spaces (gaps) between product detections.
        
        Analyzes horizontal spacing between detected products to identify
        out-of-stock areas. A gap is considered significant if its width
        exceeds the minimum threshold (default: 100px).
        
        The algorithm works as follows:
        1. Sort detections left-to-right by x-coordinate (if not already sorted)
        2. Compute horizontal gaps between consecutive detections
        3. Also check gaps at shelf edges (start and end)
        4. Flag gaps exceeding min_gap_width as significant
        5. Return list of GapRegion objects with bbox and metadata
        
        Args:
            detections: List of Detection objects from detect_products()
                - Must contain bbox (x, y, width, height) for each detection
                - Should be sorted left-to-right (automatically sorted by detect_products)
                - Can be empty list (returns edge gaps only)
            
            image_width: Width of the shelf image in pixels
                - Used to compute gaps at image edges
                - Should match the actual image dimensions
                - Typical values: 640-1920px
            
            min_gap_width: Minimum gap width to flag as significant (pixels)
                - If None, uses self.min_gap_width from __init__
                - Gaps smaller than this are considered normal product spacing
                - Typical values: 50-200px depending on camera setup
                - Default: 100px (about 2x normal product spacing)
        
        Returns:
            List of GapRegion objects sorted left-to-right.
            Each GapRegion contains:
                - bbox: (x, y, width, height) - gap bounding box
                - gap_width: Horizontal gap width in pixels
                - is_significant: True if gap_width >= min_gap_width
            
            Edge Cases:
                - No detections: Returns one gap spanning entire image width
                - Single detection: Returns gaps before and after the detection
                - Detections touching: No gap between them (gap_width = 0)
        
        Raises:
            ValueError: If image_width <= 0 or min_gap_width < 0
        
        Example:
            >>> detector = ProductDetector()
            >>> detections = detector.detect_products("shelf.jpg")
            >>> gaps = detector.detect_gaps(detections, image_width=1920)
            >>> 
            >>> # Filter significant gaps (out-of-stock areas)
            >>> significant_gaps = [g for g in gaps if g.is_significant]
            >>> print(f"Found {len(significant_gaps)} out-of-stock areas")
            Found 3 out-of-stock areas
            >>> 
            >>> # Largest gap
            >>> largest_gap = max(gaps, key=lambda g: g.gap_width)
            >>> print(f"Largest gap: {largest_gap.gap_width}px at x={largest_gap.bbox[0]}")
            Largest gap: 285px at x=1240
            >>> 
            >>> # Gap severity classification
            >>> for gap in significant_gaps:
            ...     if gap.gap_width > 150:
            ...         severity = "HIGH"
            ...     elif gap.gap_width > 100:
            ...         severity = "MEDIUM"
            ...     else:
            ...         severity = "LOW"
            ...     print(f"Gap at x={gap.bbox[0]}: {gap.gap_width}px ({severity} priority)")
            Gap at x=340: 120px (MEDIUM priority)
            Gap at x=890: 285px (HIGH priority)
            Gap at x=1620: 105px (MEDIUM priority)
        
        Performance:
            - Time complexity: O(n) where n = number of detections
            - Space complexity: O(n) for storing gap regions
            - Typical latency: <5ms for 100 detections
            - Much faster than YOLO inference (300-400ms)
        
        Implementation Notes:
            - Detections are automatically sorted by detect_products()
            - Gap height is computed from surrounding detection heights
            - Gap y-coordinate is averaged from surrounding detections
            - Edge gaps (at x=0 and x=image_width) are always included
            - Empty shelf (no detections) results in one full-width gap
        """
        # Use instance threshold if not overridden
        gap_threshold = min_gap_width if min_gap_width is not None else self.min_gap_width
        
        # Validate inputs
        if image_width <= 0:
            raise ValueError(
                f"Image width must be positive, got {image_width}. "
                f"Provide the actual image width in pixels (e.g., 1920)."
            )
        
        if gap_threshold < 0:
            raise ValueError(
                f"Minimum gap width cannot be negative, got {gap_threshold}. "
                f"Use 0 to include all gaps, or positive value to filter."
            )
        
        self.logger.info(
            f"Analyzing gaps for {len(detections)} detections",
            extra={
                "detection_count": len(detections),
                "image_width": image_width,
                "min_gap_width": gap_threshold
            }
        )
        
        # Sort detections by x-coordinate (left-to-right) if not already sorted
        sorted_detections = sorted(detections, key=lambda d: d.bbox[0])
        
        gaps: list[GapRegion] = []
        
        # Special case: No detections means entire shelf is empty
        if not sorted_detections:
            self.logger.warning(
                "No products detected - entire shelf appears empty",
                extra={"image_width": image_width}
            )
            
            # Create one gap spanning the entire image
            # Use a default height of 100px since we have no reference detections
            default_height = 100
            gap = GapRegion(
                bbox=(0, 0, image_width, default_height),
                gap_width=image_width,
                is_significant=image_width >= gap_threshold
            )
            return [gap]
        
        # Compute average detection height for gap height estimation
        avg_height = sum(d.bbox[3] for d in sorted_detections) // len(sorted_detections)
        avg_y = sum(d.bbox[1] for d in sorted_detections) // len(sorted_detections)
        
        # Check gap at left edge (from x=0 to first detection)
        first_det = sorted_detections[0]
        first_det_x, first_det_y, first_det_w, first_det_h = first_det.bbox
        
        left_edge_gap_width = first_det_x
        if left_edge_gap_width > 0:  # There's space before first detection
            gap = GapRegion(
                bbox=(0, first_det_y, left_edge_gap_width, first_det_h),
                gap_width=left_edge_gap_width,
                is_significant=left_edge_gap_width >= gap_threshold
            )
            gaps.append(gap)
        
        # Check gaps between consecutive detections
        for i in range(len(sorted_detections) - 1):
            current_det = sorted_detections[i]
            next_det = sorted_detections[i + 1]
            
            # Extract bounding boxes
            curr_x, curr_y, curr_w, curr_h = current_det.bbox
            next_x, next_y, next_w, next_h = next_det.bbox
            
            # Compute gap between current detection's right edge and next detection's left edge
            gap_start_x = curr_x + curr_w
            gap_end_x = next_x
            gap_width = gap_end_x - gap_start_x
            
            # Only create gap if there's actual space (no overlap or touching)
            if gap_width > 0:
                # Use average height of surrounding detections for gap height
                gap_height = (curr_h + next_h) // 2
                gap_y = (curr_y + next_y) // 2
                
                gap = GapRegion(
                    bbox=(gap_start_x, gap_y, gap_width, gap_height),
                    gap_width=gap_width,
                    is_significant=gap_width >= gap_threshold
                )
                gaps.append(gap)
        
        # Check gap at right edge (from last detection to image_width)
        last_det = sorted_detections[-1]
        last_det_x, last_det_y, last_det_w, last_det_h = last_det.bbox
        
        right_edge_gap_start = last_det_x + last_det_w
        right_edge_gap_width = image_width - right_edge_gap_start
        
        if right_edge_gap_width > 0:  # There's space after last detection
            gap = GapRegion(
                bbox=(right_edge_gap_start, last_det_y, right_edge_gap_width, last_det_h),
                gap_width=right_edge_gap_width,
                is_significant=right_edge_gap_width >= gap_threshold
            )
            gaps.append(gap)
        
        # Log results
        significant_gaps = [g for g in gaps if g.is_significant]
        self.logger.info(
            f"Detected {len(gaps)} total gaps ({len(significant_gaps)} significant)",
            extra={
                "total_gaps": len(gaps),
                "significant_gaps": len(significant_gaps),
                "min_gap_width": gap_threshold
            }
        )
        
        return gaps
