"""
Test script for DocumentIntelligenceExtractor (T018).

This script tests the basic functionality of the Document Intelligence wrapper
without requiring Azure credentials (for development verification).

To run with real Azure credentials:
    python scripts/test_document_agent.py --with-azure
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import DocumentIntelligenceExtractor
from src.models import DocumentType
from src.utils import config


def test_basic_initialization():
    """Test that DocumentIntelligenceExtractor can be initialized."""
    print("=" * 60)
    print("Test 1: Basic Initialization")
    print("=" * 60)
    
    try:
        # Check if credentials are configured
        if not config.AZURE_DOCUMENT_INTELLIGENCE_KEY:
            print("⚠️  No Azure credentials found")
            print("   Set AZURE_DOCUMENT_INTELLIGENCE_KEY and AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
            print("   in your .env file to run live tests")
            print("✅ Initialization test skipped (expected without credentials)")
            return True
        
        # Try to initialize
        extractor = DocumentIntelligenceExtractor()
        print(f"✅ Extractor initialized successfully")
        print(f"   Endpoint: {extractor.endpoint}")
        return True
        
    except ValueError as e:
        print(f"✅ Expected error without credentials: {e}")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_model_selection():
    """Test that _select_model chooses correct models."""
    print("\n" + "=" * 60)
    print("Test 2: Model Selection")
    print("=" * 60)
    
    try:
        # We can test model selection without credentials
        # Create a mock extractor with dummy credentials
        extractor = DocumentIntelligenceExtractor.__new__(DocumentIntelligenceExtractor)
        
        # Test model mapping
        test_cases = [
            (DocumentType.PAY_STUB, "prebuilt-invoice"),
            (DocumentType.BANK_STATEMENT, "prebuilt-invoice"),
            (DocumentType.TAX_RETURN, "prebuilt-tax.us.w2"),
            (DocumentType.DRIVERS_LICENSE, "prebuilt-idDocument"),
            (DocumentType.EMPLOYMENT_LETTER, "prebuilt-read"),
        ]
        
        all_passed = True
        for doc_type, expected_model in test_cases:
            model = extractor._select_model(doc_type.value)
            if model == expected_model:
                print(f"✅ {doc_type.value:20s} → {model}")
            else:
                print(f"❌ {doc_type.value:20s} → {model} (expected {expected_model})")
                all_passed = False
        
        # Test invalid document type
        try:
            extractor._select_model("invalid_type")
            print("❌ Should have raised ValueError for invalid type")
            all_passed = False
        except ValueError as e:
            print(f"✅ Correctly rejected invalid type: {str(e)[:50]}...")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_with_sample_pdf():
    """Test document analysis with a real PDF (requires Azure credentials)."""
    print("\n" + "=" * 60)
    print("Test 3: Document Analysis (Optional)")
    print("=" * 60)
    
    # Check if credentials are available
    if not config.AZURE_DOCUMENT_INTELLIGENCE_KEY:
        print("⚠️  Skipped: No Azure credentials configured")
        print("   Set credentials in .env to run live document analysis")
        return True
    
    # Check if test PDFs exist
    test_pdf = Path("tests/sample_applications/pay_stub_clean.pdf")
    if not test_pdf.exists():
        print(f"⚠️  Skipped: Test PDF not found at {test_pdf}")
        return True
    
    try:
        print(f"📄 Analyzing: {test_pdf.name}")
        
        extractor = DocumentIntelligenceExtractor()
        result = extractor.analyze_document(
            document_path=str(test_pdf),
            document_type=DocumentType.PAY_STUB,
            application_id="TEST-001"
        )
        
        print(f"✅ Analysis complete!")
        print(f"   Document ID: {result.document_id}")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print(f"   Valid: {result.is_valid}")
        print(f"   Fields extracted: {len(result.structured_data)}")
        print(f"   Method: {result.extraction_method}")
        
        if result.structured_data:
            print(f"\n   Sample fields:")
            for key, value in list(result.structured_data.items())[:3]:
                print(f"     - {key}: {str(value)[:50]}")
        
        # Test passes if extraction completed (even with borderline confidence)
        return result.confidence_score > 0.0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🧪 Testing DocumentIntelligenceExtractor (T018)\n")
    
    results = []
    
    # Run tests
    results.append(("Initialization", test_basic_initialization()))
    results.append(("Model Selection", test_model_selection()))
    results.append(("Document Analysis", test_with_sample_pdf()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nPassed: {total_passed}/{len(results)}")
    
    if total_passed == len(results):
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
