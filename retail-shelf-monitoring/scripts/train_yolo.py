"""
Train YOLOv8 model on SKU-110K dataset.

This script trains a YOLOv8s model for product detection on retail shelf images.
The model learns to detect products as a single "object" class, which is then
used for gap detection (out-of-stock analysis).

Usage:
    # Train with default settings (50 epochs, batch size 16)
    python scripts/train_yolo.py
    
    # Custom configuration
    python scripts/train_yolo.py --epochs 100 --batch 32 --model yolov8m
    
    # Resume from checkpoint
    python scripts/train_yolo.py --resume runs/detect/train/weights/last.pt

Related Tasks:
    - T028: Train YOLOv8s model on SKU-110K
    - T029: Evaluate model on test set
    - T030: Save best checkpoint to models/

Output:
    - Training runs saved to: runs/detect/train/
    - Best model: runs/detect/train/weights/best.pt
    - Metrics: runs/detect/train/results.csv
"""

import argparse
from pathlib import Path
import sys
from datetime import datetime

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ Error: ultralytics package not found")
    print("   Install it with: pip install ultralytics")
    sys.exit(1)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 model on SKU-110K dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Model configuration
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8s.pt",
        choices=["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"],
        help="YOLOv8 model size (n=nano, s=small, m=medium, l=large, x=xlarge)"
    )
    
    # Training hyperparameters
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs"
    )
    
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Batch size (reduce if out of memory)"
    )
    
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Image size for training (must be multiple of 32)"
    )
    
    parser.add_argument(
        "--patience",
        type=int,
        default=10,
        help="Early stopping patience (epochs without improvement)"
    )
    
    # Dataset
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/SKU110K_yolo/data.yaml",
        help="Path to dataset YAML configuration"
    )
    
    # Device configuration
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Device to use (e.g., '0' for GPU, 'cpu', 'mps'). Empty = auto-detect"
    )
    
    # Training options
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume training from checkpoint path"
    )
    
    parser.add_argument(
        "--project",
        type=str,
        default="runs/detect",
        help="Project directory for saving results"
    )
    
    parser.add_argument(
        "--name",
        type=str,
        default="train",
        help="Experiment name"
    )
    
    parser.add_argument(
        "--exist-ok",
        action="store_true",
        help="Allow overwriting existing experiment"
    )
    
    parser.add_argument(
        "--pretrained",
        action="store_true",
        default=True,
        help="Use pretrained weights (recommended)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of worker threads for data loading"
    )
    
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Cache images in RAM for faster training (requires ~8GB RAM)"
    )
    
    return parser.parse_args()


def validate_dataset(data_yaml: Path) -> bool:
    """
    Validate that dataset exists and is properly formatted.
    
    Args:
        data_yaml: Path to YOLO dataset configuration file
        
    Returns:
        True if valid, False otherwise
    """
    if not data_yaml.exists():
        print(f"❌ Error: Dataset configuration not found: {data_yaml}")
        print("   Run data preprocessing first:")
        print("   python scripts/prepare_data.py")
        return False
    
    # Check if train/val/test directories exist
    import yaml
    with open(data_yaml, 'r') as f:
        config = yaml.safe_load(f)
    
    dataset_path = Path(config['path'])
    required_splits = ['train', 'val', 'test']
    
    for split in required_splits:
        split_path = dataset_path / config[split]
        if not split_path.exists():
            print(f"❌ Error: Dataset split not found: {split_path}")
            return False
    
    print(f"✅ Dataset validated: {data_yaml}")
    print(f"   Path: {dataset_path}")
    print(f"   Classes: {config['nc']} ({', '.join(config['names'])})")
    
    return True


def main():
    """Main training function."""
    args = parse_args()
    
    print("="*70)
    print("YOLOv8 Training - SKU-110K Product Detection")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Validate dataset
    data_yaml = Path(args.data)
    if not validate_dataset(data_yaml):
        sys.exit(1)
    
    print()
    print("Training Configuration:")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Batch size: {args.batch}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Device: {args.device or 'auto-detect'}")
    print(f"  Workers: {args.workers}")
    print(f"  Patience: {args.patience} epochs")
    print(f"  Cache: {'Yes' if args.cache else 'No'}")
    print()
    
    # Load model
    if args.resume:
        print(f"📦 Resuming from checkpoint: {args.resume}")
        model = YOLO(args.resume)
    else:
        print(f"📦 Loading model: {args.model}")
        model = YOLO(args.model)
    
    print("🚀 Starting training...")
    print("   (Training progress will be displayed by YOLO)")
    print()
    
    # Train model
    try:
        results = model.train(
            data=str(data_yaml),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            patience=args.patience,
            project=args.project,
            name=args.name,
            exist_ok=args.exist_ok,
            pretrained=args.pretrained,
            workers=args.workers,
            cache=args.cache,
            # Additional optimization settings
            optimizer='AdamW',  # Better than SGD for most cases
            lr0=0.01,           # Initial learning rate
            lrf=0.01,           # Final learning rate (lr0 * lrf)
            momentum=0.937,     # SGD momentum/Adam beta1
            weight_decay=0.0005, # Optimizer weight decay
            warmup_epochs=3.0,  # Warmup epochs
            warmup_momentum=0.8, # Warmup initial momentum
            save=True,          # Save checkpoints
            save_period=10,     # Save checkpoint every N epochs
            val=True,           # Validate during training
            plots=True,         # Save training plots
            verbose=True        # Verbose output
        )
        
        print()
        print("="*70)
        print("✅ Training Complete!")
        print("="*70)
        
        # Get training directory
        train_dir = Path(args.project) / args.name
        weights_dir = train_dir / "weights"
        
        print()
        print("Results:")
        print(f"  Training directory: {train_dir}")
        print(f"  Best model: {weights_dir / 'best.pt'}")
        print(f"  Last model: {weights_dir / 'last.pt'}")
        print(f"  Metrics: {train_dir / 'results.csv'}")
        print(f"  Plots: {train_dir}/*.png")
        
        # Display key metrics
        if hasattr(results, 'results_dict'):
            metrics = results.results_dict
            print()
            print("Final Metrics:")
            print(f"  Precision: {metrics.get('metrics/precision(B)', 0):.3f}")
            print(f"  Recall: {metrics.get('metrics/recall(B)', 0):.3f}")
            print(f"  mAP@0.5: {metrics.get('metrics/mAP50(B)', 0):.3f}")
            print(f"  mAP@0.5:0.95: {metrics.get('metrics/mAP50-95(B)', 0):.3f}")
        
        print()
        print("Next Steps:")
        print("  1. Evaluate model: python scripts/evaluate_yolo.py")
        print(f"  2. Copy best model: cp {weights_dir / 'best.pt'} models/yolo_sku110k_best.pt")
        print("  3. Test inference: python scripts/test_inference.py")
        print()
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Training interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ Error during training: {str(e)}")
        print()
        print("Common issues:")
        print("  - Out of memory: Reduce --batch size (try 8 or 4)")
        print("  - CUDA error: Check GPU drivers and CUDA installation")
        print("  - Dataset error: Verify data.yaml paths are correct")
        sys.exit(1)


if __name__ == "__main__":
    main()
