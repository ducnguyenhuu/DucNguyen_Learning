"""
Create application metadata database for workflow state tracking.

This script creates data/database.db with the applications table for
persisting loan application metadata throughout the multi-agent workflow.

Task: T013 - Create database.db for application metadata per plan.md

Purpose:
- Track application status through workflow stages
- Record agent completion flags (document, risk, compliance, decision)
- Store MLflow run IDs for experiment tracking
- Persist processing metrics (time, cost)
- Log errors encountered during processing

The schema follows the ApplicationMetadata contract from mcp-server.yaml.

Usage:
    python src/mcp/create_app_db.py
    
This will create the database at data/database.sqlite with proper schema.
"""

import sqlite3
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def create_database(db_path: Path, reset: bool = False) -> None:
    """
    Create application metadata database with applications table.
    
    Args:
        db_path: Path to SQLite database file
        reset: If True, drop existing tables before creating
        
    Schema aligns with ApplicationMetadata in contracts/mcp-server.yaml:
    - application_id: Primary key, format APP-YYYY-NNN
    - status: Enum (pending, processing, completed, failed)
    - created_at, updated_at: ISO 8601 timestamps
    - Completion flags: document, risk, compliance, decision
    - final_decision: Enum (approved, conditional_approval, denied, refer_to_manual)
    - mlflow_run_id: Experiment tracking reference
    - Processing metrics: time, cost
    - error_messages: JSON array of error strings
    """
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Drop table if reset requested
        if reset:
            cursor.execute("DROP TABLE IF EXISTS applications")
            print(f"✅ Dropped existing applications table")
        
        # Create applications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                application_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                document_extraction_complete INTEGER NOT NULL DEFAULT 0,
                risk_assessment_complete INTEGER NOT NULL DEFAULT 0,
                compliance_check_complete INTEGER NOT NULL DEFAULT 0,
                decision_complete INTEGER NOT NULL DEFAULT 0,
                final_decision TEXT CHECK(final_decision IN ('approved', 'conditional_approval', 'denied', 'refer_to_manual')),
                mlflow_run_id TEXT,
                total_processing_time_seconds REAL,
                total_cost_usd REAL,
                error_messages TEXT DEFAULT '[]'
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_status 
            ON applications(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_created_at 
            ON applications(created_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_mlflow_run_id 
            ON applications(mlflow_run_id)
        """)
        
        # Commit changes
        conn.commit()
        
        print(f"\n" + "="*70)
        print(f"DATABASE CREATION SUCCESS")
        print(f"="*70)
        print(f"✅ Created applications table at {db_path}")
        print(f"\nTable: applications")
        print(f"  Columns: 13 (application_id, status, timestamps, flags, metrics)")
        print(f"  Constraints: ")
        print(f"    - application_id: PRIMARY KEY")
        print(f"    - status: CHECK (pending|processing|completed|failed)")
        print(f"    - final_decision: CHECK (approved|conditional_approval|denied|refer_to_manual)")
        print(f"  Indexes: ")
        print(f"    - idx_applications_status (for filtering by status)")
        print(f"    - idx_applications_created_at (for chronological queries)")
        print(f"    - idx_applications_mlflow_run_id (for experiment tracking)")
        
        # Verify table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='applications'
        """)
        
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM applications")
            count = cursor.fetchone()[0]
            print(f"\n✅ Verification: Table exists with {count} records")
            print(f"\n💡 Next Step: Applications will be tracked via MCP /application endpoints")
            print(f"="*70)
            print(f"✅ T013 COMPLETE - Application metadata database created successfully")
            print(f"="*70)
        else:
            print(f"❌ Verification failed: Table not found")
            sys.exit(1)
            
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        raise
        
    finally:
        conn.close()


def verify_schema(db_path: Path) -> bool:
    """
    Verify applications table schema matches specification.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        True if schema is correct, False otherwise
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
            WHERE type='table' AND name='applications'
        """)
        
        if not cursor.fetchone():
            print(f"❌ Table 'applications' not found")
            return False
        
        # Get table info
        cursor.execute("PRAGMA table_info(applications)")
        columns = cursor.fetchall()
        
        # Expected columns per mcp-server.yaml
        expected_columns = {
            'application_id': 'TEXT',
            'status': 'TEXT',
            'created_at': 'TEXT',
            'updated_at': 'TEXT',
            'document_extraction_complete': 'INTEGER',
            'risk_assessment_complete': 'INTEGER',
            'compliance_check_complete': 'INTEGER',
            'decision_complete': 'INTEGER',
            'final_decision': 'TEXT',
            'mlflow_run_id': 'TEXT',
            'total_processing_time_seconds': 'REAL',
            'total_cost_usd': 'REAL',
            'error_messages': 'TEXT'
        }
        
        # Validate columns
        found_columns = {col[1]: col[2] for col in columns}
        
        print(f"\n" + "="*70)
        print(f"SCHEMA VERIFICATION")
        print(f"="*70)
        
        all_valid = True
        for col_name, col_type in expected_columns.items():
            if col_name not in found_columns:
                print(f"❌ Missing column: {col_name}")
                all_valid = False
            elif not found_columns[col_name].startswith(col_type):
                print(f"⚠️  Column {col_name}: expected {col_type}, found {found_columns[col_name]}")
            else:
                print(f"✅ Column {col_name}: {found_columns[col_name]}")
        
        # Check indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='applications'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        print(f"\nIndexes:")
        expected_indexes = ['idx_applications_status', 'idx_applications_created_at', 'idx_applications_mlflow_run_id']
        for idx in expected_indexes:
            if idx in indexes:
                print(f"✅ Index: {idx}")
            else:
                print(f"⚠️  Missing index: {idx}")
        
        print(f"="*70)
        
        if all_valid:
            print(f"✅ Schema verification passed")
            return True
        else:
            print(f"❌ Schema verification failed")
            return False
            
    except sqlite3.Error as e:
        print(f"❌ Verification error: {e}")
        return False
        
    finally:
        conn.close()


