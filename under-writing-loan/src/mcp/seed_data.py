"""
Seed mock credit bureau database with test profiles.

This script populates data/mock_credit_bureau.db with 4 representative
credit profiles for testing the loan underwriting workflow.

Task: T012 - Populate mock_credit_bureau.db with 4 test profiles per quickstart.md

Test Profiles:
1. Excellent Credit (780): Ideal borrower, no issues
2. Good Credit (720): Strong borrower, minor concerns
3. Fair Credit (670): Marginal borrower, some red flags
4. Poor Credit (590): High-risk borrower, multiple issues

Usage:
    python src/mcp/seed_data.py

This will insert 4 test profiles into the credit_reports table.
"""

import sqlite3
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Test profile definitions per quickstart.md
TEST_PROFILES = [
    {
        "ssn": "111-11-1111",
        "name": "Test Excellent",
        "credit_score": 780,
        "credit_utilization": 15.0,
        "accounts_open": 12,
        "derogatory_marks": 0,
        "credit_age_months": 120,  # 10 years
        "payment_history": "excellent",
        "late_payments_12mo": 0,
        "hard_inquiries_12mo": 1,
        "bureau_source": "mock_credit_bureau"
    },
    {
        "ssn": "222-22-2222",
        "name": "Test Good",
        "credit_score": 720,
        "credit_utilization": 28.5,
        "accounts_open": 8,
        "derogatory_marks": 0,
        "credit_age_months": 84,  # 7 years
        "payment_history": "good",
        "late_payments_12mo": 1,
        "hard_inquiries_12mo": 2,
        "bureau_source": "mock_credit_bureau"
    },
    {
        "ssn": "333-33-3333",
        "name": "Test Fair",
        "credit_score": 670,
        "credit_utilization": 45.0,
        "accounts_open": 6,
        "derogatory_marks": 1,  # One collection
        "credit_age_months": 48,  # 4 years
        "payment_history": "fair",
        "late_payments_12mo": 3,
        "hard_inquiries_12mo": 4,
        "bureau_source": "mock_credit_bureau"
    },
    {
        "ssn": "444-44-4444",
        "name": "Test Poor",
        "credit_score": 590,
        "credit_utilization": 85.0,
        "accounts_open": 4,
        "derogatory_marks": 3,  # Multiple collections/charge-offs
        "credit_age_months": 36,  # 3 years
        "payment_history": "poor",
        "late_payments_12mo": 6,
        "hard_inquiries_12mo": 8,
        "bureau_source": "mock_credit_bureau"
    }
]


def seed_database(db_path: Path, reset: bool = False) -> None:
    """
    Seed database with test credit profiles.
    
    Args:
        db_path: Path to SQLite database file
        reset: If True, delete existing records before seeding
    """
    
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        print(f"💡 Run 'python src/mcp/create_credit_db.py' first to create the database")
        sys.exit(1)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='credit_reports'
        """)
        if not cursor.fetchone():
            print(f"❌ Table 'credit_reports' not found in database")
            print(f"💡 Run 'python src/mcp/create_credit_db.py' first to create the schema")
            sys.exit(1)
        
        # Reset if requested
        if reset:
            cursor.execute("DELETE FROM credit_reports")
            conn.commit()
            print(f"✅ Cleared existing credit records")
        
        # Check for existing records
        cursor.execute("SELECT COUNT(*) FROM credit_reports")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0 and not reset:
            print(f"⚠️  Database already contains {existing_count} records")
            response = input("Do you want to keep existing records and add new ones? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Aborted by user")
                sys.exit(0)
        
        # Insert test profiles
        inserted = 0
        skipped = 0
        
        for profile in TEST_PROFILES:
            try:
                cursor.execute("""
                    INSERT INTO credit_reports (
                        ssn, name, credit_score, credit_utilization,
                        accounts_open, derogatory_marks, credit_age_months,
                        payment_history, late_payments_12mo, hard_inquiries_12mo,
                        bureau_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile["ssn"],
                    profile["name"],
                    profile["credit_score"],
                    profile["credit_utilization"],
                    profile["accounts_open"],
                    profile["derogatory_marks"],
                    profile["credit_age_months"],
                    profile["payment_history"],
                    profile["late_payments_12mo"],
                    profile["hard_inquiries_12mo"],
                    profile["bureau_source"]
                ))
                inserted += 1
                print(f"✅ Inserted: {profile['name']} ({profile['ssn']}) - Score: {profile['credit_score']}")
                
            except sqlite3.IntegrityError:
                skipped += 1
                print(f"⚠️  Skipped: {profile['name']} ({profile['ssn']}) - Already exists")
        
        # Commit changes
        conn.commit()
        
        # Display summary
        print(f"\n" + "="*70)
        print(f"SEED DATA SUMMARY")
        print(f"="*70)
        print(f"Inserted: {inserted} profiles")
        print(f"Skipped: {skipped} profiles (already existed)")
        print(f"Total in database: {existing_count + inserted}")
        
        # Verify seeded data
        print(f"\n" + "-"*70)
        print(f"CREDIT PROFILES IN DATABASE")
        print(f"-"*70)
        
        cursor.execute("""
            SELECT ssn, name, credit_score, payment_history, 
                   credit_utilization, late_payments_12mo
            FROM credit_reports
            ORDER BY credit_score DESC
        """)
        
        profiles = cursor.fetchall()
        for ssn, name, score, history, utilization, late_payments in profiles:
            print(f"{name:.<30} {ssn} | Score: {score:>3} | History: {history:>9} | "
                  f"Util: {utilization:>5.1f}% | Late: {late_payments}")
        
        print(f"\n" + "="*70)
        print(f"✅ T012 COMPLETE - Mock credit bureau database seeded successfully")
        print(f"="*70)
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        raise
        
    finally:
        conn.close()


