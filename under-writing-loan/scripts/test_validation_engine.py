"""
Test Rule-Based Validation Engine

This demonstrates the new configurable validation system where rules
are defined in YAML instead of hardcoded in Python.

Benefits:
- Add new rules by editing validation_rules.yaml
- No Python code changes needed
- Business users can configure rules
- Easy to audit and version control rules
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import ValidationRuleEngine
from src.models import DocumentType


def test_rule_based_validation():
    """Test the new rule-based validation engine"""
    
    print("\n" + "=" * 80)
    print("RULE-BASED VALIDATION ENGINE TEST")
    print("=" * 80)
    
    # Initialize engine (loads rules from YAML)
    engine = ValidationRuleEngine("src/validation_rules.yaml")
    
    print(f"\n✓ Engine initialized")
    print(f"  Rules file: src/validation_rules.yaml")
    
    # Test 1: Valid pay stub
    print("\n" + "-" * 80)
    print("TEST 1: Valid Pay Stub")
    print("-" * 80)
    
    valid_data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        "pay_period_start": "2024-01-01",
        "pay_period_end": "2024-01-15"
    }
    
    is_valid, errors = engine.validate(valid_data, DocumentType.PAY_STUB)
    
    print(f"Result: {'✅ PASS' if is_valid else '❌ FAIL'}")
    print(f"Errors: {len(errors)}")
    if errors:
        for error in errors:
            print(f"  - {error}")
    
    assert is_valid, "Valid data should pass"
    
    # Test 2: Invalid pay stub (net > gross)
    print("\n" + "-" * 80)
    print("TEST 2: Invalid Pay Stub - Rule PAY_001 (Net > Gross)")
    print("-" * 80)
    
    invalid_data = {
        "employer_name": "Acme Corporation",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 6000.00,  # INVALID!
        "pay_period_start": "2024-01-01",
        "pay_period_end": "2024-01-15"
    }
    
    is_valid, errors = engine.validate(invalid_data, DocumentType.PAY_STUB)
    
    print(f"Result: {'✅ PASS' if is_valid else '❌ FAIL (Expected)'}")
    print(f"Errors: {len(errors)}")
    for error in errors:
        print(f"  - {error}")
    
    assert not is_valid, "Invalid data should fail"
    assert any("PAY_001" in err for err in errors), "Should trigger PAY_001 rule"
    
    # Test 3: Bank statement with balance equation
    print("\n" + "-" * 80)
    print("TEST 3: Bank Statement - Rule BANK_002 (Balance Equation)")
    print("-" * 80)
    
    bank_data = {
        "bank_name": "Chase Bank",
        "statement_start_date": "2024-01-01",
        "statement_end_date": "2024-01-31",
        "beginning_balance": 1000.00,
        "total_deposits": 5000.00,
        "total_withdrawals": 3000.00,
        "ending_balance": 5000.00  # WRONG! Should be 3000
    }
    
    is_valid, errors = engine.validate(bank_data, DocumentType.BANK_STATEMENT)
    
    print(f"Result: {'✅ PASS' if is_valid else '❌ FAIL (Expected)'}")
    print(f"Errors: {len(errors)}")
    for error in errors:
        print(f"  - {error}")
    
    assert not is_valid, "Invalid balance should fail"
    assert any("BANK_002" in err for err in errors), "Should trigger BANK_002 rule"
    
    # Test 4: Demonstrate adding new rule
    print("\n" + "-" * 80)
    print("DEMONSTRATION: How to Add New Rules")
    print("-" * 80)
    
    print("""
To add a new validation rule, simply edit src/validation_rules.yaml:

Example - Add maximum income limit:

pay_stub:
  rules:
    - rule_id: PAY_006
      name: "Gross income below maximum"
      type: range
      fields:
        - gross_monthly_income
      min_value: 0
      max_value: 50000  # $50k/month cap
      error_message: "Gross income ({value}) exceeds maximum ($50,000)"
      severity: warning

Then reload the engine:
    engine.reload_rules()

No Python code changes needed! ✨
""")
    
    # Summary
    print("\n" + "=" * 80)
    print("BENEFITS OF RULE-BASED VALIDATION")
    print("=" * 80)
    print("""
1. ✅ Add rules without coding (edit YAML file)
2. ✅ Business users can configure rules
3. ✅ Easy to test rule changes (just edit config)
4. ✅ Version control for rules (Git tracks YAML changes)
5. ✅ Hot-reload in production (reload_rules() without restart)
6. ✅ Rule audit trail (who changed what, when)
7. ✅ Severity levels (critical, warning, info)
8. ✅ Flexible rule types (comparison, range, format, calculation)
""")
    
    print("\n✅ ALL TESTS PASSED!\n")


if __name__ == "__main__":
    test_rule_based_validation()
