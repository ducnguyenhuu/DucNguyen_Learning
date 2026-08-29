"""
Document Agent Integration Example (T018-T021)

This script demonstrates the complete document processing pipeline:
1. DocumentIntelligenceExtractor - Extract raw fields from PDF (T018)
2. FieldNormalizer - Normalize fields using GPT-4o (T019)
3. DataValidator - Validate business rules via YAML config (T020)
4. CompletenessCalculator - Score extraction completeness (T021)

Usage:
    python3 scripts/demo_document_agent_pipeline.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import CompletenessCalculator, DataValidator
from src.models import DocumentType


def demo_document_agent_pipeline():
    """Demonstrate the complete document processing pipeline"""
    
    print("\n" + "=" * 80)
    print("DOCUMENT AGENT PIPELINE DEMONSTRATION")
    print("=" * 80)
    print("\nThis demo shows how T018-T021 work together to process documents:")
    print("  T018: DocumentIntelligenceExtractor (requires Azure credentials)")
    print("  T019: FieldNormalizer (requires Azure OpenAI credentials)")
    print("  T020: DataValidator (YAML-based validation)")
    print("  T021: CompletenessCalculator (field completeness scoring)")
    
    # Simulate extracted and normalized data
    # In production, this would come from DocumentIntelligenceExtractor + FieldNormalizer
    print("\n" + "-" * 80)
    print("SIMULATED EXTRACTION & NORMALIZATION")
    print("-" * 80)
    print("(In production, Azure Document Intelligence + GPT-4o would extract this)")
    
    normalized_pay_stub = {
        "employer_name": "Acme Corporation",
        "employee_name": "Jane Doe",
        "gross_monthly_income": 5000.00,
        "net_monthly_income": 3800.00,
        "pay_period_start": "2025-01-01",
        "pay_period_end": "2025-01-15",
        "employer_address": "123 Main St, City, ST 12345",
        "ytd_gross": 60000.00,
        "ytd_taxes": 12000.00
    }
    
    print(f"\n📄 Normalized Pay Stub Data:")
    for key, value in normalized_pay_stub.items():
        print(f"  {key}: {value}")
    
    # Step 1: Validate using DataValidator (T020)
    print("\n" + "-" * 80)
    print("STEP 1: VALIDATION (T020 - DataValidator)")
    print("-" * 80)
    
    validator = DataValidator()
    is_valid, errors = validator.validate(normalized_pay_stub, DocumentType.PAY_STUB)
    
    if is_valid:
        print("✅ Validation: PASSED")
        print("   All business rules satisfied")
    else:
        print(f"❌ Validation: FAILED")
        print(f"   Errors found: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    
    # Step 2: Calculate completeness using CompletenessCalculator (T021)
    print("\n" + "-" * 80)
    print("STEP 2: COMPLETENESS SCORING (T021 - CompletenessCalculator)")
    print("-" * 80)
    
    calculator = CompletenessCalculator()
    score, missing, quality = calculator.calculate_completeness(
        normalized_pay_stub,
        DocumentType.PAY_STUB
    )
    
    print(f"📊 Completeness Score: {score:.1f}%")
    print(f"📊 Quality Assessment: {quality.upper()}")
    
    if missing:
        print(f"⚠️  Missing Required Fields: {', '.join(missing)}")
    else:
        print("✅ All Required Fields Present")
    
    required_fields = calculator.get_required_fields(DocumentType.PAY_STUB)
    print(f"\n📋 Required Fields ({len(required_fields)}):")
    for field in required_fields:
        status = "✓" if field in normalized_pay_stub else "✗"
        print(f"   {status} {field}")
    
    # Demonstrate different completeness scenarios
    print("\n" + "-" * 80)
    print("COMPLETENESS SCENARIOS")
    print("-" * 80)
    
    scenarios = [
        {
            "name": "Excellent (100%)",
            "data": normalized_pay_stub,
            "description": "All required fields present"
        },
        {
            "name": "Good (83%)",
            "data": {k: v for k, v in normalized_pay_stub.items() if k != "pay_period_end"},
            "description": "One field missing"
        },
        {
            "name": "Partial (67%)",
            "data": {
                "employer_name": "Acme Corp",
                "employee_name": "Jane Doe",
                "gross_monthly_income": 5000.00,
                "net_monthly_income": 3800.00
            },
            "description": "Two fields missing"
        },
        {
            "name": "Poor (33%)",
            "data": {
                "employer_name": "Acme Corp",
                "employee_name": "Jane Doe"
            },
            "description": "Most fields missing"
        }
    ]
    
    for scenario in scenarios:
        score, missing, quality = calculator.calculate_completeness(
            scenario["data"],
            DocumentType.PAY_STUB
        )
        print(f"\n  {scenario['name']}: {score:.0f}% - {quality.upper()}")
        print(f"    {scenario['description']}")
        if missing:
            print(f"    Missing: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}")
    
    # Summary
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print("\n✅ Document Agent Components Ready:")
    print("   [T018] DocumentIntelligenceExtractor - Extract from PDFs (requires Azure)")
    print("   [T019] FieldNormalizer - Normalize with GPT-4o (requires Azure OpenAI)")
    print("   [T020] DataValidator - YAML-based validation")
    print("   [T021] CompletenessCalculator - Field completeness scoring")
    
    print("\n📊 Pipeline Flow:")
    print("   PDF → DocumentIntelligence → Raw Fields")
    print("   Raw Fields → FieldNormalizer → Normalized Data")
    print("   Normalized Data → DataValidator → Validation Results")
    print("   Normalized Data → CompletenessCalculator → Completeness Score")
    
    print("\n🎯 Next Steps:")
    print("   - T022: Create interactive notebook demonstrating full pipeline")
    print("   - T023: Add JSON viewer for extracted data")
    print("   - T024: Implement cost logging")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        demo_document_agent_pipeline()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
