"""
MCP Server Connectors Package.

This package contains data source connectors that abstract access to:
- File system (loan application documents)
- Credit bureau database (mock SQLite)
- Application metadata database (SQLite)

The connector pattern decouples the MCP server from direct data access,
making it easier to swap implementations (e.g., S3 instead of local files,
real credit bureau APIs instead of mock database).

Modules:
- file_connector.py: File system access for uploaded documents
- credit_connector.py: Credit bureau database queries
- app_connector.py: Application metadata queries (future)

Usage:
    from src.mcp.connectors import FileConnector, CreditConnector
    
    # Access uploaded documents
    file_conn = FileConnector(base_path="data/applications")
    pdf_data = file_conn.get_file("app-001/paystub.pdf")
    
    # Query credit reports
    credit_conn = CreditConnector(db_path="data/mock_credit_bureau.db")
    report = credit_conn.get_credit_report("123-45-6789")
"""

__version__ = "1.0.0"
__author__ = "AI Loan Underwriting System"

# Import connectors
from .file_connector import FileConnector
from .credit_connector import CreditConnector

__all__ = [
    "FileConnector",
    "CreditConnector",
]
