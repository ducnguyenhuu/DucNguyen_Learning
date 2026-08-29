"""
Example: Document Extraction with DocumentIntelligenceExtractor

This example demonstrates how to use the DocumentIntelligenceExtractor
to extract structured data from loan documents.

Usage:
    python examples/document_extraction_example.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import DocumentIntelligenceExtractor
from src.models import DocumentType


def example_basic_extraction():
    """Basic document extraction example."""
    print("=" * 60)
    print("Example 1: Basic Document Extraction")
    print("=" * 60)
    
    # Initialize extractor (uses credentials from .env)
    extractor = DocumentIntelligenceExtractor()
    
    # Extract data from a pay stub - using type-safe enum
    result = extractor.analyze_document(
        document_path="tests/sample_applications/pay_stub_clean.pdf",
        document_type=DocumentType.PAY_STUB,  # Type-safe enum!
        application_id="APP-2025-001"
    )
    
    print(f"✅ Extraction complete!")
    print(f"   Document ID: {result.document_id}")
    print(f"   Confidence: {result.confidence_score:.2%}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Fields extracted: {len(result.structured_data)}")
    
    # Display some extracted fields
    if result.structured_data:
        print(f"\n   Extracted fields:")
        for key, value in list(result.structured_data.items())[:5]:
            print(f"     • {key}: {value}")
    
    return result


def example_all_document_types():
    """Extract different document types."""
    print("\n" + "=" * 60)
    print("Example 2: Multiple Document Types")
    print("=" * 60)
    
    extractor = DocumentIntelligenceExtractor()
    
    # Documents to process with their types
    documents = [
        ("tests/sample_applications/pay_stub_clean.pdf", DocumentType.PAY_STUB),
        ("tests/sample_applications/bank_statement.pdf", DocumentType.BANK_STATEMENT),
        ("tests/sample_applications/drivers_license.pdf", DocumentType.DRIVERS_LICENSE),
    ]
    
    results = []
    for doc_path, doc_type in documents:
        if Path(doc_path).exists():
            result = extractor.analyze_document(
                document_path=doc_path,
                document_type=doc_type,  # Type-safe!
                application_id="APP-2025-002"
            )
            results.append(result)
            print(f"✅ {doc_type.value:20s} - Confidence: {result.confidence_score:.2%}")
        else:
            print(f"⚠️  {doc_path} not found, skipping")
    
    return results


def example_error_handling():
    """Demonstrate error handling."""
    print("\n" + "=" * 60)
    print("Example 3: Error Handling")
    print("=" * 60)
    
    extractor = DocumentIntelligenceExtractor()
    
    # Try to extract from non-existent file
    try:
        result = extractor.analyze_document(
            document_path="nonexistent.pdf",
            document_type=DocumentType.PAY_STUB,
            application_id="APP-2025-003"
        )
    except FileNotFoundError as e:
        print(f"✅ Correctly caught error: {e}")
    
    # Invalid document type (string instead of enum will still work)
    result = extractor.analyze_document(
        document_path="tests/sample_applications/pay_stub_clean.pdf",
        document_type="pay_stub",  # String also works (backward compatible)
        application_id="APP-2025-004"
    )
    print(f"✅ Backward compatible: String type also works")


def main():
    """Run all examples."""
    print("\n📚 Document Extraction Examples\n")
    
    try:
        # Example 1: Basic extraction
        example_basic_extraction()
        
        # Example 2: Multiple document types
        example_all_document_types()
        
        # Example 3: Error handling
        example_error_handling()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you have:")
        print("  1. Azure Document Intelligence credentials in .env")
        print("  2. Test PDFs in tests/sample_applications/")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