def verify_seed_data(db_path: Path) -> bool:
    """
    Verify test profiles exist in database.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        True if all test profiles exist, False otherwise
    """
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check for test SSNs
        test_ssns = [p["ssn"] for p in TEST_PROFILES]
        placeholders = ','.join('?' * len(test_ssns))
        
        cursor.execute(f"""
            SELECT ssn, name, credit_score 
            FROM credit_reports 
            WHERE ssn IN ({placeholders})
            ORDER BY credit_score DESC
        """, test_ssns)
        
        found_profiles = cursor.fetchall()
        
        if len(found_profiles) == len(TEST_PROFILES):
            print(f"✅ All {len(TEST_PROFILES)} test profiles found in database:")
            for ssn, name, score in found_profiles:
                print(f"   - {name} ({ssn}): Score {score}")
            return True
        else:
            print(f"❌ Expected {len(TEST_PROFILES)} profiles, found {len(found_profiles)}")
            return False
            
    except sqlite3.Error as e:
        print(f"❌ Verification error: {e}")
        return False
        
    finally:
        conn.close()


def main():
    """Main entry point for database seeding."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Seed mock credit bureau database with test profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed database with test profiles
  python src/mcp/seed_data.py
  
  # Reset database and seed (delete existing records)
  python src/mcp/seed_data.py --reset
  
  # Verify test profiles exist
  python src/mcp/seed_data.py --verify-only

Test Profiles:
  1. Test Excellent (111-11-1111): Score 780 - Ideal borrower
  2. Test Good (222-22-2222): Score 720 - Strong borrower
  3. Test Fair (333-33-3333): Score 670 - Marginal borrower  
  4. Test Poor (444-44-4444): Score 590 - High-risk borrower
        """
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Delete existing records before seeding (WARNING: deletes all data)'
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify test profiles exist, do not insert data'
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
    print("MOCK CREDIT BUREAU DATABASE SEEDING")
    print("="*70)
    print(f"\nDatabase Path: {db_path}")
    print(f"Task: T012 - Seed mock credit bureau with 4 test profiles")
    print()
    
    if args.verify_only:
        # Verification mode
        print("Mode: Verification only\n")
        if verify_seed_data(db_path):
            print("\n✅ Test profiles verified successfully")
            sys.exit(0)
        else:
            print("\n❌ Test profiles missing or incomplete")
            sys.exit(1)
    else:
        # Seeding mode
        print(f"Mode: {'Reset and seed' if args.reset else 'Seed (preserve existing)'}\n")
        
        if args.reset:
            response = input(f"⚠️  WARNING: This will delete all existing credit records. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Aborted by user")
                sys.exit(0)
        
        try:
            seed_database(db_path, reset=args.reset)
            
            # Verify after seeding
            print("\nVerifying seeded data...")
            if verify_seed_data(db_path):
                print("\n💡 Next Step: Start MCP server with 'uvicorn src.mcp.server:app --reload'")
                sys.exit(0)
            else:
                print("\n❌ Verification failed after seeding")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Failed to seed database: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