def main():
    """Main entry point for database creation."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create application metadata database for workflow tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create database with applications table
  python src/mcp/create_app_db.py
  
  # Reset database (drop existing tables)
  python src/mcp/create_app_db.py --reset
  
  # Verify schema without modifying
  python src/mcp/create_app_db.py --verify-only

Database Purpose:
  Tracks loan application workflow state through multi-agent processing:
  - Document Agent → risk_assessment_complete flag
  - Risk Agent → compliance_check_complete flag  
  - Compliance Agent → decision_complete flag
  - Decision Agent → final_decision stored
  
  Enables MCP server /application/{id} endpoint to query progress.
        """
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Drop existing tables before creating (WARNING: deletes all data)'
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify schema, do not create or modify'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/database.db',
        help='Path to database file (default: data/database.db)'
    )
    
    args = parser.parse_args()
    
    # Resolve database path
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    
    print("="*70)
    print("APPLICATION METADATA DATABASE CREATION")
    print("="*70)
    print(f"\nDatabase Path: {db_path}")
    print(f"Task: T013 - Create database.sqlite for application tracking")
    print()
    
    if args.verify_only:
        # Verification mode
        print("Mode: Verification only\n")
        if verify_schema(db_path):
            print("\n✅ Schema verified successfully")
            sys.exit(0)
        else:
            print("\n❌ Schema verification failed")
            sys.exit(1)
    else:
        # Creation mode
        print(f"Mode: {'Reset and create' if args.reset else 'Create (preserve existing)'}\n")
        
        if args.reset and db_path.exists():
            response = input(f"⚠️  WARNING: This will delete all application metadata. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Aborted by user")
                sys.exit(0)
        
        try:
            create_database(db_path, reset=args.reset)
            
            # Verify after creation
            print("\nVerifying schema...")
            if verify_schema(db_path):
                print("\n💡 Next Step: Orchestrator will persist workflow state via /application PUT endpoint")
                sys.exit(0)
            else:
                print("\n❌ Verification failed after creation")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Failed to create database: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
