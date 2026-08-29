"""
Contract: SKU Classifier Module
Module: src/shelf_monitor/core/classifier.py
Purpose: Product recognition and SKU classification for Challenge 2

This contract defines the interface for the SKUClassifier class, which:
1. Classifies detected products to specific SKUs using YOLOv8
2. Compares performance with Azure Custom Vision classifier
3. Links detections to product catalog via SKU
4. Evaluates model metrics (mAP, accuracy, FPS)

Related:
- Challenge 2: Product Recognition (T046-T066)
- Data Model: Detection dataclass, Product table
- YOLO Wrapper: src/shelf_monitor/models/yolo.py
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pathlib import Path


# ============================================
# Data Classes
# ============================================

@dataclass
class ClassificationResult:
    """
    Represents SKU classification result for a single detection.
    
    Attributes:
        sku: Predicted Stock Keeping Unit
        product_id: Product ID from catalog (if matched)
        confidence: Classification confidence (0.0-1.0)
        bbox: Bounding box as (x, y, width, height)
        class_id: Model class ID (internal)
    
    Example:
        >>> result = ClassificationResult(
        ...     sku="COKE-500ML",
        ...     product_id=1,
        ...     confidence=0.94,
        ...     bbox=(120, 50, 80, 150),
        ...     class_id=5
        ... )
    """
    sku: str
    product_id: Optional[int]
    confidence: float
    bbox: Tuple[int, int, int, int]
    class_id: int


@dataclass
class ModelMetrics:
    """
    Evaluation metrics for SKU classification model.
    
    Attributes:
        map_50: Mean Average Precision at IoU=0.5
        map_50_95: Mean Average Precision at IoU=0.5:0.95
        precision: Precision across all classes
        recall: Recall across all classes
        f1_score: F1 score (harmonic mean of precision/recall)
        inference_fps: Inference speed (frames per second)
        model_size_mb: Model file size in megabytes
    
    Target Metrics (Challenge 2):
        - mAP@0.5 > 85%
        - Accuracy > 90%
        - Inference FPS > 10 (on GPU)
    
    Example:
        >>> metrics = ModelMetrics(
        ...     map_50=0.87,
        ...     map_50_95=0.72,
        ...     precision=0.91,
        ...     recall=0.88,
        ...     f1_score=0.89,
        ...     inference_fps=15.3,
        ...     model_size_mb=22.5
        ... )
    """
    map_50: float
    map_50_95: float
    precision: float
    recall: float
    f1_score: float
    inference_fps: float
    model_size_mb: float


# ============================================
# SKU Classifier Interface
# ============================================

class SKUClassifier:
    """
    Classifies products to specific SKUs using YOLOv8 object detection.
    
    This class wraps YOLOv8 model for end-to-end product recognition:
    detection + classification in single pass.
    
    Responsibilities:
        1. Load trained YOLOv8 model from checkpoint
        2. Perform inference on shelf images
        3. Map predicted classes to SKUs via product catalog
        4. Calculate evaluation metrics (mAP, accuracy, FPS)
        5. Compare with Azure Custom Vision performance
    
    Model Details:
        - Architecture: YOLOv8s (small variant)
        - Training: 50 epochs on SKU-110K dataset
        - Classes: Product categories from SKU-110K
        - Input Size: 640x640 pixels
        - Batch Size: 16 (training), 1 (inference)
    
    Configuration:
        - MODEL_PATH: Path to trained YOLO weights (.pt file)
        - CONFIDENCE_THRESHOLD: Minimum confidence (default: 0.5)
        - IOU_THRESHOLD: NMS IoU threshold (default: 0.4)
        - DEVICE: 'cuda' or 'cpu' (auto-detect GPU)
    
    Usage:
        >>> classifier = SKUClassifier(model_path="models/yolov8s_sku.pt")
        >>> results = classifier.classify_products("shelf_image.jpg")
        >>> for result in results:
        ...     print(f"{result.sku}: {result.confidence:.2f}")
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.4,
        device: Optional[str] = None
    ) -> None:
        """
        Initialize SKUClassifier with trained YOLOv8 model.
        
        Args:
            model_path: Path to YOLOv8 weights file (.pt)
            confidence_threshold: Minimum confidence for predictions
            iou_threshold: NMS IoU threshold for duplicate removal
            device: 'cuda', 'cpu', or None (auto-detect)
        
        Raises:
            FileNotFoundError: If model_path does not exist
            ValueError: If thresholds not in valid range
            RuntimeError: If model fails to load
        
        Implementation Notes:
            - Load model with ultralytics.YOLO(model_path)
            - Auto-detect GPU: torch.cuda.is_available()
            - Validate model classes match product catalog
            - Warm-up inference with dummy image
        """
        pass
    
    def classify_products(
        self,
        image_path: str,
        return_crops: bool = False
    ) -> List[ClassificationResult]:
        """
        Classify all products in shelf image to SKUs.
        
        This performs end-to-end detection + classification:
        1. Detect product bounding boxes
        2. Classify each detection to SKU
        3. Apply NMS to remove duplicates
        4. Link SKUs to product catalog
        
        Args:
            image_path: Path to shelf image file
            return_crops: If True, save cropped product images
        
        Returns:
            List of ClassificationResult objects with SKU predictions
        
        Raises:
            FileNotFoundError: If image_path does not exist
            RuntimeError: If inference fails
        
        Implementation Notes:
            - Call model.predict(image_path, conf=threshold)
            - Convert YOLO results to ClassificationResult
            - Map class_id to SKU using catalog lookup
            - If return_crops=True, save crops to data/crops/
        
        Example:
            >>> classifier = SKUClassifier()
            >>> results = classifier.classify_products("shelf.jpg")
            >>> print(f"Classified {len(results)} products")
            Classified 28 products
            >>> sku_counts = {}
            >>> for r in results:
            ...     sku_counts[r.sku] = sku_counts.get(r.sku, 0) + 1
            >>> print(sku_counts)
            {'COKE-500ML': 8, 'PEPSI-330ML': 5, ...}
        """
        pass
    
    def classify_batch(
        self,
        image_paths: List[str],
        batch_size: int = 8
    ) -> List[List[ClassificationResult]]:
        """
        Classify multiple images in batches for efficiency.
        
        Args:
            image_paths: List of paths to shelf images
            batch_size: Number of images to process simultaneously
        
        Returns:
            List of results lists (one per image)
        
        Implementation Notes:
            - Use model.predict() with batch processing
            - Measure inference time for FPS calculation
            - Handle batch errors gracefully (skip failed images)
        
        Example:
            >>> classifier = SKUClassifier()
            >>> image_paths = ["shelf1.jpg", "shelf2.jpg", "shelf3.jpg"]
            >>> batch_results = classifier.classify_batch(image_paths)
            >>> for img, results in zip(image_paths, batch_results):
            ...     print(f"{img}: {len(results)} products")
        """
        pass
    
    def evaluate_model(
        self,
        test_images_dir: str,
        ground_truth_annotations: str
    ) -> ModelMetrics:
        """
        Evaluate model performance on test dataset.
        
        Calculates comprehensive metrics:
        - mAP@0.5: Primary metric for object detection
        - mAP@0.5:0.95: Stricter metric across IoU thresholds
        - Precision, Recall, F1: Per-class and overall
        - Inference FPS: Speed on current hardware
        
        Args:
            test_images_dir: Directory with test images
            ground_truth_annotations: Path to YOLO format labels
        
        Returns:
            ModelMetrics object with all evaluation metrics
        
        Raises:
            FileNotFoundError: If test data not found
            ValueError: If annotations format invalid
        
        Implementation Notes:
            - Use YOLO.val() for validation metrics
            - Calculate FPS: num_images / total_inference_time
            - Compare against target: mAP@0.5 > 85%, accuracy > 90%
            - Log detailed per-class metrics
        
        Example:
            >>> classifier = SKUClassifier()
            >>> metrics = classifier.evaluate_model(
            ...     test_images_dir="data/test/images",
            ...     ground_truth_annotations="data/test/labels"
            ... )
            >>> print(f"mAP@0.5: {metrics.map_50:.2%}")
            mAP@0.5: 87.34%
            >>> print(f"Inference FPS: {metrics.inference_fps:.1f}")
            Inference FPS: 15.3
        """
        pass
    
    def link_to_catalog(
        self,
        results: List[ClassificationResult],
        catalog: Dict[str, int]
    ) -> List[ClassificationResult]:
        """
        Link SKU predictions to product catalog IDs.
        
        Args:
            results: Classification results with SKU strings
            catalog: Mapping from SKU to product_id {sku: product_id}
        
        Returns:
            Updated results with product_id filled
        
        Implementation Notes:
            - Lookup each result.sku in catalog
            - Set result.product_id if SKU found
            - Log warnings for unrecognized SKUs
            - Handle fuzzy matching if exact match fails
        
        Example:
            >>> catalog = {"COKE-500ML": 1, "PEPSI-330ML": 2}
            >>> results = [ClassificationResult(sku="COKE-500ML", ...)]
            >>> linked = classifier.link_to_catalog(results, catalog)
            >>> print(linked[0].product_id)
            1
        """
        pass
    
    def compare_with_azure(
        self,
        image_path: str,
        azure_predictor: object
    ) -> Dict[str, any]:
        """
        Compare YOLOv8 performance with Azure Custom Vision.
        
        Comparison Metrics:
        - Accuracy: Agreement between models
        - Speed: Inference time (YOLO vs Azure)
        - Cost: Free (local) vs API calls ($)
        - Detections: Number found by each model
        
        Args:
            image_path: Test image path
            azure_predictor: Azure Custom Vision prediction client
        
        Returns:
            Dict with comparison results
        
        Example:
            >>> comparison = classifier.compare_with_azure(
            ...     "shelf.jpg",
            ...     azure_predictor
            ... )
            >>> print(comparison)
            {
                'yolo_detections': 28,
                'azure_detections': 26,
                'agreement': 0.92,
                'yolo_time_ms': 45.2,
                'azure_time_ms': 312.5,
                'yolo_fps': 22.1,
                'azure_fps': 3.2,
                'cost_per_image': {'yolo': 0.00, 'azure': 0.002}
            }
        """
        pass


