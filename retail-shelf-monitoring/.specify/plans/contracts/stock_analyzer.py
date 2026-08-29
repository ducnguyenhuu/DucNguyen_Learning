"""
Contract: Stock Analyzer Module
Module: src/shelf_monitor/core/stock_analyzer.py
Purpose: Stock level estimation and counting for Challenge 3

This contract defines the interface for the StockAnalyzer class, which:
1. Aggregates product detections by SKU
2. Estimates stock quantities on shelves
3. Calculates depth estimates (Phase 1: simple, Phase 2: height-based)
4. Provides stock count trends over time

Related:
- Challenge 3: Stock Level Estimation (T067-T079)
- Data Model: StockCount dataclass, Detection table
- Database: Aggregation queries in crud.py
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import datetime


# ============================================
# Data Classes
# ============================================

@dataclass
class ProductCount:
    """
    Aggregated stock count for a single SKU.
    
    Attributes:
        product_id: Product identifier from catalog
        sku: Stock Keeping Unit
        count: Number of visible products (front-facing)
        depth_estimate: Estimated depth (rows behind front)
        total_quantity: count × depth_estimate
        avg_confidence: Average detection confidence
        timestamps: Detection timestamps for trend analysis
    
    Validation:
        - count >= 0
        - depth_estimate >= 1
        - avg_confidence in [0.0, 1.0]
    
    Example:
        >>> count = ProductCount(
        ...     product_id=1,
        ...     sku="COKE-500ML",
        ...     count=12,
        ...     depth_estimate=1,
        ...     total_quantity=12,
        ...     avg_confidence=0.91,
        ...     timestamps=[datetime(2024, 1, 15, 10, 30)]
        ... )
    """
    product_id: int
    sku: str
    count: int
    depth_estimate: int
    total_quantity: int
    avg_confidence: float
    timestamps: List[datetime]


@dataclass
class StockTrend:
    """
    Stock level trend over time for a single SKU.
    
    Attributes:
        product_id: Product identifier
        sku: Stock Keeping Unit
        counts_over_time: List of (timestamp, count) tuples
        avg_count: Average count across all timestamps
        min_count: Minimum count (potential stockout)
        max_count: Maximum count (peak stock)
        velocity: Stock depletion rate (units/day)
    
    Usage:
        Used to predict stockout timing and optimize reordering.
    
    Example:
        >>> trend = StockTrend(
        ...     product_id=1,
        ...     sku="COKE-500ML",
        ...     counts_over_time=[
        ...         (datetime(2024, 1, 15, 8, 0), 20),
        ...         (datetime(2024, 1, 15, 12, 0), 15),
        ...         (datetime(2024, 1, 15, 16, 0), 10)
        ...     ],
        ...     avg_count=15.0,
        ...     min_count=10,
        ...     max_count=20,
        ...     velocity=-2.5  # -2.5 units per 4-hour period
        ... )
    """
    product_id: int
    sku: str
    counts_over_time: List[Tuple[datetime, int]]
    avg_count: float
    min_count: int
    max_count: int
    velocity: float


# ============================================
# Stock Analyzer Interface
# ============================================

class StockAnalyzer:
    """
    Analyzes product detections to estimate stock levels on shelves.
    
    This class provides stock counting and trend analysis for inventory
    management. It aggregates detections by SKU and estimates total
    quantities including products behind the front row.
    
    Responsibilities:
        1. Count products by SKU from detection results
        2. Estimate depth (Phase 1: fixed=1, Phase 2: height-based)
        3. Calculate total quantities (count × depth)
        4. Track stock trends over time
        5. Identify low-stock products (potential stockouts)
    
    Depth Estimation Strategy:
        - Phase 1 (T070): depth_estimate = 1 (front row only)
        - Phase 2 (Future): Analyze bbox heights to estimate rows
          - If bbox_height > avg_height * 1.5, estimate depth = 2-3
          - Use heuristics based on product category
    
    Accuracy Targets:
        - Count accuracy > 90%
        - MAPE (Mean Absolute Percentage Error) < 15%
    
    Configuration:
        - MIN_CONFIDENCE: Minimum detection confidence to count (default: 0.5)
        - DEPTH_THRESHOLD: Height multiplier for depth estimation (default: 1.5)
    
    Usage:
        >>> analyzer = StockAnalyzer()
        >>> detections = [...]  # From SKUClassifier
        >>> counts = analyzer.count_products(detections)
        >>> for count in counts:
        ...     print(f"{count.sku}: {count.total_quantity} units")
    """
    
    def __init__(
        self,
        min_confidence: float = 0.5,
        depth_threshold: float = 1.5
    ) -> None:
        """
        Initialize StockAnalyzer with configuration.
        
        Args:
            min_confidence: Minimum detection confidence to include in counts
            depth_threshold: Height multiplier for depth estimation (Phase 2)
        
        Raises:
            ValueError: If min_confidence not in [0.0, 1.0]
        
        Implementation Notes:
            - Store configuration parameters
            - Initialize statistics tracking (for MAPE calculation)
        """
        pass
    
    def count_products(
        self,
        detections: List[Dict],
        group_by: str = "sku"
    ) -> List[ProductCount]:
        """
        Aggregate detections by SKU to count products.
        
        Algorithm:
            1. Filter detections by min_confidence
            2. Group detections by SKU (or product_id)
            3. For each group:
               - count = number of detections
               - depth_estimate = estimate_depth(detections)
               - total_quantity = count × depth_estimate
               - avg_confidence = mean(detection.confidence)
        
        Args:
            detections: List of detection dicts with keys:
                - sku, product_id, confidence, bbox, timestamp
            group_by: Grouping key ("sku" or "product_id")
        
        Returns:
            List of ProductCount objects, sorted by total_quantity (desc)
        
        Raises:
            ValueError: If detections list is empty or missing required keys
        
        Implementation Notes:
            - Use collections.defaultdict for grouping
            - Call estimate_depth() for each SKU group
            - Sort results by total_quantity descending
        
        Example:
            >>> detections = [
            ...     {"sku": "COKE-500ML", "confidence": 0.9, "bbox": (10,10,80,150)},
            ...     {"sku": "COKE-500ML", "confidence": 0.85, "bbox": (100,10,80,150)},
            ...     {"sku": "PEPSI-330ML", "confidence": 0.92, "bbox": (200,10,70,130)}
            ... ]
            >>> counts = analyzer.count_products(detections)
            >>> print(counts[0])
            ProductCount(sku='COKE-500ML', count=2, total_quantity=2)
        """
        pass
    
    def estimate_depth(
        self,
        detections: List[Dict],
        phase: int = 1
    ) -> int:
        """
        Estimate depth (number of product rows) from detection heights.
        
        Phase 1 (Simple):
            - Return 1 (assume single front-facing row)
        
        Phase 2 (Height-based):
            - Calculate avg_height = mean(detection.bbox[3])
            - If max_height > avg_height * depth_threshold:
                - depth = 2 or 3 (heuristic based on height ratio)
            - Else: depth = 1
        
        Args:
            detections: List of detections for a single SKU
            phase: 1 for simple, 2 for height-based
        
        Returns:
            Estimated depth (1, 2, or 3)
        
        Implementation Notes:
            - Phase 1: Always return 1 (T070)
            - Phase 2: Implement height analysis heuristic
            - Consider product category: beverages often stacked deeper
        
        Example:
            >>> detections = [
            ...     {"bbox": (10, 10, 80, 150)},  # height=150
            ...     {"bbox": (100, 10, 80, 160)}  # height=160
            ... ]
            >>> depth = analyzer.estimate_depth(detections, phase=1)
            >>> print(depth)
            1
            >>> depth = analyzer.estimate_depth(detections, phase=2)
            >>> print(depth)
            2  # Taller bboxes suggest depth
        """
        pass
    
    def analyze_stock_levels(
        self,
        analysis_job_id: int,
        db_session: object
    ) -> List[ProductCount]:
        """
        Analyze stock levels from database for a specific analysis job.
        
        This method queries the database to aggregate detections and
        calculate stock counts, avoiding in-memory processing for
        large datasets.
        
        Args:
            analysis_job_id: ID of analysis job to query
            db_session: SQLAlchemy database session
        
        Returns:
            List of ProductCount objects from database aggregation
        
        Implementation Notes:
            - Execute SQL query: GROUP BY product_id, COUNT(*)
            - Join with products table to get SKU
            - Calculate avg_confidence from detection.confidence
            - Call estimate_depth() if phase=2
        
        SQL Query Example:
            SELECT 
                p.id, p.sku, COUNT(d.id) as count,
                AVG(d.confidence) as avg_confidence
            FROM detections d
            JOIN products p ON d.product_id = p.id
            WHERE d.analysis_job_id = ?
            GROUP BY p.id, p.sku
            ORDER BY count DESC
        
        Example:
            >>> counts = analyzer.analyze_stock_levels(
            ...     analysis_job_id=1,
            ...     db_session=session
            ... )
            >>> for count in counts[:5]:  # Top 5 products
            ...     print(f"{count.sku}: {count.total_quantity}")
        """
        pass
    
    def get_stock_trends(
        self,
        product_id: int,
        start_date: datetime,
        end_date: datetime,
        db_session: object
    ) -> StockTrend:
        """
        Calculate stock level trends over time for a product.
        
        This enables:
        - Stockout prediction (when will stock run out?)
        - Reorder timing optimization
        - Demand pattern analysis
        
        Args:
            product_id: Product to analyze
            start_date: Start of time period
            end_date: End of time period
            db_session: SQLAlchemy database session
        
        Returns:
            StockTrend object with historical counts and statistics
        
        Implementation Notes:
            - Query detections grouped by date/hour
            - Calculate velocity: linear regression slope
            - Identify min_count (potential stockout)
            - Return time-series data for visualization
        
        Example:
            >>> trend = analyzer.get_stock_trends(
            ...     product_id=1,
            ...     start_date=datetime(2024, 1, 15),
            ...     end_date=datetime(2024, 1, 16),
            ...     db_session=session
            ... )
            >>> print(f"Velocity: {trend.velocity:.2f} units/hour")
            Velocity: -0.42 units/hour
            >>> if trend.velocity < 0:
            ...     hours_until_empty = trend.min_count / abs(trend.velocity)
            ...     print(f"Stockout in {hours_until_empty:.1f} hours")
        """
        pass
    
    def identify_low_stock(
        self,
        counts: List[ProductCount],
        threshold: int = 5
    ) -> List[ProductCount]:
        """
        Identify products with low stock (potential stockouts).
        
        Args:
            counts: List of ProductCount objects
            threshold: Minimum quantity threshold (units)
        
        Returns:
            Filtered list of low-stock products
        
        Implementation Notes:
            - Filter where total_quantity < threshold
            - Sort by total_quantity ascending (most urgent first)
        
        Example:
            >>> counts = analyzer.count_products(detections)
            >>> low_stock = analyzer.identify_low_stock(counts, threshold=5)
            >>> for product in low_stock:
            ...     print(f"⚠️ {product.sku}: {product.total_quantity} units")
            ⚠️ PEPSI-330ML: 2 units
            ⚠️ SPRITE-500ML: 4 units
        """
        pass
    
    def calculate_accuracy(
        self,
        predicted_counts: List[ProductCount],
        ground_truth_counts: Dict[str, int]
    ) -> Tuple[float, float]:
        """
        Calculate count accuracy metrics for evaluation.
        
        Metrics:
            - Accuracy: Percentage of exact matches
            - MAPE: Mean Absolute Percentage Error
        
        Args:
            predicted_counts: Model predictions
            ground_truth_counts: Manual counts {sku: count}
        
        Returns:
            Tuple of (accuracy, mape)
        
        Formula:
            MAPE = (1/n) * Σ |actual - predicted| / actual
        
        Target:
            - Accuracy > 90%
            - MAPE < 15%
        
        Example:
            >>> predicted = [ProductCount(sku="COKE", count=12, ...)]
            >>> ground_truth = {"COKE": 11}
            >>> accuracy, mape = analyzer.calculate_accuracy(predicted, ground_truth)
            >>> print(f"Accuracy: {accuracy:.2%}, MAPE: {mape:.2%}")
            Accuracy: 92.31%, MAPE: 8.33%
        """
        pass


# ============================================
# Helper Functions
# ============================================

def aggregate_detections_by_sku(
    detections: List[Dict],
    min_confidence: float = 0.5
) -> Dict[str, List[Dict]]:
    """
    Group detections by SKU for batch processing.
    
    Args:
        detections: List of detection dicts
        min_confidence: Filter threshold
    
    Returns:
        Dict mapping SKU to list of detections
    
    Example:
        >>> detections = [
        ...     {"sku": "COKE-500ML", "confidence": 0.9},
        ...     {"sku": "COKE-500ML", "confidence": 0.85},
        ...     {"sku": "PEPSI-330ML", "confidence": 0.92}
        ... ]
        >>> grouped = aggregate_detections_by_sku(detections)
        >>> print(grouped.keys())
        dict_keys(['COKE-500ML', 'PEPSI-330ML'])
        >>> print(len(grouped['COKE-500ML']))
        2
    """
    pass


def calculate_velocity(
    counts_over_time: List[Tuple[datetime, int]]
) -> float:
    """
    Calculate stock depletion velocity (linear regression slope).
    
    Args:
        counts_over_time: List of (timestamp, count) tuples
    
    Returns:
        Velocity in units per day (negative = depletion)
    
    Implementation Notes:
        - Convert timestamps to hours since first observation
        - Fit linear regression: count = velocity * hours + intercept
        - Return velocity in units/day
    
    Example:
        >>> counts = [
        ...     (datetime(2024, 1, 15, 8, 0), 20),
        ...     (datetime(2024, 1, 15, 12, 0), 15),
        ...     (datetime(2024, 1, 15, 16, 0), 10)
        ... ]
        >>> velocity = calculate_velocity(counts)
        >>> print(f"{velocity:.2f} units/day")
        -30.00 units/day  # Losing 30 units per day
    """
    pass


# ============================================
# Testing Interface
# ============================================

def test_stock_analyzer_with_sample_data() -> None:
    """
    Integration test for StockAnalyzer with sample detections.
    
    Test Cases:
        1. Count products from detection list
        2. Estimate depth (Phase 1: always 1)
        3. Identify low-stock products
        4. Calculate accuracy metrics
    
    Assertions:
        - All counts >= 0
        - depth_estimate = 1 (Phase 1)
        - Accuracy > 90%
        - MAPE < 15%
    
    Usage:
        >>> test_stock_analyzer_with_sample_data()
        ✓ Counted 15 unique SKUs
        ✓ Total quantity: 247 units
        ✓ Low stock: 3 products
        ✓ Accuracy: 93.2%, MAPE: 8.7%
        ✓ All assertions passed
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T067: Create ProductCount dataclass
    - T068: Create StockAnalyzer class
    - T069: Implement count_products()
    - T070: Implement estimate_depth() (Phase 1: return 1)
    - T071: Create database aggregation query in crud.py
    - T074: Create unit tests

Dependencies:
    - SKUClassifier (for input detections)
    - Database (for aggregation queries)
    - NumPy/SciPy (for trend analysis, linear regression)

Accuracy Targets:
    - Count accuracy > 90%
    - MAPE < 15%
    - Velocity calculation R² > 0.7

Next Steps:
    1. Implement this contract in src/shelf_monitor/core/stock_analyzer.py
    2. Create database aggregation queries in crud.py (T071)
    3. Write unit tests in tests/unit/test_stock_analyzer.py (T074)
    4. Create Jupyter notebook for demos (T076)
"""
