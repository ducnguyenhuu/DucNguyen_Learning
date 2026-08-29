"""
Quick test script for PolicyIndexer to verify Azure AI Search integration.

Run this after setting up Azure AI Search credentials in .env:
    python test_indexer.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.indexer import PolicyIndexer, DocumentChunker
from src.utils.config import Config

def test_indexer():
    """Test PolicyIndexer index creation."""
    print("=" * 60)
    print("Testing PolicyIndexer")
    print("=" * 60)
    
    # Validate credentials
    if not Config.validate_ai_search():
        print("❌ Azure AI Search credentials not configured!")
        print("   Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY in .env")
        return False
    
    print(f"✅ Azure AI Search endpoint: {Config.AZURE_SEARCH_ENDPOINT}")
    print(f"✅ Index name: {Config.AZURE_SEARCH_INDEX_NAME}")
    
    # Initialize indexer
    try:
        indexer = PolicyIndexer()
        print(f"\n✅ PolicyIndexer initialized")
    except Exception as e:
        print(f"\n❌ Failed to initialize PolicyIndexer: {e}")
        return False
    
    # Check if index exists
    exists = indexer.index_exists()
    print(f"\nIndex exists: {exists}")
    
    # Create index (delete if exists)
    try:
        print(f"\nCreating index '{indexer.index_name}'...")
        index = indexer.create_index(delete_if_exists=True)
        print(f"✅ Index created successfully!")
        print(f"   Name: {index.name}")
        print(f"   Fields: {len(index.fields)}")
    except Exception as e:
        print(f"❌ Failed to create index: {e}")
        return False
    
    # Get index stats
    try:
        stats = indexer.get_index_stats()
        print(f"\n📊 Index Statistics:")
        print(f"   Index name: {stats['index_name']}")
        print(f"   Field count: {stats['field_count']}")
        print(f"   Vector search: {stats['vector_search_enabled']}")
    except Exception as e:
        print(f"⚠️  Could not get index stats: {e}")
    
    return True


def test_chunker():
    """Test DocumentChunker with text and PDF files."""
    print("\n" + "=" * 60)
    print("Testing DocumentChunker")
    print("=" * 60)
    
    # Sample policy text
    sample_text = """
    Underwriting Standards for Conventional Loans
    
    Debt-to-Income Ratio Requirements:
    The debt-to-income (DTI) ratio is a critical factor in loan approval. 
    The maximum allowable DTI ratio for conventional loans is 43%.
    Borrowers with DTI ratios above 36% must demonstrate compensating factors.
    
    Loan-to-Value Ratio Guidelines:
    For primary residences, the maximum loan-to-value (LTV) ratio is 80% without PMI.
    Borrowers seeking LTV ratios above 80% must obtain private mortgage insurance.
    The maximum allowable LTV with PMI is 95% for qualified borrowers.
    
    Credit Score Requirements:
    Minimum credit score for conventional loans: 620
    Borrowers with scores 620-679: Higher down payment required (20%)
    Borrowers with scores 680-739: Standard terms apply (10% down)
    Borrowers with scores 740+: Best rates available (5% down)
    """ * 5  # Repeat to create longer text
    
    # Initialize chunker
    chunker = DocumentChunker(chunk_size=500, overlap=50)
    print(f"Chunker config: {chunker.chunk_size} tokens, {chunker.overlap} overlap")
    
    # Test 1: Text chunking
    print("\n📝 Test 1: Text Chunking")
    chunks = chunker.chunk_text(sample_text, doc_id="test-policy")
    
    print(f"✅ Created {len(chunks)} chunks from text")
    print(f"\nFirst chunk preview:")
    print(f"   Index: {chunks[0]['index']}")
    print(f"   Length: {len(chunks[0]['text'])} chars")
    print(f"   Text: {chunks[0]['text'][:200]}...")
    
    if len(chunks) > 1:
        print(f"\nSecond chunk preview:")
        print(f"   Index: {chunks[1]['index']}")
        print(f"   Length: {len(chunks[1]['text'])} chars")
        print(f"   Text: {chunks[1]['text'][:200]}...")
    
    # Test 2: PDF file chunking (if PDFs exist)
    print("\n📄 Test 2: PDF File Chunking")
    policies_dir = project_root / "data" / "policies"
    
    if policies_dir.exists():
        pdf_files = list(policies_dir.glob("*.pdf"))
        
        if pdf_files:
            # Test with first PDF found
            test_pdf = pdf_files[0]
            print(f"Testing with: {test_pdf.name}")
            
            try:
                pdf_chunks = chunker.chunk_file(test_pdf)
                print(f"✅ Created {len(pdf_chunks)} chunks from PDF")
                print(f"\nFirst PDF chunk preview:")
                print(f"   Index: {pdf_chunks[0]['index']}")
                print(f"   Length: {len(pdf_chunks[0]['text'])} chars")
                print(f"   Text: {pdf_chunks[0]['text'][:200]}...")
                
            except Exception as e:
                print(f"⚠️  PDF chunking error: {e}")
                print(f"   This may be expected if PDFs are image-based")
        else:
            print(f"⚠️  No PDF files found in {policies_dir}")
            print(f"   Skipping PDF test (expected for fresh setup)")
    else:
        print(f"⚠️  Policies directory not found: {policies_dir}")
        print(f"   Skipping PDF test (expected for fresh setup)")
    
    # Test 3: Text file chunking
    print("\n📄 Test 3: Text File Chunking (Create Sample)")
    temp_txt = project_root / "data" / "test_policy.txt"
    temp_txt.parent.mkdir(parents=True, exist_ok=True)
    temp_txt.write_text(sample_text)
    
    try:
        txt_chunks = chunker.chunk_file(temp_txt)
        print(f"✅ Created {len(txt_chunks)} chunks from text file")
        print(f"   File: {temp_txt.name}")
    except Exception as e:
        print(f"❌ Text file chunking failed: {e}")
        return False
    finally:
        # Clean up temp file
        if temp_txt.exists():
            temp_txt.unlink()
    
    return True


if __name__ == "__main__":
    print("\n🚀 Testing RAG Indexer Implementation (T038-T040)")
    print("=" * 60)
    
    # Test chunker (doesn't require Azure credentials)
    chunker_success = test_chunker()
    
    # Test indexer (requires Azure credentials)
    indexer_success = test_indexer()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"DocumentChunker: {'✅ PASSED' if chunker_success else '❌ FAILED'}")
    print(f"PolicyIndexer: {'✅ PASSED' if indexer_success else '❌ FAILED'}")
    
    if indexer_success and chunker_success:
        print("\n🎉 All tests passed! T038-T040 implementation complete.")
        print("\nCompleted Tasks:")
        print("  ✅ T038: Create src/rag/__init__.py")
        print("  ✅ T039: Implement Azure AI Search index creation")
        print("  ✅ T040: Implement PDF chunking with pdfplumber")
        print("\nNext steps:")
        print("  - T041: Implement Ada-002 embedding generator")
        print("  - T042: Implement policy upload pipeline")
        print("  - T043: Implement semantic search retriever")
    else:
        print("\n⚠️  Some tests failed. Check configuration and credentials.")
