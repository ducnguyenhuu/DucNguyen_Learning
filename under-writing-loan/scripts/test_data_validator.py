"""
Test DataValidator implementation.

This script tests T020 validation rules:
- Net income <= Gross income (pay stubs)
- Dates are chronological
- Amounts are non-negative
- Required field consistency checks
- SSN/EIN format validation

Task: T020 - Test validation rules
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.document_agent import DataValidator
from src.models import DocumentType


def test_1_initialization():
    """Test 1: DataValidator initializes successfully"""
    print("=" * 70)
    print("TEST 1: DataValidator Initialization")
    print("=" * 70)
    
    validator = DataValidator()
    print(f"✓ DataValidator initialized")
    print(f"  Type: {type(validator)}")
    print(f"  Has validate method: {hasattr(validator, 'validate')}")
    
    print("\nTEST 1: ✅ PASS\n")


def test_2_pay_stub_valid():
    """Test 2: Valid pay stub passes validation"""
    print("=" * 70)
    print("TEST 2: Valid Pay Stub")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Valid pay stub data
    data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,  # Valid: net < gross
        "pay_period_start": "2024-01-01",
        "pay_period_end": "2024-01-15",  # Valid: end > start
        "ytd_gross": 5000.00,  # First pay stub of year
        "employee_name": "John Doe"
    }
    
    is_valid, errors = validator.validate(data, DocumentType.PAY_STUB)
    
    print(f"Input data:")
    print(f"  Gross: ${data['gross_monthly_income']:.2f}")
    print(f"  Net: ${data['net_monthly_income']:.2f}")
    print(f"  Period: {data['pay_period_start']} to {data['pay_period_end']}")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors: {errors if errors else 'None'}")
    
    assert is_valid, f"Expected valid, got errors: {errors}"
    assert len(errors) == 0, f"Expected no errors, got {len(errors)}"
    
    print("\nTEST 2: ✅ PASS\n")


def test_3_pay_stub_net_exceeds_gross():
    """Test 3: Invalid pay stub - net > gross"""
    print("=" * 70)
    print("TEST 3: Invalid Pay Stub - Net Exceeds Gross")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: net > gross (fraud indicator!)
    data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 6000.00,  # INVALID!
        "pay_period_start": "2024-01-01",
        "pay_period_end": "2024-01-15"
    }
    
    is_valid, errors = validator.validate(data, DocumentType.PAY_STUB)
    
    print(f"Input data:")
    print(f"  Gross: ${data['gross_monthly_income']:.2f}")
    print(f"  Net: ${data['net_monthly_income']:.2f} 🚨 INVALID!")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    assert any("exceeds" in err.lower() for err in errors), "Expected 'exceeds' in error message"
    
    print("\nTEST 3: ✅ PASS\n")


def test_4_pay_stub_invalid_dates():
    """Test 4: Invalid pay stub - start date after end date"""
    print("=" * 70)
    print("TEST 4: Invalid Pay Stub - Dates Out of Order")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: start > end
    data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        "pay_period_start": "2024-01-15",  # AFTER end date!
        "pay_period_end": "2024-01-01"     # BEFORE start date!
    }
    
    is_valid, errors = validator.validate(data, DocumentType.PAY_STUB)
    
    print(f"Input data:")
    print(f"  Start: {data['pay_period_start']}")
    print(f"  End: {data['pay_period_end']} 🚨 BEFORE START!")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    assert any("pay period" in err.lower() for err in errors), "Expected date error"
    
    print("\nTEST 4: ✅ PASS\n")


def test_5_bank_statement_valid():
    """Test 5: Valid bank statement passes validation"""
    print("=" * 70)
    print("TEST 5: Valid Bank Statement")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Valid bank statement with balance equation
    data = {
        "bank_name": "Chase Bank",
        "statement_start_date": "2024-01-01",
        "statement_end_date": "2024-01-31",
        "beginning_balance": 1000.00,
        "total_deposits": 5000.00,
        "total_withdrawals": 3000.00,
        "ending_balance": 3000.00  # 1000 + 5000 - 3000 = 3000 ✓
    }
    
    is_valid, errors = validator.validate(data, DocumentType.BANK_STATEMENT)
    
    print(f"Input data:")
    print(f"  Period: {data['statement_start_date']} to {data['statement_end_date']}")
    print(f"  Beginning: ${data['beginning_balance']:.2f}")
    print(f"  + Deposits: ${data['total_deposits']:.2f}")
    print(f"  - Withdrawals: ${data['total_withdrawals']:.2f}")
    print(f"  = Ending: ${data['ending_balance']:.2f} ✓")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors: {errors if errors else 'None'}")
    
    assert is_valid, f"Expected valid, got errors: {errors}"
    
    print("\nTEST 5: ✅ PASS\n")


def test_6_bank_statement_invalid_balance():
    """Test 6: Invalid bank statement - balance equation doesn't match"""
    print("=" * 70)
    print("TEST 6: Invalid Bank Statement - Balance Mismatch")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: ending balance doesn't match equation
    data = {
        "bank_name": "Chase Bank",
        "statement_start_date": "2024-01-01",
        "statement_end_date": "2024-01-31",
        "beginning_balance": 1000.00,
        "total_deposits": 5000.00,
        "total_withdrawals": 3000.00,
        "ending_balance": 5000.00  # WRONG! Should be 3000
    }
    
    is_valid, errors = validator.validate(data, DocumentType.BANK_STATEMENT)
    
    calculated = data['beginning_balance'] + data['total_deposits'] - data['total_withdrawals']
    print(f"Input data:")
    print(f"  Beginning: ${data['beginning_balance']:.2f}")
    print(f"  + Deposits: ${data['total_deposits']:.2f}")
    print(f"  - Withdrawals: ${data['total_withdrawals']:.2f}")
    print(f"  = Expected: ${calculated:.2f}")
    print(f"  Actual ending: ${data['ending_balance']:.2f} 🚨 MISMATCH!")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    assert any("inconsistent" in err.lower() for err in errors), "Expected balance inconsistency error"
    
    print("\nTEST 6: ✅ PASS\n")


