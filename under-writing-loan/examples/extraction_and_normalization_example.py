"""
Example: Complete Document Processing Pipeline (T018 + T019)

This example demonstrates the full extraction and normalization workflow:
1. DocumentIntelligenceExtractor extracts raw fields from PDF
2. FieldNormalizer cleans and standardizes the data
3. Result is ready for downstream agents (Risk, Compliance, Decision)

Usage:
    python examples/extraction_and_normalization_example.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.document_agent import DocumentIntelligenceExtractor, FieldNormalizer
from src.models import DocumentType


def process_document(document_path: str, document_type: DocumentType):
    """
    Complete processing pipeline: Extract → Normalize.
    
    Args:
        document_path: Path to PDF file
        document_type: Type of document
    """
    print("=" * 70)
    print(f"Processing: {Path(document_path).name}")
    print(f"Type: {document_type.value}")
    print("=" * 70)
    
    # Step 1: Extract raw fields using Azure Document Intelligence
    print("\n📄 Step 1: Azure Document Intelligence Extraction")
    print("-" * 70)
    
    extractor = DocumentIntelligenceExtractor()
    extracted_doc = extractor.analyze_document(
        document_path=document_path,
        document_type=document_type,
        application_id="EXAMPLE-001"
    )
    
    print(f"✅ Extraction complete")
    print(f"   Method: {extracted_doc.extraction_method}")
    print(f"   Confidence: {extracted_doc.confidence_score:.2f}")
    print(f"   Raw fields extracted: {len(extracted_doc.structured_data)}")
    print(f"\n   Raw data sample:")
    for key, value in list(extracted_doc.structured_data.items())[:5]:
        print(f"   - {key}: {value}")
    
    # Step 2: Normalize fields using GPT-4o
    print(f"\n🤖 Step 2: GPT-4o Field Normalization")
    print("-" * 70)
    
    normalizer = FieldNormalizer()
    normalized_data, prompt_tokens, completion_tokens = normalizer.normalize(
        raw_data=extracted_doc.structured_data,
        document_type=document_type,
        document_id=extracted_doc.document_id
    )
    
    total_tokens = prompt_tokens + completion_tokens
    cost_estimate = (prompt_tokens * 0.00015 + completion_tokens * 0.0006) / 1000  # GPT-4o pricing
    
    print(f"✅ Normalization complete")
    print(f"   Token usage: {total_tokens} tokens")
    print(f"   Cost estimate: ${cost_estimate:.4f}")
    print(f"   Normalized fields: {len(normalized_data)}")
    print(f"\n   Normalized data:")
    for key, value in normalized_data.items():
        print(f"   - {key}: {value}")
    
    # Step 3: Show transformation comparison
    print(f"\n🔄 Transformation Comparison")
    print("-" * 70)
    print("Before (Raw) → After (Normalized)")
    print()
    
    # Find matching transformations
    transformations = [
        ("VendorName", "employer_name", "Field name unified"),
        ("InvoiceTotal", "gross_monthly_income", "Monetary value cleaned"),
        ("InvoiceDate", "pay_date", "Date standardized"),
        ("CustomerName", "employee_name", "Name title-cased"),
    ]
    
    for raw_key, norm_key, description in transformations:
        if raw_key in extracted_doc.structured_data and norm_key in normalized_data:
            raw_val = extracted_doc.structured_data[raw_key]
            norm_val = normalized_data[norm_key]
            print(f"✓ {raw_key}: '{raw_val}'")
            print(f"  → {norm_key}: '{norm_val}'")
            print(f"  ({description})")
            print()
    
    print("\n✅ Pipeline complete! Data ready for Risk Agent.")
    print()


def main():
    """Run extraction and normalization examples."""
    print("\n" + "🔧" * 35)
    print("DOCUMENT PROCESSING PIPELINE EXAMPLE")
    print("Demonstrates: T018 (Extraction) + T019 (Normalization)")
    print("🔧" * 35 + "\n")
    
    # Example 1: Pay stub
    pay_stub_path = "tests/sample_applications/pay_stub_clean.pdf"
    
    if Path(pay_stub_path).exists():
        process_document(pay_stub_path, DocumentType.PAY_STUB)
    else:
        print(f"⚠️  Sample file not found: {pay_stub_path}")
        print("   Run test data generation first")
    
    print("\n" + "=" * 70)
    print("💡 Key Benefits of Two-Stage Processing:")
    print("=" * 70)
    print("""
1. **Separation of Concerns**:
   - Azure DI handles OCR and basic field extraction
   - GPT-4o handles intelligent normalization and calculations

2. **Cost Optimization**:
   - DI: ~$0.001/page (cheap, fast)
   - GPT-4o: ~$0.005/document (only for normalization)
   - Total: ~$0.006/document vs $0.03 if using Vision for everything

3. **Adaptability**:
   - DI extracts what it can from prebuilt models
   - GPT-4o adapts to variations and calculates derived values
   - Pipeline handles messy real-world documents gracefully

4. **Quality**:
   - Structured data ready for downstream agents
   - Consistent schemas regardless of document template
   - Confidence tracking at both extraction and normalization stages
    """)
    
    print("\n📚 Next Steps:")
    print("   - T020: Add DataValidator for consistency checks")
    print("   - T021: Add CompletenessCalculator for quality scoring")
    print("   - Then: Ready for notebooks/01_document_agent.ipynb demo")


if __name__ == "__main__":
    main()
