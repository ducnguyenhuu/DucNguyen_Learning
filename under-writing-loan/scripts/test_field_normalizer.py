"""
Test script for FieldNormalizer class.

This script validates T019 implementation:
- GPT-4o normalization of extracted fields
- Field name unification
- Date standardization
- Monetary value cleaning
- Annual to monthly calculation

Usage:
    python3 scripts/test_field_normalizer.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.document_agent import FieldNormalizer
from src.models import DocumentType
from src.utils import config


def test_initialization():
    """Test 1: Validate FieldNormalizer initializes correctly."""
    print("=" * 60)
    print("Test 1: FieldNormalizer Initialization")
    print("=" * 60)
    
    try:
        normalizer = FieldNormalizer()
        print(f"✅ Normalizer initialized successfully")
        print(f"   Endpoint: {normalizer.endpoint}")
        print(f"   Deployment: {normalizer.deployment}")
        return True
    except Exception as e:
        print(f"❌ Initialization failed: {str(e)}")
        return False


def test_pay_stub_normalization():
    """Test 2: Normalize pay stub fields."""
    print("\n" + "=" * 60)
    print("Test 2: Pay Stub Normalization")
    print("=" * 60)
    
    # Simulate raw extraction from Document Intelligence (invoice model)
    raw_data = {
        "VendorName": "ACME CORPORATION",
        "CustomerName": "JANE DOE",
        "InvoiceTotal": "$5,000.00",
        "InvoiceDate": "2025-01-15",
        "Items": [
            {"Description": "Gross Pay", "Amount": "$5,000.00"},
            {"Description": "Federal Tax", "Amount": "$800.00"},
            {"Description": "State Tax", "Amount": "$300.00"},
            {"Description": "Net Pay", "Amount": "$3,900.00"}
        ]
    }
    
    print(f"\n📄 Raw extracted data:")
    print(f"   VendorName: {raw_data['VendorName']}")
    print(f"   InvoiceTotal: {raw_data['InvoiceTotal']}")
    print(f"   InvoiceDate: {raw_data['InvoiceDate']}")
    
    try:
        normalizer = FieldNormalizer()
        normalized, prompt_tokens, completion_tokens = normalizer.normalize(
            raw_data,
            DocumentType.PAY_STUB,
            "TEST-001"
        )
        
        print(f"\n✅ Normalization successful!")
        print(f"   Token usage: {prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total")
        print(f"\n📊 Normalized data:")
        for key, value in normalized.items():
            print(f"   {key}: {value}")
        
        # Validate key transformations
        checks = []
        if "employer_name" in normalized:
            checks.append("✅ VendorName → employer_name")
        if "gross_monthly_income" in normalized:
            checks.append("✅ InvoiceTotal → gross_monthly_income")
        if isinstance(normalized.get("gross_monthly_income"), (int, float)):
            checks.append("✅ Cleaned monetary value (removed $, comma)")
        if "pay_date" in normalized or "pay_period_end" in normalized:
            checks.append("✅ Date field present")
        
        print(f"\n🔍 Validation checks:")
        for check in checks:
            print(f"   {check}")
        
        return len(checks) >= 3
        
    except Exception as e:
        print(f"❌ Normalization failed: {str(e)}")
        return False


def test_bank_statement_normalization():
    """Test 3: Normalize bank statement fields (same DI model, different document type)."""
    print("\n" + "=" * 60)
    print("Test 3: Bank Statement Normalization")
    print("=" * 60)
    
    # Same invoice model fields, but different document type!
    raw_data = {
        "VendorName": "Chase Bank",
        "CustomerName": "John Smith",
        "InvoiceTotal": "$12,350.45",
        "InvoiceDate": "2025-01-31"
    }
    
    print(f"\n📄 Raw extracted data:")
    print(f"   VendorName: {raw_data['VendorName']}")
    print(f"   InvoiceTotal: {raw_data['InvoiceTotal']}")
    
    try:
        normalizer = FieldNormalizer()
        normalized, prompt_tokens, completion_tokens = normalizer.normalize(
            raw_data,
            DocumentType.BANK_STATEMENT,  # Different context!
            "TEST-002"
        )
        
        print(f"\n✅ Normalization successful!")
        print(f"   Token usage: {prompt_tokens + completion_tokens} total")
        print(f"\n📊 Normalized data:")
        for key, value in normalized.items():
            print(f"   {key}: {value}")
        
        # Validate context-aware mapping
        checks = []
        if "bank_name" in normalized:
            checks.append("✅ VendorName → bank_name (NOT employer_name)")
        if "ending_balance" in normalized or "account_balance" in normalized:
            checks.append("✅ InvoiceTotal → ending_balance (NOT income)")
        if "account_holder_name" in normalized:
            checks.append("✅ CustomerName → account_holder_name")
        
        print(f"\n🔍 Context-aware mapping:")
        for check in checks:
            print(f"   {check}")
        
        return len(checks) >= 2
        
    except Exception as e:
        print(f"❌ Normalization failed: {str(e)}")
        return False


def test_annual_to_monthly_calculation():
    """Test 4: Verify annual to monthly income calculation."""
    print("\n" + "=" * 60)
    print("Test 4: Annual to Monthly Calculation")
    print("=" * 60)
    
    # Tax return with annual wages
    raw_data = {
        "WagesAmount": "$60,000.00",
        "EmployerEIN": "12-3456789",
        "EmployeeSSN": "***-**-1234",
        "FederalTaxWithheld": "$9,000.00"
    }
    
    print(f"\n📄 Raw extracted data:")
    print(f"   WagesAmount: {raw_data['WagesAmount']} (annual)")
    
    try:
        normalizer = FieldNormalizer()
        normalized, prompt_tokens, completion_tokens = normalizer.normalize(
            raw_data,
            DocumentType.TAX_RETURN,
            "TEST-003"
        )
        
        print(f"\n✅ Normalization successful!")
        print(f"\n📊 Normalized data:")
        for key, value in normalized.items():
            print(f"   {key}: {value}")
        
        # Check for monthly calculation
        if "wages_monthly" in normalized:
            monthly = normalized["wages_monthly"]
            expected = 60000 / 12  # 5000
            if abs(monthly - expected) < 1:  # Allow small float differences
                print(f"\n✅ Annual to monthly calculation correct: ${monthly:.2f} ≈ ${expected:.2f}")
                return True
        
        print(f"\n⚠️  Monthly calculation field not found or incorrect")
        return False
        
    except Exception as e:
        print(f"❌ Normalization failed: {str(e)}")
        return False


def main():
    """Run all FieldNormalizer tests."""
    print("\n" + "🧪" * 30)
    print("FIELD NORMALIZER TEST SUITE (T019)")
    print("🧪" * 30 + "\n")
    
    # Check Azure OpenAI credentials
    if not config.validate_azure_openai():
        print("⚠️  Azure OpenAI credentials not configured")
        print("   Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env")
        print("   Skipping tests that require API access\n")
        
        # Can still test initialization
        result1 = False
        try:
            normalizer = FieldNormalizer()
            result1 = True
        except ValueError:
            result1 = False
        
        results = [result1]
    else:
        # Run all tests
        result1 = test_initialization()
        result2 = test_pay_stub_normalization()
        result3 = test_bank_statement_normalization()
        result4 = test_annual_to_monthly_calculation()
        
        results = [result1, result2, result3, result4]
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if result1:
        print("✅ PASS - Initialization")
    else:
        print("❌ FAIL - Initialization")
    
    if len(results) > 1:
        if results[1]:
            print("✅ PASS - Pay Stub Normalization")
        else:
            print("❌ FAIL - Pay Stub Normalization")
        
        if results[2]:
            print("✅ PASS - Bank Statement Context Awareness")
        else:
            print("❌ FAIL - Bank Statement Context Awareness")
        
        if results[3]:
            print("✅ PASS - Annual to Monthly Calculation")
        else:
            print("❌ FAIL - Annual to Monthly Calculation")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
