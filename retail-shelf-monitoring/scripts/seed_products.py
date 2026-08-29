"""
Seed Product Catalog with Realistic Retail Products

This script populates the database with 10 realistic retail products across 3 categories.
Provides reference data for all 4 ML challenges:
- Challenge 1: Out-of-Stock Detection
- Challenge 2: Product Recognition  
- Challenge 3: Stock Estimation
- Challenge 4: Price Verification

Usage:
    python scripts/seed_products.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shelf_monitor.database.crud import (
    create_category,
    create_product,
    get_categories,
    get_category_by_name,
    get_products,
)
from src.shelf_monitor.database.session import SessionLocal


def seed_database():
    """Seed categories and products into database."""
    db = SessionLocal()
    
    try:
        print("=" * 70)
        print("Product Catalog Seeding")
        print("=" * 70)
        print()
        
        # Step 1: Create Categories
        print("Step 1: Creating categories...")
        categories_data = [
            {
                "name": "Beverages",
                "description": "Soft drinks, juices, and bottled water"
            },
            {
                "name": "Snacks",
                "description": "Chips, cookies, crackers, and packaged snacks"
            },
            {
                "name": "Household",
                "description": "Cleaning supplies and household essentials"
            }
        ]
        
        categories = {}
        for cat_data in categories_data:
            # Check if category already exists
            existing = get_category_by_name(db, cat_data["name"])
            if existing:
                print(f"  ⚠️  Category '{cat_data['name']}' already exists (ID: {existing.id})")
                categories[cat_data["name"]] = existing
            else:
                category = create_category(
                    db,
                    name=cat_data["name"],
                    description=cat_data["description"]
                )
                categories[cat_data["name"]] = category
                print(f"  ✅ Created category: {category.name} (ID: {category.id})")
        
        print()
        
        # Step 2: Create Products
        print("Step 2: Creating products...")
        products_data = [
            # Beverages (4 products)
            {
                "sku": "BEV-COKE-330",
                "name": "Coca-Cola 330ml",
                "category": "Beverages",
                "expected_price": 1.99,
                "barcode": "5449000000996"
            },
            {
                "sku": "BEV-PEPSI-330",
                "name": "Pepsi 330ml",
                "category": "Beverages",
                "expected_price": 1.89,
                "barcode": "012000001659"
            },
            {
                "sku": "BEV-SPRITE-330",
                "name": "Sprite 330ml",
                "category": "Beverages",
                "expected_price": 1.79,
                "barcode": "5449000017888"
            },
            {
                "sku": "BEV-WATER-500",
                "name": "Bottled Water 500ml",
                "category": "Beverages",
                "expected_price": 0.99,
                "barcode": "074780021579"
            },
            
            # Snacks (4 products)
            {
                "sku": "SNK-LAYS-REG",
                "name": "Lay's Classic Chips 40g",
                "category": "Snacks",
                "expected_price": 2.49,
                "barcode": "028400000000"
            },
            {
                "sku": "SNK-OREO-154",
                "name": "Oreo Cookies 154g",
                "category": "Snacks",
                "expected_price": 3.49,
                "barcode": "044000012809"
            },
            {
                "sku": "SNK-PRINGLES",
                "name": "Pringles Original 165g",
                "category": "Snacks",
                "expected_price": 3.99,
                "barcode": "038000845604"
            },
            {
                "sku": "SNK-KITKAY-45",
                "name": "KitKat 4-Finger 45g",
                "category": "Snacks",
                "expected_price": 1.29,
                "barcode": "5000159459228"
            },
            
            # Household (2 products)
            {
                "sku": "HSE-TIDE-1L",
                "name": "Tide Liquid Detergent 1L",
                "category": "Household",
                "expected_price": 12.99,
                "barcode": "037000037064"
            },
            {
                "sku": "HSE-PAPER-6",
                "name": "Toilet Paper 6-pack",
                "category": "Household",
                "expected_price": 8.49,
                "barcode": "073010001275"
            }
        ]
        
        created_count = 0
        skipped_count = 0
        
        for prod_data in products_data:
            try:
                product = create_product(
                    db,
                    sku=prod_data["sku"],
                    name=prod_data["name"],
                    category_id=categories[prod_data["category"]].id,
                    expected_price=prod_data["expected_price"],
                    barcode=prod_data["barcode"]
                )
                print(f"  ✅ Created: {product.name} (SKU: {product.sku}, ${product.expected_price:.2f})")
                created_count += 1
            except ValueError as e:
                print(f"  ⚠️  Skipped: {prod_data['name']} - {str(e)}")
                skipped_count += 1
        
        print()
        print("=" * 70)
        print("Seeding Summary")
        print("=" * 70)
        
        # Verify database state
        all_categories = get_categories(db, limit=100)
        all_products = get_products(db, limit=100)
        
        print(f"Categories in database: {len(all_categories)}")
        for cat in all_categories:
            product_count = len(cat.products)
            print(f"  - {cat.name}: {product_count} products")
        
        print()
        print(f"Products in database: {len(all_products)}")
        print(f"  Created: {created_count}")
        print(f"  Skipped: {skipped_count}")
        
        print()
        print("✅ Product catalog seeding complete!")
        print()
        print("Next Steps:")
        print("  - T019-T024: Set up FastAPI application")
        print("  - T028: Label subset of images with these 10 products")
        print("  - T050: Train YOLO model with custom classes")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