# ============================================
# Helper Functions
# ============================================

def convert_coco_to_yolo(
    coco_annotations: str,
    output_dir: str,
    class_mapping: Dict[int, str]
) -> None:
    """
    Convert COCO format annotations to YOLO format for training.
    
    COCO Format: JSON with bbox as [x, y, width, height]
    YOLO Format: TXT files with normalized coordinates
    
    Args:
        coco_annotations: Path to COCO JSON file
        output_dir: Directory to save YOLO txt files
        class_mapping: Mapping from COCO category_id to class_name
    
    Implementation Notes:
        - Parse COCO JSON with json.load()
        - For each image: create <image_id>.txt
        - For each annotation: write line "class_id x_center y_center width height"
        - Normalize coordinates: divide by image width/height
    
    Example:
        >>> convert_coco_to_yolo(
        ...     "annotations/instances_train.json",
        ...     "data/train/labels",
        ...     class_mapping={0: "beverage", 1: "snack"}
        ... )
        Converted 8,233 images with 45,127 annotations
    """
    pass


def train_yolov8_model(
    data_yaml: str,
    epochs: int = 50,
    batch_size: int = 16,
    image_size: int = 640,
    pretrained: str = "yolov8s.pt"
) -> str:
    """
    Train YOLOv8 model on SKU-110K dataset.
    
    This is the main training function called by T050.
    
    Args:
        data_yaml: Path to data.yaml config file
        epochs: Number of training epochs
        batch_size: Batch size for training
        image_size: Input image size (pixels)
        pretrained: Pretrained weights (COCO or custom)
    
    Returns:
        Path to best model checkpoint (.pt file)
    
    Training Configuration:
        - Optimizer: AdamW
        - Learning Rate: 0.01 (with cosine annealing)
        - Augmentation: Mosaic, MixUp, HSV, Flip
        - Validation: Every 5 epochs
        - Save: Best model by mAP@0.5
    
    Example:
        >>> best_model = train_yolov8_model(
        ...     data_yaml="data/sku110k.yaml",
        ...     epochs=50,
        ...     batch_size=16
        ... )
        Epoch 1/50: train_loss=1.234, val_mAP@0.5=0.456
        ...
        Epoch 50/50: train_loss=0.234, val_mAP@0.5=0.873
        >>> print(f"Best model: {best_model}")
        Best model: runs/train/exp/weights/best.pt
    """
    pass


