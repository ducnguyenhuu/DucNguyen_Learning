"""
Generate test paystub PDFs for different underwriting scenarios.

This script creates realistic paystub PDFs matching the three test scenarios:
1. High-income excellent credit applicant ($180k/year)
2. Moderate-income good credit applicant ($95k/year)  
3. Low-income poor credit applicant ($55k/year)

Usage:
    python scripts/generate_test_paystubs.py

Output: Creates 3 paystub PDFs in data/applications/
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path
import sys


def create_paystub(
    output_path: Path,
    employee_name: str,
    employee_id: str,
    company_name: str,
    company_address: str,
    gross_biweekly: float,
    hourly_rate: float = None,
    regular_hours: float = 80.0,
    overtime_hours: float = 0.0,
    pay_period: str = "11/01/2024 - 11/15/2024",
    ytd_gross: float = None
):
    """
    Create a paystub PDF with specified parameters.
    
    Args:
        output_path: Where to save the PDF
        employee_name: Employee's full name
        employee_id: Employee ID number
        company_name: Employer's name
        company_address: Employer's address
        gross_biweekly: Gross pay for this pay period
        hourly_rate: Hourly wage (if None, calculated from gross)
        regular_hours: Regular hours worked (default 80 = 2 weeks)
        overtime_hours: Overtime hours worked
        pay_period: Pay period dates
        ytd_gross: Year-to-date gross (if None, calculated as gross * 26)
    """
    
    # Calculate hourly rate if not provided
    if hourly_rate is None:
        hourly_rate = gross_biweekly / (regular_hours + overtime_hours * 1.5)
    
    # Calculate overtime pay
    regular_pay = regular_hours * hourly_rate
    overtime_pay = overtime_hours * hourly_rate * 1.5
    
    # Calculate YTD if not provided (assume 26 pay periods)
    if ytd_gross is None:
        ytd_gross = gross_biweekly * 26
    
    # Calculate deductions (approximations)
    federal_tax = gross_biweekly * 0.15
    state_tax = gross_biweekly * 0.05
    social_security = gross_biweekly * 0.062
    medicare = gross_biweekly * 0.0145
    
    total_deductions = federal_tax + state_tax + social_security + medicare
    net_pay = gross_biweekly - total_deductions
    ytd_net = ytd_gross - (total_deductions * 26)
    
    # Create PDF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont('Helvetica-Bold', 16)
    c.drawString(50, height - 50, 'PAYSTUB')
    
    # Company info
    c.setFont('Helvetica', 10)
    c.drawString(50, height - 80, company_name)
    c.drawString(50, height - 95, company_address)
    
    # Employee info
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, height - 130, 'Employee Information')
    c.setFont('Helvetica', 10)
    c.drawString(50, height - 150, f'Name: {employee_name}')
    c.drawString(50, height - 165, f'Employee ID: {employee_id}')
    c.drawString(50, height - 180, f'Pay Period: {pay_period}')
    
    # Earnings
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, height - 220, 'Earnings')
    c.setFont('Helvetica', 10)
    c.drawString(50, height - 240, f'Regular Hours: {regular_hours:.2f} hrs @ ${hourly_rate:.2f}/hr')
    c.drawString(400, height - 240, f'${regular_pay:,.2f}')
    
    if overtime_hours > 0:
        c.drawString(50, height - 260, f'Overtime: {overtime_hours:.2f} hrs @ ${hourly_rate*1.5:.2f}/hr')
        c.drawString(400, height - 260, f'${overtime_pay:,.2f}')
        earnings_y = height - 290
    else:
        earnings_y = height - 270
    
    # Gross pay
    c.setFont('Helvetica-Bold', 10)
    c.drawString(50, earnings_y, 'Gross Pay')
    c.drawString(400, earnings_y, f'${gross_biweekly:,.2f}')
    
    # Deductions
    deductions_y = earnings_y - 40
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, deductions_y, 'Deductions')
    c.setFont('Helvetica', 10)
    c.drawString(50, deductions_y - 20, 'Federal Tax')
    c.drawString(400, deductions_y - 20, f'${federal_tax:,.2f}')
    c.drawString(50, deductions_y - 35, 'State Tax')
    c.drawString(400, deductions_y - 35, f'${state_tax:,.2f}')
    c.drawString(50, deductions_y - 50, 'Social Security')
    c.drawString(400, deductions_y - 50, f'${social_security:,.2f}')
    c.drawString(50, deductions_y - 65, 'Medicare')
    c.drawString(400, deductions_y - 65, f'${medicare:,.2f}')
    
    # Net pay
    net_y = deductions_y - 105
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, net_y, 'Net Pay')
    c.drawString(400, net_y, f'${net_pay:,.2f}')
    
    # YTD summary
    ytd_y = net_y - 45
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, ytd_y, 'Year-to-Date Summary')
    c.setFont('Helvetica', 10)
    c.drawString(50, ytd_y - 20, f'Gross Pay YTD: ${ytd_gross:,.2f}')
    c.drawString(50, ytd_y - 35, f'Net Pay YTD: ${ytd_net:,.2f}')
    
    c.save()
    print(f'✅ Created: {output_path}')
    print(f'   Employee: {employee_name}')
    print(f'   Gross Biweekly: ${gross_biweekly:,.2f}')
    print(f'   Annual (26 periods): ${gross_biweekly * 26:,.2f}')
    print()


def main():
    """Generate all test paystubs."""
    
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "data" / "applications"
    
    print("="*70)
    print("GENERATING TEST PAYSTUBS")
    print("="*70)
    print()
    
    # Scenario 1: Auto-Approval - High Income ($180k/year)
    # $180,000 / 26 pay periods = $6,923 biweekly
    create_paystub(
        output_path=output_dir / "paystub_scenario1_approval.pdf",
        employee_name="Alice Excellence",
        employee_id="EMP-12345",
        company_name="Tech Corp",
        company_address="123 Innovation Dr, San Francisco, CA 94102",
        gross_biweekly=6923.08,
        regular_hours=80.0,
        overtime_hours=5.0,
        pay_period="11/01/2024 - 11/15/2024"
    )
    
    # Scenario 2: Conditional Approval - Moderate Income ($95k/year)
    # $95,000 / 26 pay periods = $3,654 biweekly
    create_paystub(
        output_path=output_dir / "paystub_scenario2_conditional.pdf",
        employee_name="Bob Marginal",
        employee_id="EMP-54321",
        company_name="Small Business Inc",
        company_address="456 Commerce St, Oakland, CA 94601",
        gross_biweekly=3653.85,
        regular_hours=80.0,
        overtime_hours=2.0,
        pay_period="11/01/2024 - 11/15/2024"
    )
    
    # Scenario 3: Rejection - Low Income ($55k/year)
    # $55,000 / 26 pay periods = $2,115 biweekly
    create_paystub(
        output_path=output_dir / "paystub_scenario3_rejection.pdf",
        employee_name="Charlie Risky",
        employee_id="EMP-99999",
        company_name="Gig Economy Co",
        company_address="789 Hustle Ave, Fresno, CA 93650",
        gross_biweekly=2115.38,
        regular_hours=80.0,
        overtime_hours=0.0,
        pay_period="11/01/2024 - 11/15/2024"
    )
    
    print("="*70)
    print("✅ ALL PAYSTUBS GENERATED")
    print("="*70)
    print()
    print("Next Steps:")
    print("1. Update notebook 07 to use scenario-specific paystubs")
    print("2. Run notebook cells to execute underwriting workflow")
    print("3. Compare outcomes across three scenarios")


if __name__ == "__main__":
    main()