def test_7_tax_return_valid():
    """Test 7: Valid tax return passes validation"""
    print("=" * 70)
    print("TEST 7: Valid Tax Return")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Valid tax return
    data = {
        "taxpayer_name": "John Doe",
        "tax_year": "2023",
        "wages_annual": 60000.00,
        "wages_monthly": 5000.00,  # 60000 / 12 = 5000 ✓
        "federal_tax_withheld": 12000.00
    }
    
    is_valid, errors = validator.validate(data, DocumentType.TAX_RETURN)
    
    print(f"Input data:")
    print(f"  Tax year: {data['tax_year']}")
    print(f"  Annual wages: ${data['wages_annual']:.2f}")
    print(f"  Monthly wages: ${data['wages_monthly']:.2f}")
    print(f"  Calculation: ${data['wages_annual']:.2f} / 12 = ${data['wages_monthly']:.2f} ✓")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors: {errors if errors else 'None'}")
    
    assert is_valid, f"Expected valid, got errors: {errors}"
    
    print("\nTEST 7: ✅ PASS\n")


def test_8_tax_return_invalid_calculation():
    """Test 8: Invalid tax return - wrong monthly calculation"""
    print("=" * 70)
    print("TEST 8: Invalid Tax Return - Wrong Monthly Calculation")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: monthly doesn't match annual / 12
    data = {
        "taxpayer_name": "John Doe",
        "tax_year": "2023",
        "wages_annual": 60000.00,
        "wages_monthly": 6000.00,  # WRONG! Should be 5000
        "federal_tax_withheld": 12000.00
    }
    
    is_valid, errors = validator.validate(data, DocumentType.TAX_RETURN)
    
    expected_monthly = data['wages_annual'] / 12
    print(f"Input data:")
    print(f"  Annual wages: ${data['wages_annual']:.2f}")
    print(f"  Expected monthly: ${expected_monthly:.2f}")
    print(f"  Actual monthly: ${data['wages_monthly']:.2f} 🚨 MISMATCH!")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    
    print("\nTEST 8: ✅ PASS\n")


def test_9_drivers_license_valid():
    """Test 9: Valid driver's license passes validation"""
    print("=" * 70)
    print("TEST 9: Valid Driver's License")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Valid driver's license
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-05-15",  # 34 years old
        "license_number": "D1234567",
        "issue_date": "2020-06-01",
        "expiration_date": "2026-06-01"  # Valid for 6 years
    }
    
    is_valid, errors = validator.validate(data, DocumentType.DRIVERS_LICENSE)
    
    print(f"Input data:")
    print(f"  Name: {data['first_name']} {data['last_name']}")
    print(f"  DOB: {data['date_of_birth']} (age ~34)")
    print(f"  Issue: {data['issue_date']}")
    print(f"  Expires: {data['expiration_date']}")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors: {errors if errors else 'None'}")
    
    assert is_valid, f"Expected valid, got errors: {errors}"
    
    print("\nTEST 9: ✅ PASS\n")