# ============================================
# Testing Interface
# ============================================

def test_classifier_with_sample_images() -> None:
    """
    Integration test for SKUClassifier with sample images.
    
    Test Cases:
        1. Single image classification
        2. Batch classification (5 images)
        3. Model evaluation on test set
        4. Comparison with Azure Custom Vision
    
    Assertions:
        - mAP@0.5 > 85%
        - Inference FPS > 10
        - SKU accuracy > 90%
        - All SKUs linked to product catalog
    
    Usage:
        >>> test_classifier_with_sample_images()
        ✓ Single image: 24 products classified
        ✓ Batch processing: 5 images in 0.3s (16.7 FPS)
        ✓ Test set evaluation: mAP@0.5=87.3%
        ✓ Azure comparison: YOLO 6.8x faster
        ✓ All assertions passed
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T046: Create SKUClassifier class skeleton
    - T047: Create YOLOv8 wrapper
    - T048: Convert SKU-110K annotations (COCO → YOLO)
    - T049: Create data.yaml configuration
    - T050: Train YOLOv8s model (50 epochs)
    - T053: Implement classify_products()
    - T054: Implement evaluate_model()
    - T060: Create unit tests

Dependencies:
    - Ultralytics YOLOv8 (ultralytics package)
    - PyTorch 2.0+ with CUDA support
    - SKU-110K dataset (11,762 images)
    - Product catalog (from database)

Performance Targets:
    - mAP@0.5 > 85%
    - Classification accuracy > 90%
    - Inference FPS > 10 (on GPU)
    - Model size < 50MB

Next Steps:
    1. Implement this contract in src/shelf_monitor/core/classifier.py
    2. Create YOLOv8 wrapper in src/shelf_monitor/models/yolo.py (T047)
    3. Convert dataset annotations (T048)
    4. Train model for 50 epochs (T050)
    5. Write unit tests in tests/unit/test_classifier.py (T060)
"""
