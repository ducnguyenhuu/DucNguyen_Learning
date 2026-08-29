"""
Full Document Processing Pipeline - T018 + T019 + T020 Integration

This example demonstrates the complete document processing workflow:
1. T018: Extract raw data from PDF using Azure Document Intelligence
2. T019: Normalize fields using GPT-4o text processing
3. T020: Validate normalized data against business rules

The pipeline showcases:
- End-to-end document processing
- Error detection and reporting
- Data quality assurance
- Cost tracking across all operations

Task: Integration example for T018 + T019 + T020
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.document_agent import (
    DocumentIntelligenceExtractor,
    FieldNormalizer,
    DataValidator
)
from src.models import DocumentType


def process_document(pdf_path: str, document_type: DocumentType):
    """
    Process a document through the full pipeline.
    
    Args:
        pdf_path: Path to PDF document
        document_type: Type of document (PAY_STUB, BANK_STATEMENT, etc.)
    """
    print("\n" + "=" * 80)
    print(f"PROCESSING DOCUMENT: {Path(pdf_path).name}")
    print(f"Document Type: {document_type.value}")
    print("=" * 80)
    
    # Step 1: Extract raw data using Azure Document Intelligence
    print("\n📄 STEP 1: EXTRACTION (T018 - Azure Document Intelligence)")
    print("-" * 80)
    
    extractor = DocumentIntelligenceExtractor()
    raw_data, confidence = extractor.analyze_document(pdf_path)
    
    print(f"✓ Extraction complete")
    print(f"  Fields extracted: {len(raw_data)}")
    print(f"  Average confidence: {confidence:.2%}")
    print(f"\n  Raw data sample:")
    for key, value in list(raw_data.items())[:5]:
        print(f"    {key}: {value}")
    if len(raw_data) > 5:
        print(f"    ... and {len(raw_data) - 5} more fields")
    
    # Step 2: Normalize using GPT-4o
    print("\n🤖 STEP 2: NORMALIZATION (T019 - GPT-4o Text Processing)")
    print("-" * 80)
    
    normalizer = FieldNormalizer()
    normalized_data, prompt_tokens, completion_tokens = normalizer.normalize(
        raw_data=raw_data,
        document_type=document_type,
        document_id="demo_document"
    )
    
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost = (prompt_tokens * 0.00015 / 1000) + (completion_tokens * 0.0006 / 1000)
    
    print(f"✓ Normalization complete")
    print(f"  Token usage: {total_tokens:,} tokens ({prompt_tokens:,} prompt + {completion_tokens:,} completion)")
    print(f"  Estimated cost: ${estimated_cost:.6f}")
    print(f"\n  Normalized data sample:")
    for key, value in list(normalized_data.items())[:5]:
        print(f"    {key}: {value}")
    if len(normalized_data) > 5:
        print(f"    ... and {len(normalized_data) - 5} more fields")
    
    # Step 3: Validate business rules
    print("\n✅ STEP 3: VALIDATION (T020 - Business Rules)")
    print("-" * 80)
    
    validator = DataValidator()
    is_valid, errors = validator.validate(normalized_data, document_type)
    
    if is_valid:
        print(f"✓ Validation PASSED - All business rules satisfied")
        print(f"  Document is ready for risk assessment")
    else:
        print(f"✗ Validation FAILED - {len(errors)} error(s) detected:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print(f"\n  ⚠️  Document requires manual review before proceeding")
    
    # Summary
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Document: {Path(pdf_path).name}")
    print(f"Type: {document_type.value}")
    print(f"Extracted fields: {len(raw_data)}")
    print(f"Normalized fields: {len(normalized_data)}")
    print(f"Extraction confidence: {confidence:.2%}")
    print(f"Validation status: {'✅ PASS' if is_valid else '❌ FAIL'}")
    print(f"Total cost: ~${estimated_cost:.6f}")
    print("=" * 80)
    
    return {
        "raw_data": raw_data,
        "normalized_data": normalized_data,
        "is_valid": is_valid,
        "errors": errors,
        "confidence": confidence,
        "tokens": total_tokens,
        "cost": estimated_cost
    }


def demonstrate_validation_scenarios():
    """Demonstrate validation with different data scenarios"""
    print("\n\n" + "=" * 80)
    print("VALIDATION SCENARIOS DEMONSTRATION")
    print("=" * 80)
    
    validator = DataValidator()
    
    scenarios = [
        {
            "name": "Valid Pay Stub",
            "data": {
                "employer_name": "Acme Corporation",
                "gross_monthly_income": 5000.00,
                "net_monthly_income": 3800.00,
                "pay_period_start": "2024-01-01",
                "pay_period_end": "2024-01-15"
            },
            "type": DocumentType.PAY_STUB,
            "expected": "PASS"
        },
        {
            "name": "Invalid Pay Stub - Net > Gross",
            "data": {
                "employer_name": "Acme Corporation",
                "gross_monthly_income": 5000.00,
                "net_monthly_income": 6000.00,  # Fraud indicator!
                "pay_period_start": "2024-01-01",
                "pay_period_end": "2024-01-15"
            },
            "type": DocumentType.PAY_STUB,
            "expected": "FAIL"
        },
        {
            "name": "Invalid Pay Stub - Dates Out of Order",
            "data": {
                "employer_name": "Acme Corporation",
                "gross_monthly_income": 5000.00,
                "net_monthly_income": 3800.00,
                "pay_period_start": "2024-01-15",
                "pay_period_end": "2024-01-01"  # End before start!
            },
            "type": DocumentType.PAY_STUB,
            "expected": "FAIL"
        },
        {
            "name": "Valid Bank Statement",
            "data": {
                "bank_name": "Chase Bank",
                "statement_start_date": "2024-01-01",
                "statement_end_date": "2024-01-31",
                "beginning_balance": 1000.00,
                "total_deposits": 5000.00,
                "total_withdrawals": 3000.00,
                "ending_balance": 3000.00  # 1000 + 5000 - 3000 = 3000
            },
            "type": DocumentType.BANK_STATEMENT,
            "expected": "PASS"
        },
        {
            "name": "Invalid Bank Statement - Balance Mismatch",
            "data": {
                "bank_name": "Chase Bank",
                "statement_start_date": "2024-01-01",
                "statement_end_date": "2024-01-31",
                "beginning_balance": 1000.00,
                "total_deposits": 5000.00,
                "total_withdrawals": 3000.00,
                "ending_balance": 5000.00  # Should be 3000!
            },
            "type": DocumentType.BANK_STATEMENT,
            "expected": "FAIL"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{'=' * 80}")
        print(f"Scenario: {scenario['name']}")
        print(f"Expected: {scenario['expected']}")
        print("-" * 80)
        
        is_valid, errors = validator.validate(scenario["data"], scenario["type"])
        
        actual = "PASS" if is_valid else "FAIL"
        match = "✓" if actual == scenario["expected"] else "✗"
        
        print(f"\nResult: {actual} {match}")
        if errors:
            print(f"Errors ({len(errors)}):")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
        else:
            print("No errors - document is valid")
    
    print("\n" + "=" * 80)
    print("VALIDATION SCENARIOS COMPLETE")
    print("=" * 80)


def main():
    """Run full pipeline demonstration"""
    print("\n" + "=" * 80)
    print("FULL DOCUMENT PROCESSING PIPELINE")
    print("T018 (Extraction) + T019 (Normalization) + T020 (Validation)")
    print("=" * 80)
    
    # Check for test documents
    test_docs_dir = Path("tests/test_documents")
    pay_stub_path = test_docs_dir / "pay_stub_clean.pdf"
    
    if pay_stub_path.exists():
        # Process real document
        result = process_document(
            pdf_path=str(pay_stub_path),
            document_type=DocumentType.PAY_STUB
        )
        
        print("\n\n📊 BENEFITS OF THIS PIPELINE:")
        print("-" * 80)
        print("1. AUTOMATION: No manual data entry - saves hours per document")
        print("2. ACCURACY: GPT-4o normalizes inconsistent formats automatically")
        print("3. QUALITY: Validation catches errors before risk assessment")
        print("4. COST: ~$0.001-0.002 per document (extremely affordable)")
        print("5. SPEED: Full pipeline completes in seconds")
        print("6. COMPLIANCE: Automated audit trail of extraction + validation")
    else:
        print(f"\n⚠️  Test document not found: {pay_stub_path}")
        print("Skipping real document processing...")
    
    # Always demonstrate validation scenarios
    demonstrate_validation_scenarios()
    
    print("\n\n" + "=" * 80)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("• T018: Azure DI extracts raw data with high confidence")
    print("• T019: GPT-4o normalizes fields intelligently")
    print("• T020: Validation ensures data quality before risk assessment")
    print("• Pipeline is production-ready for loan underwriting")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
