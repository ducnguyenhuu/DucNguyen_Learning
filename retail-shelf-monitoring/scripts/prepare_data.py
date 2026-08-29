"""
Preprocess SKU-110K dataset and convert to YOLO format.

This script:
1. Reads CSV annotations from SKU-110K
2. Converts bounding boxes to YOLO format (normalized coordinates)
3. Creates 70/15/15 train/val/test split
4. Generates data.yaml for YOLO training

Usage:
    python scripts/prepare_data.py
"""

import csv
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
from collections import defaultdict


class SKU110KToYOLO:
    """Convert SKU-110K dataset to YOLO format."""
    
    def __init__(
        self,
        raw_dir: Path,
        output_dir: Path,
        train_split: float = 0.70,
        val_split: float = 0.15,
        test_split: float = 0.15
    ):
        """
        Initialize the converter.
        
        Args:
            raw_dir: Path to SKU110K_fixed directory
            output_dir: Path to output YOLO dataset
            train_split: Training set proportion (default: 0.70)
            val_split: Validation set proportion (default: 0.15)
            test_split: Test set proportion (default: 0.15)
        """
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.images_dir = self.raw_dir / "images"
        self.annotations_dir = self.raw_dir / "annotations"
        
        # Validate splits
        assert abs(train_split + val_split + test_split - 1.0) < 0.01, \
            "Splits must sum to 1.0"
        
        self.splits = {
            'train': train_split,
            'val': val_split,
            'test': test_split
        }
        
        # Class mapping (SKU-110K only has 'object' class)
        self.class_names = ['object']
        self.class_to_id = {'object': 0}
        
    def convert_bbox_to_yolo(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        img_width: int,
        img_height: int
    ) -> Tuple[float, float, float, float]:
        """
        Convert absolute bbox coordinates to YOLO format.
        
        YOLO format: x_center y_center width height (all normalized 0-1)
        
        Args:
            x1, y1: Top-left corner (absolute pixels)
            x2, y2: Bottom-right corner (absolute pixels)
            img_width: Image width in pixels
            img_height: Image height in pixels
            
        Returns:
            Tuple of (x_center, y_center, width, height) normalized to 0-1
        """
        # Calculate center and dimensions
        width = x2 - x1
        height = y2 - y1
        x_center = x1 + width / 2
        y_center = y1 + height / 2
        
        # Normalize to 0-1
        x_center_norm = x_center / img_width
        y_center_norm = y_center / img_height
        width_norm = width / img_width
        height_norm = height / img_height
        
        # Clip to valid range
        x_center_norm = max(0.0, min(1.0, x_center_norm))
        y_center_norm = max(0.0, min(1.0, y_center_norm))
        width_norm = max(0.0, min(1.0, width_norm))
        height_norm = max(0.0, min(1.0, height_norm))
        
        return x_center_norm, y_center_norm, width_norm, height_norm
    
    def parse_csv_annotations(self, csv_path: Path) -> Dict[str, List[Dict]]:
        """
        Parse SKU-110K CSV annotations.
        
        CSV format: image_name,x1,y1,x2,y2,class,image_width,image_height
        
        Args:
            csv_path: Path to annotations CSV file
            
        Returns:
            Dictionary mapping image_name to list of annotations
        """
        annotations = defaultdict(list)
        
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) != 8:
                    continue
                    
                image_name, x1, y1, x2, y2, class_name, img_w, img_h = row
                
                annotations[image_name].append({
                    'x1': float(x1),
                    'y1': float(y1),
                    'x2': float(x2),
                    'y2': float(y2),
                    'class': class_name,
                    'img_width': int(img_w),
                    'img_height': int(img_h)
                })
        
        return annotations
    
    def create_yolo_label(
        self,
        annotations: List[Dict],
        output_path: Path
    ):
        """
        Create YOLO format label file.
        
        Args:
            annotations: List of annotation dicts for one image
            output_path: Path to save .txt label file
        """
        with open(output_path, 'w') as f:
            for ann in annotations:
                # Convert to YOLO format
                x_center, y_center, width, height = self.convert_bbox_to_yolo(
                    ann['x1'], ann['y1'], ann['x2'], ann['y2'],
                    ann['img_width'], ann['img_height']
                )
                
                # Get class ID
                class_id = self.class_to_id[ann['class']]
                
                # Write: class_id x_center y_center width height
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} "
                       f"{width:.6f} {height:.6f}\n")
    
    def process_split(self, split_name: str):
        """
        Process one split (train/val/test).
        
        Args:
            split_name: 'train', 'val', or 'test'
        """
        print(f"\n{'='*70}")
        print(f"Processing {split_name} split...")
        print(f"{'='*70}")
        
        # Read annotations
        csv_path = self.annotations_dir / f"annotations_{split_name}.csv"
        if not csv_path.exists():
            print(f"⚠️  Warning: {csv_path} not found, skipping...")
            return
        
        annotations = self.parse_csv_annotations(csv_path)
        print(f"✅ Loaded annotations for {len(annotations)} images")
        
        # Create output directories
        images_out = self.output_dir / "images" / split_name
        labels_out = self.output_dir / "labels" / split_name
        images_out.mkdir(parents=True, exist_ok=True)
        labels_out.mkdir(parents=True, exist_ok=True)
        
        # Process each image
        processed = 0
        skipped = 0
        
        for image_name, image_annotations in annotations.items():
            # Source image path
            src_image = self.images_dir / image_name
            
            if not src_image.exists():
                skipped += 1
                continue
            
            # Destination paths
            dst_image = images_out / image_name
            dst_label = labels_out / image_name.replace('.jpg', '.txt')
            
            # Copy image
            shutil.copy2(src_image, dst_image)
            
            # Create label file
            self.create_yolo_label(image_annotations, dst_label)
            
            processed += 1
            if processed % 500 == 0:
                print(f"   Processed {processed} images...")
        
        print(f"\n✅ {split_name.capitalize()} split complete:")
        print(f"   Processed: {processed} images")
        print(f"   Skipped: {skipped} images (not found)")
    
    def create_data_yaml(self):
        """Create data.yaml configuration for YOLO training."""
        data_config = {
            'path': str(self.output_dir.absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'test': 'images/test',
            'nc': len(self.class_names),
            'names': self.class_names
        }
        
        yaml_path = self.output_dir / "data.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(data_config, f, default_flow_style=False, sort_keys=False)
        
        print(f"\n✅ Created {yaml_path}")
        print(f"\nYOLO Configuration:")
        print(f"   Dataset path: {data_config['path']}")
        print(f"   Classes: {data_config['nc']} ({', '.join(data_config['names'])})")
        print(f"   Splits: train, val, test")
    
    def verify_dataset(self):
        """Verify the converted dataset."""
        print(f"\n{'='*70}")
        print("Dataset Verification")
        print(f"{'='*70}")
        
        for split in ['train', 'val', 'test']:
            images_dir = self.output_dir / "images" / split
            labels_dir = self.output_dir / "labels" / split
            
            if not images_dir.exists():
                continue
            
            image_count = len(list(images_dir.glob("*.jpg")))
            label_count = len(list(labels_dir.glob("*.txt")))
            
            print(f"\n{split.capitalize()}:")
            print(f"   Images: {image_count:,}")
            print(f"   Labels: {label_count:,}")
            
            if image_count != label_count:
                print(f"   ⚠️  Warning: Image count != Label count")
            else:
                print(f"   ✅ Image/Label count matches")
            
            # Sample check
            if image_count > 0:
                sample_image = list(images_dir.glob("*.jpg"))[0]
                sample_label = labels_dir / (sample_image.stem + ".txt")
                
                if sample_label.exists():
                    with open(sample_label, 'r') as f:
                        bbox_count = len(f.readlines())
                    print(f"   Sample: {sample_image.name} has {bbox_count} objects")
    
    def run(self):
        """Run the full conversion pipeline."""
        print("SKU-110K to YOLO Converter")
        print(f"{'='*70}")
        print(f"Source: {self.raw_dir}")
        print(f"Output: {self.output_dir}")
        print(f"Splits: train={self.splits['train']:.0%}, "
              f"val={self.splits['val']:.0%}, "
              f"test={self.splits['test']:.0%}")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each split
        for split in ['train', 'val', 'test']:
            self.process_split(split)
        
        # Create data.yaml
        self.create_data_yaml()
        
        # Verify
        self.verify_dataset()
        
        print(f"\n{'='*70}")
        print("✅ Dataset preparation complete!")
        print(f"{'='*70}")
        print(f"\nYOLO dataset ready at: {self.output_dir}")
        print(f"\nTo train YOLOv8:")
        print(f"  yolo train data={self.output_dir}/data.yaml model=yolov8s.pt epochs=50")


def main():
    """Main entry point."""
    # Paths
    raw_dir = Path("data/raw/SKU110K/SKU110K_fixed")
    output_dir = Path("data/processed/SKU110K_yolo")
    
    # Create converter
    converter = SKU110KToYOLO(
        raw_dir=raw_dir,
        output_dir=output_dir,
        train_split=0.70,
        val_split=0.15,
        test_split=0.15
    )
    
    # Run conversion
    converter.run()


if __name__ == "__main__":
    main()
