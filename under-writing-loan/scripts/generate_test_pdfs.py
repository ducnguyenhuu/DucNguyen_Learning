"""
Generate test PDF files for loan underwriting system.

This script creates realistic-looking PDF documents for testing the Document Agent:
- Pay stubs (clean and scanned versions)
- Bank statements
- Driver's licenses
- Tax returns

Task: T015 - Create test PDF files
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from pathlib import Path
from datetime import datetime, timedelta
import random


def create_pay_stub_clean(output_path: Path):
    """Create a clean, high-quality pay stub PDF."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Company header
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER
    )
    story.append(Paragraph("ACME CORPORATION", company_style))
    story.append(Paragraph("123 Main Street, San Francisco, CA 94105", styles['Normal']))
    story.append(Paragraph("Phone: (415) 555-0100 | Fax: (415) 555-0101", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Pay stub title
    title_style = ParagraphStyle('Title', parent=styles['Heading2'], alignment=TA_CENTER)
    story.append(Paragraph("EMPLOYEE PAY STUB", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Employee information table
    employee_data = [
        ['Employee Name:', 'Jane Doe', 'Employee ID:', 'EMP-2025-001'],
        ['Social Security:', 'XXX-XX-1111', 'Pay Period:', 'Oct 1 - Oct 31, 2025'],
        ['Department:', 'Engineering', 'Pay Date:', 'November 5, 2025'],
        ['Position:', 'Senior Software Engineer', 'Payment Method:', 'Direct Deposit'],
    ]
    
    employee_table = Table(employee_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    employee_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f0f0')),
    ]))
    story.append(employee_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Earnings section
    story.append(Paragraph("<b>EARNINGS</b>", styles['Heading3']))
    earnings_data = [
        ['Description', 'Rate', 'Hours', 'Current', 'YTD'],
        ['Regular Pay', '$75.00', '160.00', '$12,000.00', '$120,000.00'],
        ['Overtime Pay', '$112.50', '0.00', '$0.00', '$5,000.00'],
        ['Bonus', '-', '-', '$0.00', '$8,000.00'],
        ['<b>GROSS PAY</b>', '', '', '<b>$12,000.00</b>', '<b>$133,000.00</b>'],
    ]
    
    earnings_table = Table(earnings_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.25*inch, 1.25*inch])
    earnings_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
    ]))
    story.append(earnings_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Deductions section
    story.append(Paragraph("<b>DEDUCTIONS</b>", styles['Heading3']))
    deductions_data = [
        ['Description', 'Current', 'YTD'],
        ['Federal Income Tax', '$2,400.00', '$26,600.00'],
        ['State Income Tax', '$600.00', '$6,650.00'],
        ['Social Security', '$744.00', '$8,246.00'],
        ['Medicare', '$174.00', '$1,929.00'],
        ['Health Insurance', '$250.00', '$2,750.00'],
        ['401(k) Contribution', '$1,200.00', '$13,200.00'],
        ['<b>TOTAL DEDUCTIONS</b>', '<b>$5,368.00</b>', '<b>$59,375.00</b>'],
    ]
    
    deductions_table = Table(deductions_data, colWidths=[4*inch, 1.5*inch, 1.5*inch])
    deductions_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
    ]))
    story.append(deductions_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Net pay section
    story.append(Paragraph("<b>NET PAY</b>", styles['Heading3']))
    net_pay_data = [
        ['Current Period', 'Year to Date'],
        ['$6,632.00', '$73,625.00'],
    ]
    
    net_pay_table = Table(net_pay_data, colWidths=[3.5*inch, 3.5*inch])
    net_pay_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#d4edda')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(net_pay_table)
    
    doc.build(story)
    print(f"✓ Created: {output_path}")


def create_pay_stub_scanned(output_path: Path):
    """Create a lower-quality 'scanned' pay stub PDF."""
    # Similar to clean but with slightly degraded text quality simulation
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Add note about scan quality
    story.append(Paragraph("<i>Note: This is a simulated scanned document with lower quality</i>", 
                          styles['Italic']))
    story.append(Spacer(1, 0.2*inch))
    
    # Company header (slightly less formatted)
    story.append(Paragraph("<b>TECH SOLUTIONS INC</b>", styles['Heading2']))
    story.append(Paragraph("456 Market St, Austin, TX 78701", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>EARNINGS STATEMENT</b>", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    
    # Simple text-based information
    info = [
        "Employee: John Smith",
        "SSN: XXX-XX-4444",
        "Pay Period: October 16-31, 2025",
        "Pay Date: November 8, 2025",
        "",
        "Gross Earnings:",
        "  Regular Wages: $4,166.67",
        "  YTD Gross: $50,000.00",
        "",
        "Deductions:",
        "  Federal Tax: $833.33",
        "  State Tax: $208.33",
        "  Social Security: $258.33",
        "  Medicare: $60.42",
        "  Health Insurance: $150.00",
        "  YTD Deductions: $18,150.00",
        "",
        "Net Pay: $2,656.26",
        "YTD Net Pay: $31,850.00",
    ]
    
    for line in info:
        story.append(Paragraph(line, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created: {output_path}")


def create_bank_statement(output_path: Path):
    """Create a sample bank statement PDF."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Bank header
    bank_style = ParagraphStyle('BankHeader', parent=styles['Heading1'], 
                               textColor=colors.HexColor('#003366'), alignment=TA_CENTER)
    story.append(Paragraph("FIRST NATIONAL BANK", bank_style))
    story.append(Paragraph("www.firstnationalbank.com | 1-800-555-BANK", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Account holder info
    story.append(Paragraph("<b>MONTHLY STATEMENT</b>", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    
    account_info = [
        ['Account Holder:', 'Jane Doe', 'Statement Period:', 'Oct 1 - Oct 31, 2025'],
        ['Account Number:', 'XXXX-XXXX-1234', 'Account Type:', 'Checking'],
        ['Address:', '789 Oak Avenue, San Francisco, CA 94102', '', ''],
    ]
    
    info_table = Table(account_info, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
        ('BACKGROUND', (2, 0), (2, 1), colors.HexColor('#e8f4f8')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Account summary
    story.append(Paragraph("<b>ACCOUNT SUMMARY</b>", styles['Heading3']))
    summary_data = [
        ['Beginning Balance', '$8,450.23'],
        ['Total Deposits', '$12,632.00'],
        ['Total Withdrawals', '$-9,234.15'],
        ['<b>Ending Balance</b>', '<b>$11,848.08</b>'],
    ]
    
    summary_table = Table(summary_data, colWidths=[5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Transaction history
    story.append(Paragraph("<b>TRANSACTION HISTORY</b>", styles['Heading3']))
    transactions_data = [
        ['Date', 'Description', 'Debit', 'Credit', 'Balance'],
        ['10/01', 'Beginning Balance', '', '', '$8,450.23'],
        ['10/05', 'Direct Deposit - ACME CORP', '', '$6,632.00', '$15,082.23'],
        ['10/07', 'Mortgage Payment', '$-2,450.00', '', '$12,632.23'],
        ['10/10', 'Grocery Store', '$-234.56', '', '$12,397.67'],
        ['10/15', 'Gas Station', '$-78.90', '', '$12,318.77'],
        ['10/20', 'Direct Deposit - ACME CORP', '', '$6,000.00', '$18,318.77'],
        ['10/22', 'Electric Bill', '$-145.23', '', '$18,173.54'],
        ['10/25', 'Restaurant', '$-89.45', '', '$18,084.09'],
        ['10/28', 'Online Shopping', '$-456.78', '', '$17,627.31'],
        ['10/30', 'ATM Withdrawal', '$-200.00', '', '$17,427.31'],
        ['10/31', 'Transfer to Savings', '$-5,579.23', '', '$11,848.08'],
    ]
    
    trans_table = Table(transactions_data, colWidths=[0.8*inch, 3.2*inch, 1*inch, 1*inch, 1*inch])
    trans_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (2, 0), (4, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ]))
    story.append(trans_table)
    
    doc.build(story)
    print(f"✓ Created: {output_path}")


def create_drivers_license(output_path: Path):
    """Create a sample driver's license PDF."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], 
                                textColor=colors.HexColor('#0066cc'), alignment=TA_CENTER)
    story.append(Paragraph("STATE OF CALIFORNIA", title_style))
    story.append(Paragraph("DEPARTMENT OF MOTOR VEHICLES", styles['Heading2']))
    story.append(Paragraph("DRIVER LICENSE", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    # License information
    license_data = [
        ['LICENSE NUMBER:', 'D1234567', 'CLASS:', 'C'],
        ['', '', 'ENDORSEMENTS:', 'None'],
        ['EXPIRES:', 'November 19, 2029', 'RESTRICTIONS:', 'None'],
        ['', '', 'DOB:', '06/15/1985'],
        ['LAST NAME:', 'DOE', 'SEX:', 'F'],
        ['FIRST NAME:', 'JANE', 'EYES:', 'BRN'],
        ['MIDDLE NAME:', 'MARIE', 'HT:', '5\'-06"'],
        ['', '', 'WGT:', '140 lbs'],
        ['ADDRESS:', '789 Oak Avenue', '', ''],
        ['', 'San Francisco, CA 94102', '', ''],
        ['', '', '', ''],
        ['ISSUE DATE:', '11/19/2024', 'DD:', '123456789012'],
    ]
    
    license_table = Table(license_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 1.5*inch])
    license_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#0066cc')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e6f2ff')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#e6f2ff')),
    ]))
    story.append(license_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Disclaimer
    story.append(Paragraph("<i><font size=8>This is a sample driver's license for testing purposes only. "
                          "Not a valid government-issued identification document.</font></i>", 
                          styles['Italic']))
    
    doc.build(story)
    print(f"✓ Created: {output_path}")


def main():
    """Generate all test PDF files."""
    print("\n=== Generating Test PDF Files (T015) ===\n")
    
    base_path = Path(__file__).parent.parent / "tests" / "sample_applications"
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Generate PDFs
    create_pay_stub_clean(base_path / "pay_stub_clean.pdf")
    create_pay_stub_scanned(base_path / "pay_stub_scanned.pdf")
    create_bank_statement(base_path / "bank_statement.pdf")
    create_drivers_license(base_path / "drivers_license.pdf")
    
    print(f"\n✅ All test PDFs created in: {base_path}\n")


if __name__ == "__main__":
    main()
