"""
Shared utility functions for the loan underwriting system.

This module provides common helper functions used across agents and services.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging for a module.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def save_json(data: Dict[str, Any], filepath: Path) -> None:
    """
    Save dictionary as JSON file.
    
    Args:
        data: Dictionary to save
        filepath: Path where to save the file
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


def load_json(filepath: Path) -> Dict[str, Any]:
    """
    Load JSON file as dictionary.
    
    Args:
        filepath: Path to JSON file
    
    Returns:
        Loaded dictionary
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_directory(path: Path) -> None:
    """
    Create directory if it doesn't exist.
    
    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.utcnow().isoformat() + 'Z'


class MLflowLogger:
    """
    Wrapper for MLflow logging operations.
    
    Simplifies experiment tracking for notebook-based development.
    """
    
    def __init__(self, tracking_uri: Optional[str] = None):
        """
        Initialize MLflow logger.
        
        Args:
            tracking_uri: MLflow tracking server URI (default: from env)
        """
        self.tracking_uri = tracking_uri
        self._mlflow = None
    
    @property
    def mlflow(self):
        """Lazy import MLflow to avoid import errors if not installed."""
        if self._mlflow is None:
            import mlflow
            self._mlflow = mlflow
            if self.tracking_uri:
                mlflow.set_tracking_uri(self.tracking_uri)
        return self._mlflow
    
    def start_run(self, run_name: str, experiment_name: str = "loan-underwriting"):
        """
        Start MLflow run.
        
        Args:
            run_name: Name for this run
            experiment_name: Experiment name (default: loan-underwriting)
        
        Returns:
            MLflow run context manager
        """
        self.mlflow.set_experiment(experiment_name)
        return self.mlflow.start_run(run_name=run_name)
    
    def log_params(self, params: Dict[str, Any]) -> None:
        """Log parameters to current run."""
        for key, value in params.items():
            self.mlflow.log_param(key, value)
    
    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """Log metrics to current run."""
        for key, value in metrics.items():
            self.mlflow.log_metric(key, value)
    
    def log_artifact(self, filepath: Path) -> None:
        """Log file artifact to current run."""
        self.mlflow.log_artifact(str(filepath))
    
    def log_dict(self, data: Dict[str, Any], filename: str) -> None:
        """
        Log dictionary as JSON artifact.
        
        Args:
            data: Dictionary to log
            filename: Artifact filename
        """
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f, indent=2, default=str)
            temp_path = f.name
        
        self.mlflow.log_artifact(temp_path, artifact_path=filename)
        Path(temp_path).unlink()


class DocumentAnalyzer:
    """
    Analyze Document Intelligence extraction patterns.
    
    Helps identify document types and extraction quality metrics
    for continuous improvement.
    """
    
    def __init__(self):
        self.extraction_log = []
    
    def record_extraction(
        self,
        document_type: str,
        confidence_score: float,
        extraction_method: str = "document_intelligence"
    ) -> None:
        """
        Record an extraction event.
        
        Args:
            document_type: Type of document (pay_stub, bank_statement, etc.)
            confidence_score: Extraction confidence score
            extraction_method: Method used (default: document_intelligence)
        """
        self.extraction_log.append({
            'document_type': document_type,
            'confidence_score': confidence_score,
            'extraction_method': extraction_method,
            'timestamp': get_timestamp()
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Analyze extraction statistics.
        
        Returns:
            Dictionary with extraction statistics by document type
        """
        if not self.extraction_log:
            return {}
        
        stats = {}
        for entry in self.extraction_log:
            doc_type = entry['document_type']
            if doc_type not in stats:
                stats[doc_type] = {
                    'count': 0,
                    'avg_confidence': 0.0,
                    'min_confidence': 1.0,
                    'max_confidence': 0.0
                }
            
            stats[doc_type]['count'] += 1
            stats[doc_type]['avg_confidence'] += entry['confidence_score']
            stats[doc_type]['min_confidence'] = min(
                stats[doc_type]['min_confidence'], 
                entry['confidence_score']
            )
            stats[doc_type]['max_confidence'] = max(
                stats[doc_type]['max_confidence'], 
                entry['confidence_score']
            )
        
        # Calculate averages
        for doc_type in stats:
            count = stats[doc_type]['count']
            stats[doc_type]['avg_confidence'] /= count
        
        return stats
