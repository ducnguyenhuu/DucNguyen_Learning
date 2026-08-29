"""
Generate policy documents for loan underwriting RAG system.

This script creates 5 sample lending policy documents:
1. Underwriting Standards
2. Credit Requirements
3. Income Verification
4. Property Guidelines
5. Compliance Rules

Task: T016 - Create policy documents for RAG system
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from pathlib import Path
from datetime import datetime


def create_header_footer(canvas, doc):
    """Add header and footer to each page."""
    canvas.saveState()
    
    # Header
    canvas.setFont('Helvetica-Bold', 10)
    canvas.drawString(inch, 10.5*inch, "DUC NGUYEN LENDING CORPORATION")
    canvas.setFont('Helvetica', 8)
    canvas.drawString(inch, 10.3*inch, "Confidential - Internal Use Only")
    
    # Footer
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(7.5*inch, 0.5*inch, f"Page {doc.page}")
    canvas.drawString(inch, 0.5*inch, f"Effective Date: January 1, 2025")
    
    canvas.restoreState()


def create_underwriting_standards(output_path: Path):
    """Create underwriting standards policy document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=1.2*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=18, textColor=colors.HexColor('#1a1a1a'),
                                alignment=TA_CENTER, spaceAfter=20)
    
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                  fontSize=14, textColor=colors.HexColor('#2c3e50'),
                                  spaceAfter=12, spaceBefore=12)
    
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                               alignment=TA_JUSTIFY, fontSize=10, leading=14)
    
    # Title
    story.append(Paragraph("UNDERWRITING STANDARDS POLICY", title_style))
    story.append(Paragraph("Version 2.1 | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Section 1
    story.append(Paragraph("1. PURPOSE AND SCOPE", heading_style))
    story.append(Paragraph(
        "This policy establishes the underwriting standards for all conventional mortgage loans originated "
        "by Duc Nguyen Lending Corporation. These standards ensure consistent loan quality, regulatory compliance, "
        "and appropriate risk management while maintaining competitive market positioning.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 2
    story.append(Paragraph("2. CREDIT SCORE REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>2.1 Minimum Credit Score:</b> The minimum acceptable credit score for conventional loans is 620. "
        "Applications with scores below this threshold must be automatically declined unless extraordinary "
        "compensating factors are present and documented.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.2 Risk-Based Pricing Tiers:</b><br/>"
        "• Excellent (740+): Prime rate<br/>"
        "• Good (680-739): Prime + 0.25%<br/>"
        "• Fair (620-679): Prime + 0.75%<br/>",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 3
    story.append(Paragraph("3. DEBT-TO-INCOME RATIO GUIDELINES", heading_style))
    story.append(Paragraph(
        "<b>3.1 Standard DTI Limits:</b> The maximum debt-to-income ratio for conventional loans is 36% "
        "for front-end ratio (housing expenses only) and 43% for back-end ratio (all debt obligations).",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>3.2 DTI Exceptions:</b> DTI ratios up to 45% may be approved with strong compensating factors:<br/>"
        "• Credit score above 740<br/>"
        "• Cash reserves exceeding 6 months PITI (Principal, Interest, Taxes, Insurance)<br/>"
        "• Down payment greater than 20%<br/>"
        "• Stable employment history exceeding 2 years with same employer<br/>"
        "• Demonstrated history of managing higher housing expenses",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 4
    story.append(Paragraph("4. LOAN-TO-VALUE REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>4.1 Maximum LTV:</b> Standard maximum loan-to-value ratio is 97% for primary residences. "
        "LTV above 80% requires private mortgage insurance (PMI).",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.2 Property Type Variations:</b><br/>"
        "• Single-family primary residence: 97% maximum LTV<br/>"
        "• Condo primary residence: 95% maximum LTV<br/>"
        "• Multi-family (2-4 units): 85% maximum LTV<br/>"
        "• Investment properties: 80% maximum LTV<br/>"
        "• Second homes: 90% maximum LTV",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 5
    story.append(Paragraph("5. EMPLOYMENT AND INCOME VERIFICATION", heading_style))
    story.append(Paragraph(
        "<b>5.1 Employment Stability:</b> Borrowers must demonstrate stable employment for a minimum of "
        "2 years. Gaps in employment exceeding 6 months require detailed explanation and documentation.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>5.2 Income Documentation:</b> All income sources must be verified through:<br/>"
        "• Most recent 2 pay stubs<br/>"
        "• W-2 forms for previous 2 years<br/>"
        "• Tax returns for self-employed borrowers (2 years)<br/>"
        "• Bank statements showing regular deposits<br/>"
        "• Employment verification letter (VOE) dated within 30 days of closing",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 6
    story.append(Paragraph("6. ASSET REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>6.1 Minimum Reserves:</b> Borrowers must demonstrate liquid reserves equal to 2 months PITI "
        "after closing for single-family primary residences. Multi-family and investment properties require "
        "6 months reserves.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>6.2 Down Payment Source:</b> Down payment funds must be documented and sourced. Large deposits "
        "(>25% of monthly income) within 60 days of application require explanation and documentation. "
        "Gift funds are acceptable with proper gift letter documentation.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 7
    story.append(Paragraph("7. CREDIT HISTORY REVIEW", heading_style))
    story.append(Paragraph(
        "<b>7.1 Payment History:</b> Applicants must demonstrate satisfactory payment history with no "
        "more than 2 late payments (30+ days) in the past 12 months on any credit account.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>7.2 Derogatory Items:</b><br/>"
        "• Bankruptcy: 4 years from discharge date<br/>"
        "• Foreclosure: 7 years from completion date<br/>"
        "• Short sale/Deed in lieu: 4 years from completion<br/>"
        "• Collections/Charge-offs: Must be paid if >$2,000 aggregate",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # Section 8
    story.append(Paragraph("8. COMPENSATING FACTORS", heading_style))
    story.append(Paragraph(
        "When applications do not meet all standard criteria, underwriters may approve based on compensating "
        "factors that offset identified risks:<br/>"
        "• Substantial down payment (20% or more)<br/>"
        "• Excellent credit history (no late payments in 24 months)<br/>"
        "• Significant liquid reserves (6+ months PITI)<br/>"
        "• Low residual income ratio post-closing<br/>"
        "• Demonstrated ability to accumulate savings<br/>"
        "• Minimal credit utilization (<30% of available credit)<br/>"
        "• Long employment history with steady income growth",
        body_style
    ))
    
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"✓ Created: {output_path}")


def create_credit_requirements(output_path: Path):
    """Create credit requirements policy document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=1.2*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                  fontSize=14, spaceAfter=12, spaceBefore=12)
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                               alignment=TA_JUSTIFY, fontSize=10, leading=14)
    
    story.append(Paragraph("CREDIT REQUIREMENTS POLICY", title_style))
    story.append(Paragraph("Version 1.8 | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. CREDIT SCORE EVALUATION", heading_style))
    story.append(Paragraph(
        "<b>1.1 Credit Report Sources:</b> All applications require a tri-merge credit report from Equifax, "
        "Experian, and TransUnion. The middle score will be used for qualification purposes. If only two "
        "scores are available, the lower score is used.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>1.2 Score Requirements by Loan Type:</b><br/>"
        "• Conventional: 620 minimum<br/>"
        "• FHA: 580 minimum (3.5% down), 500 minimum (10% down)<br/>"
        "• VA: No minimum (compensating factors required if <620)<br/>"
        "• USDA: 640 recommended",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("2. CREDIT UTILIZATION", heading_style))
    story.append(Paragraph(
        "<b>2.1 Acceptable Utilization:</b> Total revolving credit utilization should not exceed 50% of "
        "available credit. Utilization above 80% may indicate financial stress and requires additional "
        "scrutiny and compensating factors.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.2 Individual Account Utilization:</b> Multiple accounts at maximum limits (>95% utilization) "
        "may indicate inability to manage credit responsibly, even if aggregate utilization is acceptable.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("3. PAYMENT HISTORY STANDARDS", heading_style))
    story.append(Paragraph(
        "<b>3.1 Late Payment Limits:</b><br/>"
        "• Last 12 months: Maximum 2 late payments (30 days)<br/>"
        "• Last 24 months: Maximum 4 late payments (30 days)<br/>"
        "• 60-day late payments: Maximum 1 in past 24 months<br/>"
        "• 90-day late payments: None in past 24 months",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>3.2 Housing Payment History:</b> Current and previous mortgage/rent payment history must be "
        "perfect (no 30-day late payments) for past 12 months. Any mortgage late payments in past 12 "
        "months result in automatic decline.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("4. DEROGATORY CREDIT EVENTS", heading_style))
    story.append(Paragraph(
        "<b>4.1 Bankruptcy Seasoning Requirements:</b><br/>"
        "• Chapter 7: 4 years from discharge date<br/>"
        "• Chapter 13: 2 years from discharge, 4 years from dismissal<br/>"
        "• Multiple bankruptcies: 7 years from most recent discharge<br/>"
        "Re-established credit required with minimum 2 tradelines in good standing.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.2 Foreclosure and Short Sale:</b><br/>"
        "• Foreclosure: 7 years from completion<br/>"
        "• Short sale: 4 years if deficiency was forgiven<br/>"
        "• Deed in lieu: 4 years from completion<br/>"
        "Re-established credit and documented extenuating circumstances required.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.3 Collections and Charge-Offs:</b> All collection accounts and charge-offs totaling "
        "$2,000 or more must be paid in full prior to closing. Medical collections under $5,000 may "
        "be excluded from DTI calculations if adequately explained.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("5. INQUIRIES AND NEW CREDIT", heading_style))
    story.append(Paragraph(
        "<b>5.1 Hard Inquiries:</b> Multiple hard inquiries (>6) within 12 months may indicate credit "
        "shopping or financial distress. Borrower must provide written explanation for any inquiries not "
        "related to rate shopping for mortgage, auto, or student loans.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>5.2 New Credit Accounts:</b> Opening new credit accounts within 90 days of application may "
        "impact debt-to-income ratios and requires updated credit report and re-qualification. New accounts "
        "after initial approval but before closing may result in loan denial.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("6. CREDIT AGE AND DEPTH", heading_style))
    story.append(Paragraph(
        "<b>6.1 Credit History Length:</b> Minimum 2 years of established credit history required. "
        "Borrowers with limited credit history (<3 years) may qualify with non-traditional credit "
        "references (rent, utilities, insurance payments) if documented for 12+ months.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>6.2 Number of Tradelines:</b> Minimum 3 active tradelines required, with at least 12 months "
        "history each. Authorized user accounts may be considered but primary accounts are preferred.",
        body_style
    ))
    
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"✓ Created: {output_path}")


def create_income_verification(output_path: Path):
    """Create income verification policy document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=1.2*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                  fontSize=14, spaceAfter=12, spaceBefore=12)
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                               alignment=TA_JUSTIFY, fontSize=10, leading=14)
    
    story.append(Paragraph("INCOME VERIFICATION POLICY", title_style))
    story.append(Paragraph("Version 2.0 | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. EMPLOYMENT VERIFICATION", heading_style))
    story.append(Paragraph(
        "<b>1.1 W-2 Employment Documentation:</b> Salaried and hourly employees must provide:<br/>"
        "• Most recent 30 days of pay stubs showing year-to-date earnings<br/>"
        "• W-2 forms for most recent 2 years<br/>"
        "• Written verification of employment (VOE) dated within 10 days of closing<br/>"
        "• Verbal VOE required within 10 days of closing to confirm continued employment",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>1.2 Employment Stability:</b> Minimum 2 years employment history required. Job changes within "
        "same field/industry are acceptable. Career changes or gaps exceeding 6 months require detailed "
        "written explanation and may require additional reserves.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("2. SELF-EMPLOYMENT INCOME", heading_style))
    story.append(Paragraph(
        "<b>2.1 Documentation Requirements:</b> Self-employed borrowers (≥25% ownership) must provide:<br/>"
        "• Personal tax returns (1040) for most recent 2 years with all schedules<br/>"
        "• Business tax returns (1120, 1120S, 1065) for 2 years if applicable<br/>"
        "• Year-to-date profit & loss statement<br/>"
        "• Business license and proof of business operation<br/>"
        "• CPA letter confirming business viability (if applicable)",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.2 Income Calculation:</b> Self-employment income is calculated by averaging 24 months of "
        "reported income after adding back non-cash deductions (depreciation, depletion, business use of "
        "home). Declining income trends may result in lower qualifying income or denial.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("3. BONUS AND COMMISSION INCOME", heading_style))
    story.append(Paragraph(
        "<b>3.1 Qualification Requirements:</b> Bonus and commission income may be used for qualification "
        "if 2-year history is documented via W-2s and pay stubs. Income must be stable or increasing. "
        "Declining trends require use of lower average or exclusion from qualifying income.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>3.2 Calculation Method:</b> Average 24 months of bonus/commission income. If employed less than "
        "2 years but more than 1 year, average available months. Less than 1 year history generally cannot "
        "be used unless employer letter confirms guaranteed minimum.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("4. OTHER INCOME SOURCES", heading_style))
    story.append(Paragraph(
        "<b>4.1 Rental Income:</b> Rental income from investment properties may be used with:<br/>"
        "• Lease agreement showing rental amount<br/>"
        "• Tax returns (Schedule E) showing 2-year history<br/>"
        "• 75% of gross rents used for qualifying (25% maintenance factor)",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.2 Social Security and Pension:</b> Must be verified with award letter or benefit statement. "
        "Income must continue for at least 3 years. SSI income must be documented to continue indefinitely.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.3 Alimony and Child Support:</b> Must be court-ordered and documented with divorce decree or "
        "separation agreement. Must continue for at least 3 years. 6 months payment history required via "
        "bank statements.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("5. INCOME CALCULATION STANDARDS", heading_style))
    story.append(Paragraph(
        "<b>5.1 Overtime and Part-Time Income:</b> May be included if 2-year history documented and "
        "employer confirms likelihood of continuance. Average 24 months for stable income, use lower "
        "figure if declining trend.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>5.2 Income Trending:</b><br/>"
        "• Increasing trend: Use most recent 12-month average<br/>"
        "• Stable trend: Use 24-month average<br/>"
        "• Declining trend: Use most recent 12 months or exclude if significant decline",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("6. VERIFICATION TIMING", heading_style))
    story.append(Paragraph(
        "<b>6.1 Pre-Closing Verification:</b> All employment and income must be re-verified within 10 "
        "business days of closing. Any changes in employment status, income, or employer must be "
        "immediately reported and may require complete re-underwriting.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>6.2 Verbal VOE:</b> Underwriter or processor must complete verbal verification of employment "
        "by speaking directly with employer HR department or supervisor within 10 days of closing to "
        "confirm continued employment and income stability.",
        body_style
    ))
    
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"✓ Created: {output_path}")


def create_property_guidelines(output_path: Path):
    """Create property guidelines policy document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=1.2*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                  fontSize=14, spaceAfter=12, spaceBefore=12)
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                               alignment=TA_JUSTIFY, fontSize=10, leading=14)
    
    story.append(Paragraph("PROPERTY GUIDELINES POLICY", title_style))
    story.append(Paragraph("Version 1.5 | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. APPRAISAL REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>1.1 Appraiser Qualifications:</b> All appraisals must be completed by state-licensed or "
        "certified appraisers with appropriate coverage for the property type and location. Appraisers "
        "must be independent and ordered through approved appraisal management company (AMC).",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>1.2 Appraisal Standards:</b> Full interior and exterior appraisal required for all purchase "
        "and refinance transactions. Comparable sales must be within 1 mile and sold within 6 months. "
        "Minimum 3 comparable sales required.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("2. PROPERTY TYPE ELIGIBILITY", heading_style))
    story.append(Paragraph(
        "<b>2.1 Single-Family Detached:</b> Primary residence, second home, and investment properties "
        "eligible. Maximum LTV varies by occupancy: 97% primary, 90% second home, 80% investment.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.2 Condominiums:</b> Must be in approved projects (Fannie Mae/Freddie Mac approval) or "
        "meet project review requirements. Owner-occupancy ratio must be at least 51%. Maximum 15% "
        "commercial space. HOA must be financially stable with adequate reserves.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.3 Multi-Family (2-4 units):</b> All units must be residential. Mixed-use properties with "
        "commercial space limited to 25% of total square footage. Owner occupancy required for LTV >80%.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("3. PROPERTY CONDITION", heading_style))
    story.append(Paragraph(
        "<b>3.1 Minimum Property Standards:</b> Property must be habitable, structurally sound, and meet "
        "local building codes. Major defects identified in appraisal must be repaired prior to closing "
        "or funds held in escrow for completion.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>3.2 Required Repairs:</b> Any conditions affecting safety, soundness, or structural integrity "
        "must be repaired. This includes: roof damage, foundation issues, electrical/plumbing defects, "
        "HVAC failures, and pest infestation.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("4. PROPERTY VALUATION", heading_style))
    story.append(Paragraph(
        "<b>4.1 Value Adjustments:</b> Appraised value may be adjusted for market conditions, property "
        "condition, and location factors. Adjustments exceeding 25% per comparable require additional "
        "explanation and may trigger review appraisal.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.2 Contract Price vs Appraisal:</b> Lower of sales price or appraised value used for LTV "
        "calculations. Appraisal shortfalls require additional down payment to maintain approved LTV ratio.",
        body_style
    ))
    
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"✓ Created: {output_path}")


def create_compliance_rules(output_path: Path):
    """Create compliance rules policy document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=1.2*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                  fontSize=14, spaceAfter=12, spaceBefore=12)
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'],
                               alignment=TA_JUSTIFY, fontSize=10, leading=14)
    
    story.append(Paragraph("COMPLIANCE RULES POLICY", title_style))
    story.append(Paragraph("Version 3.0 | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. FAIR LENDING COMPLIANCE", heading_style))
    story.append(Paragraph(
        "<b>1.1 Equal Credit Opportunity Act (ECOA):</b> All lending decisions must be based solely on "
        "creditworthiness factors. Prohibited basis considerations include race, color, religion, national "
        "origin, sex, marital status, age, or receipt of public assistance.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>1.2 Fair Housing Act:</b> No discrimination in any aspect of residential lending based on "
        "protected classes. All marketing, application processing, and underwriting must be conducted "
        "in compliance with fair housing regulations.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("2. ABILITY-TO-REPAY REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>2.1 Qualified Mortgage (QM) Standards:</b> All loans must meet QM requirements unless "
        "documented exception applies:<br/>"
        "• DTI ratio not exceeding 43%<br/>"
        "• No negative amortization, interest-only, or balloon features<br/>"
        "• Loan term not exceeding 30 years<br/>"
        "• Points and fees not exceeding 3% of loan amount",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>2.2 Income Verification:</b> Reasonable and good faith determination of borrower's ability "
        "to repay required. Documentation must support all income sources used for qualification.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("3. DISCLOSURE REQUIREMENTS", heading_style))
    story.append(Paragraph(
        "<b>3.1 TRID Compliance:</b> All required disclosures must be provided within regulatory "
        "timeframes:<br/>"
        "• Loan Estimate (LE): Within 3 business days of application<br/>"
        "• Closing Disclosure (CD): At least 3 business days before closing<br/>"
        "• Any changes requiring new waiting period must be properly documented",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>3.2 Adverse Action Notices:</b> All denied, withdrawn, or incomplete applications require "
        "adverse action notice within 30 days. Notice must specify specific reasons for denial.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("4. ANTI-PREDATORY LENDING", heading_style))
    story.append(Paragraph(
        "<b>4.1 HOEPA Compliance:</b> High-cost mortgages must comply with HOEPA restrictions. Loans "
        "exceeding APR or points/fees triggers require additional disclosures and counseling.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>4.2 Prohibited Practices:</b> The following practices are strictly prohibited:<br/>"
        "• Loan flipping or frequent refinancing without borrower benefit<br/>"
        "• Yield spread premium abuse<br/>"
        "• Mandatory arbitration clauses<br/>"
        "• Prepayment penalties on high-cost loans",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("5. PRIVACY AND DATA SECURITY", heading_style))
    story.append(Paragraph(
        "<b>5.1 Gramm-Leach-Bliley Act:</b> All borrower information must be protected with appropriate "
        "safeguards. Privacy notices must be provided at application and annually thereafter.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>5.2 Information Security:</b> All systems handling borrower data must implement appropriate "
        "security measures including encryption, access controls, and audit trails. Data breaches must "
        "be reported immediately per regulatory requirements.",
        body_style
    ))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("6. QUALITY CONTROL", heading_style))
    story.append(Paragraph(
        "<b>6.1 Post-Closing Review:</b> Minimum 10% of closed loans must undergo post-closing quality "
        "control review. Discretionary sample plus all loans meeting specific risk criteria.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<b>6.2 Defect Trending:</b> All defects identified in QC review must be documented, trended, "
        "and addressed through corrective action. Significant defect rates trigger mandatory training "
        "or process improvements.",
        body_style
    ))
    
    doc.build(story, onFirstPage=create_header_footer, onLaterPages=create_header_footer)
    print(f"✓ Created: {output_path}")


def main():
    """Generate all policy documents."""
    print("\n=== Generating Policy Documents (T016) ===\n")
    
    base_path = Path(__file__).parent.parent / "data" / "policies"
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Generate policy PDFs
    create_underwriting_standards(base_path / "underwriting_standards.pdf")
    create_credit_requirements(base_path / "credit_requirements.pdf")
    create_income_verification(base_path / "income_verification.pdf")
    create_property_guidelines(base_path / "property_guidelines.pdf")
    create_compliance_rules(base_path / "compliance_rules.pdf")
    
    print(f"\n✅ All policy documents created in: {base_path}\n")


if __name__ == "__main__":
    main()
