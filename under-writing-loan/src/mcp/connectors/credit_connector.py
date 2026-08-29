"""
Credit connector for MCP server - handles credit bureau database queries.

Provides abstracted access to mock credit bureau data stored in SQLite.
In production, this would interface with real credit bureau APIs
(Experian, Equifax, TransUnion).
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import CREDIT_DB

logger = logging.getLogger(__name__)


class CreditConnector:
    """
    Credit bureau database connector for loan underwriting.
    
    Queries mock_credit_bureau.db to retrieve applicant credit reports.
    Abstracts database access and converts rows to CreditReport schema.
    
    Usage:
        connector = CreditConnector()
        report = connector.get_credit_report("123-45-6789")
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize credit connector.
        
        Args:
            db_path: Path to SQLite database (defaults to CREDIT_DB from config)
        """
        self.db_path = db_path or CREDIT_DB
        self.db_path = Path(self.db_path).resolve()
        
        # Validate database exists
        if not self.db_path.exists():
            logger.warning(f"Credit database not found at: {self.db_path}")
            logger.warning("Run src/mcp/seed_data.py to create and populate the database")
        
        logger.info(f"CreditConnector initialized with database: {self.db_path}")
    
    def get_credit_report(self, ssn: str) -> dict:
        """
        Retrieve credit report for given SSN.
        
        Args:
            ssn: Social Security Number in XXX-XX-XXXX format
        
        Returns:
            Dictionary matching CreditReport schema from data-model.md
        
        Raises:
            ValueError: Invalid SSN format
            FileNotFoundError: Database does not exist
            KeyError: No credit record found for SSN
            sqlite3.Error: Database query failed
        
        Examples:
            >>> connector = CreditConnector()
            >>> report = connector.get_credit_report("123-45-6789")
            >>> print(f"Credit Score: {report['credit_score']}")
        """
        # Validate SSN format
        if not self._validate_ssn_format(ssn):
            raise ValueError(
                f"Invalid SSN format: {ssn}. Expected XXX-XX-XXXX format"
            )
        
        # Check database exists
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Credit database not found at: {self.db_path}. "
                "Run src/mcp/seed_data.py to create it."
            )
        
        try:
            # Connect to database
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Query credit report
            cursor.execute("""
                SELECT 
                    ssn,
                    credit_score,
                    credit_utilization,
                    accounts_open,
                    derogatory_marks,
                    credit_age_months,
                    payment_history,
                    late_payments_12mo,
                    hard_inquiries_12mo,
                    bureau_source,
                    updated_at
                FROM credit_reports
                WHERE ssn = ?
            """, (ssn,))
            
            row = cursor.fetchone()
            conn.close()
            
            # Check if record found
            if not row:
                logger.warning(f"No credit record found for SSN: {ssn}")
                raise KeyError(f"No credit report exists for SSN {ssn}")
            
            # Convert to dictionary matching CreditReport schema
            report = {
                "ssn": row["ssn"],
                "report_date": datetime.utcnow().isoformat(),
                "credit_score": row["credit_score"],
                "credit_utilization": row["credit_utilization"],
                "accounts_open": row["accounts_open"],
                "derogatory_marks": row["derogatory_marks"],
                "credit_age_months": row["credit_age_months"],
                "payment_history": row["payment_history"],
                "late_payments_12mo": row["late_payments_12mo"],
                "hard_inquiries_12mo": row["hard_inquiries_12mo"],
                "bureau_source": row["bureau_source"],
            }
            
            logger.info(
                f"Retrieved credit report for SSN: {ssn} "
                f"(score: {report['credit_score']}, "
                f"payment_history: {report['payment_history']})"
            )
            
            return report
        
        except sqlite3.Error as e:
            logger.error(f"Database error querying credit report for {ssn}: {e}")
            raise sqlite3.Error(f"Failed to query credit database: {e}") from e
    
    def credit_record_exists(self, ssn: str) -> bool:
        """
        Check if a credit record exists for given SSN.
        
        Args:
            ssn: Social Security Number
        
        Returns:
            True if credit record exists, False otherwise
        """
        if not self._validate_ssn_format(ssn):
            return False
        
        if not self.db_path.exists():
            return False
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM credit_reports WHERE ssn = ? LIMIT 1", (ssn,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except sqlite3.Error:
            return False
    
    def list_all_ssns(self) -> list[str]:
        """
        List all SSNs in the credit database.
        
        Useful for testing and validation.
        
        Returns:
            List of SSNs
        
        Raises:
            FileNotFoundError: Database does not exist
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Credit database not found at: {self.db_path}")
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ssn FROM credit_reports ORDER BY credit_score DESC")
            rows = cursor.fetchall()
            conn.close()
            
            ssns = [row["ssn"] for row in rows]
            logger.info(f"Listed {len(ssns)} SSNs from credit database")
            return ssns
        
        except sqlite3.Error as e:
            logger.error(f"Error listing SSNs: {e}")
            raise sqlite3.Error(f"Failed to list SSNs: {e}") from e
    
    def get_credit_summary(self, ssn: str) -> dict:
        """
        Get simplified credit summary with just key metrics.
        
        Args:
            ssn: Social Security Number
        
        Returns:
            Dictionary with credit_score, payment_history, risk_level
        
        Raises:
            ValueError: Invalid SSN or no record found
        """
        report = self.get_credit_report(ssn)
        
        # Determine risk level based on credit score
        score = report["credit_score"]
        if score >= 740:
            risk_level = "low"
        elif score >= 670:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return {
            "ssn": report["ssn"],
            "credit_score": report["credit_score"],
            "payment_history": report["payment_history"],
            "risk_level": risk_level,
            "derogatory_marks": report["derogatory_marks"],
        }
    
    def get_database_stats(self) -> dict:
        """
        Get statistics about the credit database.
        
        Returns:
            Dictionary with total records, score distribution, etc.
        """
        if not self.db_path.exists():
            return {
                "exists": False,
                "total_records": 0,
                "error": "Database not found",
            }
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total records
            cursor.execute("SELECT COUNT(*) FROM credit_reports")
            total = cursor.fetchone()[0]
            
            # Score distribution
            cursor.execute("""
                SELECT 
                    AVG(credit_score) as avg_score,
                    MIN(credit_score) as min_score,
                    MAX(credit_score) as max_score
                FROM credit_reports
            """)
            stats = cursor.fetchone()
            
            # Payment history distribution
            cursor.execute("""
                SELECT payment_history, COUNT(*) as count
                FROM credit_reports
                GROUP BY payment_history
            """)
            payment_dist = {row["payment_history"]: row["count"] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                "exists": True,
                "total_records": total,
                "avg_credit_score": round(stats["avg_score"], 1) if stats["avg_score"] else 0,
                "min_credit_score": stats["min_score"],
                "max_credit_score": stats["max_score"],
                "payment_history_distribution": payment_dist,
            }
        
        except sqlite3.Error as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                "exists": True,
                "error": str(e),
            }
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Create database connection with row factory.
        
        Returns:
            SQLite connection with dict-like row access
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def _validate_ssn_format(self, ssn: str) -> bool:
        """
        Validate SSN format matches XXX-XX-XXXX pattern.
        
        Args:
            ssn: Social Security Number string
        
        Returns:
            True if valid format, False otherwise
        """
        import re
        pattern = r'^\d{3}-\d{2}-\d{4}$'
        return bool(re.match(pattern, ssn))