def test_10_drivers_license_invalid_age():
    """Test 10: Invalid driver's license - future DOB (age < 16)"""
    print("=" * 70)
    print("TEST 10: Invalid Driver's License - Too Young")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: DOB makes person too young (or in future!)
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "2020-05-15",  # Only 4 years old!
        "license_number": "D1234567",
        "issue_date": "2020-06-01",
        "expiration_date": "2026-06-01"
    }
    
    is_valid, errors = validator.validate(data, DocumentType.DRIVERS_LICENSE)
    
    print(f"Input data:")
    print(f"  DOB: {data['date_of_birth']} 🚨 TOO YOUNG!")
    print(f"  Issue: {data['issue_date']}")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    
    print("\nTEST 10: ✅ PASS\n")


def test_11_ssn_validation():
    """Test 11: SSN format validation"""
    print("=" * 70)
    print("TEST 11: SSN Format Validation")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Test various SSN formats
    test_cases = [
        # (data, should_be_valid, description)
        ({"employee_ssn": "123-45-6789"}, True, "Valid: XXX-XX-XXXX"),
        ({"employee_ssn": "123456789"}, True, "Valid: 9 digits"),
        ({"employee_ssn": "***-**-1234"}, True, "Valid: Masked with last 4"),
        ({"employee_ssn": "1234"}, True, "Valid: Last 4 only"),
        ({"employee_ssn": "12-34-567"}, False, "Invalid: Wrong format"),
        ({"employee_ssn": "abc-de-fghi"}, False, "Invalid: Letters"),
    ]
    
    passed = 0
    failed = 0
    
    for data, should_be_valid, description in test_cases:
        is_valid, errors = validator.validate(data, DocumentType.PAY_STUB)
        
        # Check if SSN validation worked as expected
        has_ssn_error = any("SSN" in err or "ssn" in err for err in errors)
        
        if should_be_valid:
            # Should NOT have SSN error
            if not has_ssn_error:
                print(f"  ✓ {description}: {data['employee_ssn']}")
                passed += 1
            else:
                print(f"  ✗ {description}: {data['employee_ssn']} - Unexpected error: {errors}")
                failed += 1
        else:
            # SHOULD have SSN error
            if has_ssn_error:
                print(f"  ✓ {description}: {data['employee_ssn']} - Correctly rejected")
                passed += 1
            else:
                print(f"  ✗ {description}: {data['employee_ssn']} - Should have failed")
                failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    assert failed == 0, f"{failed} SSN validation tests failed"
    
    print("\nTEST 11: ✅ PASS\n")


def test_12_negative_amounts():
    """Test 12: Negative amounts are caught"""
    print("=" * 70)
    print("TEST 12: Negative Amounts Detection")
    print("=" * 70)
    
    validator = DataValidator()
    
    # Invalid: negative income
    data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": -5000.00,  # INVALID!
        "net_monthly_income": 3800.00,
        "pay_period_start": "2024-01-01",
        "pay_period_end": "2024-01-15"
    }
    
    is_valid, errors = validator.validate(data, DocumentType.PAY_STUB)
    
    print(f"Input data:")
    print(f"  Gross: ${data['gross_monthly_income']:.2f} 🚨 NEGATIVE!")
    print(f"\nValidation result:")
    print(f"  Is valid: {is_valid}")
    print(f"  Errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"    {i}. {error}")
    
    assert not is_valid, "Expected invalid result"
    assert len(errors) > 0, "Expected at least one error"
    assert any("negative" in err.lower() for err in errors), "Expected 'negative' in error"
    
    print("\nTEST 12: ✅ PASS\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("DATAVALIDATOR TEST SUITE - T020")
    print("Testing validation rules for all document types")
    print("=" * 70 + "\n")
    
    tests = [
        test_1_initialization,
        test_2_pay_stub_valid,
        test_3_pay_stub_net_exceeds_gross,
        test_4_pay_stub_invalid_dates,
        test_5_bank_statement_valid,
        test_6_bank_statement_invalid_balance,
        test_7_tax_return_valid,
        test_8_tax_return_invalid_calculation,
        test_9_drivers_license_valid,
        test_10_drivers_license_invalid_age,
        test_11_ssn_validation,
        test_12_negative_amounts,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ TEST ERROR: {e}\n")
            failed += 1
    
    # Summary
    print("=" * 70)
    print(f"TEST SUMMARY")
    print("=" * 70)
    print(f"Total tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success rate: {passed / len(tests) * 100:.1f}%")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! T020 DataValidator is working correctly.\n")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.\n")
        return 1


if __name__ == "__main__":
    exit(main())
