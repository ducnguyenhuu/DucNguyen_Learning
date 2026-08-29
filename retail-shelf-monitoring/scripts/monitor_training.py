"""
Monitor YOLO training progress.

This script checks the training progress and displays key metrics
from the latest training run.

Usage:
    python scripts/monitor_training.py
    
    # Watch mode (updates every 10 seconds)
    watch -n 10 python scripts/monitor_training.py
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime


def find_latest_training_run(project_dir: str = "runs/detect") -> Path:
    """Find the latest training run directory."""
    project_path = Path(project_dir)
    
    if not project_path.exists():
        return None
    
    # Find all train directories
    train_dirs = list(project_path.glob("train*"))
    if not train_dirs:
        return None
    
    # Sort by modification time and get latest
    latest = max(train_dirs, key=lambda p: p.stat().st_mtime)
    return latest


def display_training_progress(run_dir: Path):
    """Display training progress from results.csv."""
    results_csv = run_dir / "results.csv"
    
    if not results_csv.exists():
        print(f"⏳ Training started but no results yet...")
        print(f"   Run directory: {run_dir}")
        return
    
    # Read results
    try:
        df = pd.read_csv(results_csv)
        df.columns = df.columns.str.strip()  # Remove whitespace from column names
        
        total_epochs = len(df)
        latest = df.iloc[-1]
        
        print("="*70)
        print(f"YOLO Training Progress - {run_dir.name}")
        print("="*70)
        print(f"Run directory: {run_dir}")
        print()
        
        # Training progress
        print(f"📊 Progress: Epoch {total_epochs}/50 ({total_epochs/50*100:.1f}%)")
        print()
        
        # Latest metrics
        print("Latest Metrics (Epoch {}):".format(total_epochs))
        
        # Box loss (lower is better)
        if 'train/box_loss' in df.columns:
            print(f"  Train Loss:")
            print(f"    Box: {latest.get('train/box_loss', 0):.4f}")
            print(f"    Cls: {latest.get('train/cls_loss', 0):.4f}")
            print(f"    DFL: {latest.get('train/dfl_loss', 0):.4f}")
        
        # Validation metrics (higher is better)
        if 'metrics/precision(B)' in df.columns:
            print(f"  Validation Metrics:")
            print(f"    Precision: {latest.get('metrics/precision(B)', 0):.3f}")
            print(f"    Recall:    {latest.get('metrics/recall(B)', 0):.3f}")
            print(f"    mAP@0.5:   {latest.get('metrics/mAP50(B)', 0):.3f}")
            print(f"    mAP@0.5:0.95: {latest.get('metrics/mAP50-95(B)', 0):.3f}")
        
        print()
        
        # Best metrics so far
        if 'metrics/mAP50(B)' in df.columns:
            best_map50 = df['metrics/mAP50(B)'].max()
            best_epoch = df['metrics/mAP50(B)'].idxmax() + 1
            
            print(f"🏆 Best mAP@0.5: {best_map50:.3f} (Epoch {best_epoch})")
        
        # Training time estimate
        if 'time' in df.columns and total_epochs > 0:
            avg_time_per_epoch = df['time'].mean()
            remaining_epochs = 50 - total_epochs
            estimated_time_remaining = avg_time_per_epoch * remaining_epochs
            
            hours = int(estimated_time_remaining // 3600)
            minutes = int((estimated_time_remaining % 3600) // 60)
            
            print(f"⏱️  Estimated time remaining: {hours}h {minutes}m")
        
        print()
        
        # Check if training is complete
        if total_epochs >= 50:
            print("="*70)
            print("✅ TRAINING COMPLETE!")
            print("="*70)
            print()
            print("Next steps:")
            print("  1. Check best model: runs/detect/train/weights/best.pt")
            print("  2. Run evaluation: python scripts/evaluate_yolo.py")
            print("  3. Copy to models: cp runs/detect/train/weights/best.pt models/yolo_sku110k_best.pt")
        
    except Exception as e:
        print(f"❌ Error reading results: {str(e)}")
        return


def main():
    """Main function."""
    print()
    
    # Find latest training run
    run_dir = find_latest_training_run()
    
    if run_dir is None:
        print("❌ No training runs found in runs/detect/")
        print("   Start training with: python scripts/train_yolo.py")
        sys.exit(1)
    
    # Display progress
    display_training_progress(run_dir)
    
    print()
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    main()
