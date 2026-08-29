"""
Create mock credit bureau database schema.

This script initializes the SQLite database used by the MCP server
to simulate credit bureau data retrieval.

Task: T011 - Create data/mock_credit_bureau.db schema per contracts/mcp-server.yaml

Database Schema:
- Table: credit_reports
- Purpose: Store mock credit profiles for testing loan underwriting workflow
- Access: MCP server endpoint GET /credit/{ssn}

Usage:
    python src/mcp/create_credit_db.py

This will create/reset the database at data/mock_credit_bureau.db
"""

import sqlite3
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def create_database(db_path: Path, reset: bool = False) -> None:
    """
    Create mock credit bureau database with schema.
    
    Args:
        db_path: Path to SQLite database file
        reset: If True, drop existing tables before creating
        
    Schema matches mcp-server.yaml CreditReport schema and data-model.md
    """
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to database (creates file if doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Drop existing table if reset requested
        if reset:
            cursor.execute("DROP TABLE IF EXISTS credit_reports")
            print(f"✅ Dropped existing credit_reports table")
        
        # Create credit_reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_reports (
                ssn TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                credit_score INTEGER NOT NULL CHECK(credit_score BETWEEN 300 AND 850),
                credit_utilization REAL NOT NULL CHECK(credit_utilization BETWEEN 0.0 AND 100.0),
                accounts_open INTEGER NOT NULL CHECK(accounts_open >= 0),
                derogatory_marks INTEGER NOT NULL CHECK(derogatory_marks >= 0),
                credit_age_months INTEGER NOT NULL CHECK(credit_age_months >= 0),
                payment_history TEXT NOT NULL CHECK(payment_history IN ('excellent', 'good', 'fair', 'poor')),
                late_payments_12mo INTEGER DEFAULT 0 CHECK(late_payments_12mo >= 0),
                hard_inquiries_12mo INTEGER DEFAULT 0 CHECK(hard_inquiries_12mo >= 0),
                bureau_source TEXT DEFAULT 'mock_credit_bureau',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on SSN for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_credit_reports_ssn 
            ON credit_reports(ssn)
        """)
        
        # Create index on credit score for analytics
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_credit_reports_score 
            ON credit_reports(credit_score)
        """)
        
        # Commit changes
        conn.commit()
        
        print(f"✅ Created credit_reports table at {db_path}")
        print(f"\nTable Schema:")
        print(f"  - ssn (TEXT PRIMARY KEY): Social Security Number (XXX-XX-XXXX)")
        print(f"  - name (TEXT): Applicant full name")
        print(f"  - credit_score (INTEGER 300-850): FICO score")
        print(f"  - credit_utilization (REAL 0.0-100.0): % of available credit used")
        print(f"  - accounts_open (INTEGER ≥0): Number of active credit accounts")
        print(f"  - derogatory_marks (INTEGER ≥0): Collections, bankruptcies, etc.")
        print(f"  - credit_age_months (INTEGER ≥0): Age of oldest account")
        print(f"  - payment_history (TEXT): excellent|good|fair|poor")
        print(f"  - late_payments_12mo (INTEGER ≥0): Late payments in last 12 months")
        print(f"  - hard_inquiries_12mo (INTEGER ≥0): Hard credit pulls in last year")
        print(f"  - bureau_source (TEXT): Data source identifier")
        print(f"  - created_at (TIMESTAMP): Record creation timestamp")
        print(f"  - updated_at (TIMESTAMP): Record update timestamp")
        
        # Verify table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='credit_reports'
        """)
        result = cursor.fetchone()
        
        if result:
            # Get row count
            cursor.execute("SELECT COUNT(*) FROM credit_reports")
            count = cursor.fetchone()[0]
            print(f"\n✅ Verification: Table exists with {count} records")
            print(f"\n💡 Next Step: Run 'python src/mcp/seed_data.py' to populate with test profiles")
        else:
            print(f"\n❌ Verification failed: Table not found")
            
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        raise
        
    finally:
        conn.close()


def verify_schema(db_path: Path) -> bool:
    """
    Verify database schema is correct.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        True if schema is valid, False otherwise
    """
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='credit_reports'
        """)
        if not cursor.fetchone():
            print(f"❌ Table 'credit_reports' not found")
            return False
        
        # Check schema columns
        cursor.execute("PRAGMA table_info(credit_reports)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required_columns = [
            'ssn', 'name', 'credit_score', 'credit_utilization',
            'accounts_open', 'derogatory_marks', 'credit_age_months',
            'payment_history', 'late_payments_12mo', 'hard_inquiries_12mo',
            'bureau_source', 'created_at', 'updated_at'
        ]
        
        missing_columns = set(required_columns) - set(column_names)
        if missing_columns:
            print(f"❌ Missing columns: {missing_columns}")
            return False
        
        print(f"✅ Schema verification passed")
        print(f"   Columns: {', '.join(column_names)}")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Verification error: {e}")
        return False
        
    finally:
        conn.close()


def main():
    """Main entry point for database creation."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create mock credit bureau database schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create database (preserves existing data)
  python src/mcp/create_credit_db.py
  
  # Reset database (drops existing data)
  python src/mcp/create_credit_db.py --reset
  
  # Verify schema only
  python src/mcp/create_credit_db.py --verify-only
        """
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Drop existing table before creating (WARNING: deletes all data)'
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify schema, do not create/modify database'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/mock_credit_bureau.db',
        help='Path to database file (default: data/mock_credit_bureau.db)'
    )
    
    args = parser.parse_args()
    
    # Resolve database path
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    
    print("="*70)
    print("MOCK CREDIT BUREAU DATABASE SETUP")
    print("="*70)
    print(f"\nDatabase Path: {db_path}")
    print(f"Task: T011 - Create mock credit bureau database schema")
    print()
    
    if args.verify_only:
        # Verification mode
        print("Mode: Verification only\n")
        if verify_schema(db_path):
            print("\n✅ Database schema is valid")
            sys.exit(0)
        else:
            print("\n❌ Database schema is invalid or missing")
            sys.exit(1)
    else:
        # Creation mode
        print(f"Mode: {'Reset and create' if args.reset else 'Create (preserve data)'}\n")
        
        if args.reset and db_path.exists():
            response = input(f"⚠️  WARNING: This will delete all data in {db_path}. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Aborted by user")
                sys.exit(0)
        
        try:
            create_database(db_path, reset=args.reset)
            
            # Verify after creation
            print("\nVerifying schema...")
            if verify_schema(db_path):
                print("\n" + "="*70)
                print("✅ T011 COMPLETE - Mock credit bureau database created successfully")
                print("="*70)
                sys.exit(0)
            else:
                print("\n❌ Schema verification failed after creation")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Failed to create database: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
