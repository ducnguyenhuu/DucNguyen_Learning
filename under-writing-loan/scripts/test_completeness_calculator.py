"""
Test CompletenessCalculator (T021)

This script validates that the CompletenessCalculator correctly:
- Calculates percentage of required fields present
- Identifies missing critical fields
- Provides quality assessments (excellent/good/partial/poor)

Usage:
    python3 scripts/test_completeness_calculator.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.document_agent import CompletenessCalculator
from src.models import DocumentType


def test_completeness_calculator():
    """Test completeness scoring functionality"""
    
    print("\n" + "=" * 80)
    print("COMPLETENESS CALCULATOR TEST (T021)")
    print("=" * 80)
    
    calculator = CompletenessCalculator()
    
    # Test 1: Excellent completeness (100%) - All required fields present
    print("\n" + "-" * 80)
    print("Test 1: Excellent Completeness (100%)")
    print("-" * 80)
    
    complete_pay_stub = {
        "employer_name": "Acme Corporation",
        "employee_name": "John Doe",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        "pay_period_start": "2025-01-01",
        "pay_period_end": "2025-01-15",
        # Optional fields
        "employer_address": "123 Main St",
        "ytd_gross": 60000.00
    }
    
    score, missing, quality = calculator.calculate_completeness(
        complete_pay_stub,
        DocumentType.PAY_STUB
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing if missing else 'None'}")
    
    assert score == 100.0, f"Expected 100%, got {score}%"
    assert quality == "excellent", f"Expected 'excellent', got '{quality}'"
    assert len(missing) == 0, f"Expected no missing fields, got {missing}"
    print("✅ Test 1 PASSED")
    
    # Test 2: Good completeness (83%) - One field missing
    print("\n" + "-" * 80)
    print("Test 2: Good Completeness (83%)")
    print("-" * 80)
    
    mostly_complete_pay_stub = {
        "employer_name": "Acme Corporation",
        "employee_name": "John Doe",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        "pay_period_start": "2025-01-01",
        # Missing: pay_period_end
    }
    
    score, missing, quality = calculator.calculate_completeness(
        mostly_complete_pay_stub,
        DocumentType.PAY_STUB
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing}")
    
    assert 80 <= score < 100, f"Expected 80-99%, got {score}%"
    assert quality == "good", f"Expected 'good', got '{quality}'"
    assert "pay_period_end" in missing, "Expected 'pay_period_end' in missing fields"
    print("✅ Test 2 PASSED")
    
    # Test 3: Partial completeness (67%) - Two fields missing
    print("\n" + "-" * 80)
    print("Test 3: Partial Completeness (67%)")
    print("-" * 80)
    
    partial_pay_stub = {
        "employer_name": "Acme Corporation",
        "employee_name": "John Doe",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        # Missing: pay_period_start, pay_period_end
    }
    
    score, missing, quality = calculator.calculate_completeness(
        partial_pay_stub,
        DocumentType.PAY_STUB
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing}")
    
    assert 50 <= score < 80, f"Expected 50-79%, got {score}%"
    assert quality == "partial", f"Expected 'partial', got '{quality}'"
    assert len(missing) == 2, f"Expected 2 missing fields, got {len(missing)}"
    print("✅ Test 3 PASSED")
    
    # Test 4: Poor completeness (33%) - Most fields missing
    print("\n" + "-" * 80)
    print("Test 4: Poor Completeness (33%)")
    print("-" * 80)
    
    poor_pay_stub = {
        "employer_name": "Acme Corporation",
        "employee_name": "John Doe",
        # Missing: gross_monthly_income, net_monthly_income, 
        #          pay_period_start, pay_period_end
    }
    
    score, missing, quality = calculator.calculate_completeness(
        poor_pay_stub,
        DocumentType.PAY_STUB
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing}")
    
    assert score < 50, f"Expected <50%, got {score}%"
    assert quality == "poor", f"Expected 'poor', got '{quality}'"
    assert len(missing) == 4, f"Expected 4 missing fields, got {len(missing)}"
    print("✅ Test 4 PASSED")
    
    # Test 5: Bank statement completeness
    print("\n" + "-" * 80)
    print("Test 5: Bank Statement Completeness (100%)")
    print("-" * 80)
    
    complete_bank_statement = {
        "bank_name": "First National Bank",
        "account_holder_name": "Jane Smith",
        "account_number": "****1234",
        "statement_start_date": "2025-01-01",
        "statement_end_date": "2025-01-31",
        "ending_balance": 15000.00,
        # Optional
        "beginning_balance": 12000.00,
        "total_deposits": 5000.00,
        "total_withdrawals": 2000.00
    }
    
    score, missing, quality = calculator.calculate_completeness(
        complete_bank_statement,
        DocumentType.BANK_STATEMENT
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing if missing else 'None'}")
    
    assert score == 100.0, f"Expected 100%, got {score}%"
    assert quality == "excellent", f"Expected 'excellent', got '{quality}'"
    print("✅ Test 5 PASSED")
    
    # Test 6: Tax return completeness
    print("\n" + "-" * 80)
    print("Test 6: Tax Return Completeness (100%)")
    print("-" * 80)
    
    complete_tax_return = {
        "tax_year": 2024,
        "taxpayer_name": "Alice Johnson",
        "taxpayer_ssn": "***-**-5678",
        "wages_annual": 85000.00,
        "federal_tax_withheld": 15000.00,
        # Optional
        "employer_name": "Tech Corp",
        "state_tax_withheld": 5000.00
    }
    
    score, missing, quality = calculator.calculate_completeness(
        complete_tax_return,
        DocumentType.TAX_RETURN
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing if missing else 'None'}")
    
    assert score == 100.0, f"Expected 100%, got {score}%"
    assert quality == "excellent", f"Expected 'excellent', got '{quality}'"
    print("✅ Test 6 PASSED")
    
    # Test 7: Get required fields utility
    print("\n" + "-" * 80)
    print("Test 7: Get Required Fields Utility")
    print("-" * 80)
    
    pay_stub_fields = calculator.get_required_fields(DocumentType.PAY_STUB)
    bank_fields = calculator.get_required_fields(DocumentType.BANK_STATEMENT)
    
    print(f"✓ Pay stub required fields ({len(pay_stub_fields)}): {pay_stub_fields}")
    print(f"✓ Bank statement required fields ({len(bank_fields)}): {bank_fields}")
    
    assert len(pay_stub_fields) == 6, "Pay stub should have 6 required fields"
    assert len(bank_fields) == 6, "Bank statement should have 6 required fields"
    assert "employer_name" in pay_stub_fields
    assert "bank_name" in bank_fields
    print("✅ Test 7 PASSED")
    
    # Test 8: Handle null and empty string values
    print("\n" + "-" * 80)
    print("Test 8: Handle Null and Empty String Values")
    print("-" * 80)
    
    pay_stub_with_nulls = {
        "employer_name": "Acme Corporation",
        "employee_name": "",  # Empty string - should count as missing
        "gross_monthly_income": None,  # Null - should count as missing
        "net_monthly_income": 3800.00,
        "pay_period_start": "   ",  # Whitespace only - should count as missing
        "pay_period_end": "2025-01-15"
    }
    
    score, missing, quality = calculator.calculate_completeness(
        pay_stub_with_nulls,
        DocumentType.PAY_STUB
    )
    
    print(f"✓ Completeness: {score:.1f}%")
    print(f"✓ Quality: {quality}")
    print(f"✓ Missing fields: {missing}")
    
    assert score == 50.0, f"Expected 50%, got {score}%"  # 3 out of 6 fields
    assert "employee_name" in missing, "Empty string should be treated as missing"
    assert "gross_monthly_income" in missing, "Null should be treated as missing"
    assert "pay_period_start" in missing, "Whitespace should be treated as missing"
    print("✅ Test 8 PASSED")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✅ All 8 tests passed!")
    print("\nCompletenessCalculator capabilities verified:")
    print("  1. ✓ Calculate percentage completeness")
    print("  2. ✓ Identify missing required fields")
    print("  3. ✓ Provide quality assessments (excellent/good/partial/poor)")
    print("  4. ✓ Handle multiple document types")
    print("  5. ✓ Validate against required field schemas")
    print("  6. ✓ Handle null/empty/whitespace values correctly")
    print("  7. ✓ Utility method to get required fields")
    print("\nT021 Implementation: ✅ COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_completeness_calculator()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
