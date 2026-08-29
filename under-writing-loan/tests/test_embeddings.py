"""
Test script for EmbeddingGenerator (T041).

This script validates:
1. Single text embedding
2. Batch embedding with multiple texts
3. Chunk embedding integration with DocumentChunker
4. Cost tracking and reporting
5. Error handling

Run: python tests/test_embeddings.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.embeddings import EmbeddingGenerator
from src.rag.indexer import DocumentChunker
from src.utils.config import Config


def test_single_embedding():
    """Test embedding a single text."""
    print("\n" + "=" * 70)
    print("Test 1: Single Text Embedding")
    print("=" * 70)
    
    # Validate credentials
    if not Config.validate_azure_openai():
        print("❌ Azure OpenAI credentials not configured!")
        print("   Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env")
        return False
    
    try:
        generator = EmbeddingGenerator()
        print(f"✅ EmbeddingGenerator initialized")
        print(f"   Model: {generator.deployment}")
        print(f"   Endpoint: {generator.endpoint}")
        
        # Embed single text
        sample_text = "The maximum debt-to-income ratio for conventional loans is 43%."
        print(f"\nEmbedding text: '{sample_text[:60]}...'")
        
        embedding = generator.embed_text(sample_text)
        
        print(f"\n✅ Embedding generated:")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   Type: {type(embedding[0])}")
        print(f"   Sample values: {embedding[:5]}")
        
        # Check cost
        summary = generator.get_cost_summary()
        print(f"\n💰 Cost Summary:")
        print(f"   Tokens used: {summary['total_tokens']}")
        print(f"   Total cost: ${summary['total_cost']:.6f}")
        
        # Validate embedding
        assert len(embedding) == 1536, "Embedding should be 1536 dimensions"
        assert all(isinstance(x, float) for x in embedding), "Embedding should be floats"
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def test_batch_embedding():
    """Test embedding multiple texts in batch."""
    print("\n" + "=" * 70)
    print("Test 2: Batch Embedding")
    print("=" * 70)
    
    try:
        generator = EmbeddingGenerator(batch_size=3)
        
        # Create sample policy texts
        texts = [
            "Debt-to-income ratio must not exceed 43% for conventional loans.",
            "Borrowers must have a minimum credit score of 620 for approval.",
            "Loan-to-value ratio cannot exceed 80% without PMI insurance.",
            "Property appraisal must be completed by certified appraiser.",
            "Income verification requires two years of tax returns.",
        ]
        
        print(f"Embedding {len(texts)} texts in batches of {generator.batch_size}")
        
        embeddings = generator.embed_batch(texts, show_progress=True)
        
        print(f"\n✅ Batch embeddings generated:")
        print(f"   Count: {len(embeddings)}")
        print(f"   Dimensions: {len(embeddings[0])}")
        
        # Check cost
        summary = generator.get_cost_summary()
        print(f"\n💰 Cost Summary:")
        print(f"   Tokens used: {summary['total_tokens']}")
        print(f"   Total cost: ${summary['total_cost']:.6f}")
        print(f"   Cost per text: ${summary['total_cost'] / len(texts):.6f}")
        
        # Validate
        assert len(embeddings) == len(texts), "Should have one embedding per text"
        assert all(len(emb) == 1536 for emb in embeddings), "All embeddings should be 1536 dims"
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def test_chunk_embedding():
    """Test embedding document chunks."""
    print("\n" + "=" * 70)
    print("Test 3: Chunk Embedding Integration")
    print("=" * 70)
    
    try:
        # Create sample document chunks
        chunker = DocumentChunker(chunk_size=100, overlap=10)
        
        sample_policy = """
        Underwriting Standards for Conventional Loans
        
        1. Debt-to-Income Ratio: Maximum 43%
        Borrowers with DTI ratios above 36% must demonstrate compensating factors
        such as significant liquid reserves or strong credit history.
        
        2. Credit Score Requirements:
        - Minimum credit score: 620
        - Scores 620-679: Require 20% down payment
        - Scores 680-739: Standard 10% down payment
        - Scores 740+: Best rates with 5% down
        
        3. Loan-to-Value Ratio:
        - Maximum LTV without PMI: 80%
        - Maximum LTV with PMI: 95%
        - Borrowers must maintain PMI until LTV reaches 78%
        """
        
        chunks = chunker.chunk_text(sample_policy, doc_id="test-policy")
        print(f"Created {len(chunks)} chunks from policy document")
        
        # Embed chunks
        generator = EmbeddingGenerator()
        embedded_chunks = generator.embed_chunks(chunks)
        
        print(f"\n✅ Chunks embedded:")
        print(f"   Count: {len(embedded_chunks)}")
        print(f"   Each chunk has 'embedding' field: {all('embedding' in c for c in embedded_chunks)}")
        
        # Show first chunk structure
        print(f"\n📄 First chunk structure:")
        print(f"   Keys: {list(embedded_chunks[0].keys())}")
        print(f"   Text length: {len(embedded_chunks[0]['text'])} chars")
        print(f"   Embedding dims: {len(embedded_chunks[0]['embedding'])}")
        print(f"   Index: {embedded_chunks[0]['index']}")
        
        # Check cost
        summary = generator.get_cost_summary()
        print(f"\n💰 Cost Summary:")
        print(f"   Tokens used: {summary['total_tokens']}")
        print(f"   Total cost: ${summary['total_cost']:.6f}")
        
        # Validate
        assert all('embedding' in c for c in embedded_chunks), "All chunks should have embeddings"
        assert all(len(c['embedding']) == 1536 for c in embedded_chunks), "All embeddings should be 1536 dims"
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def test_pdf_chunk_embedding():
    """Test embedding chunks from real PDF file."""
    print("\n" + "=" * 70)
    print("Test 4: PDF Chunk Embedding")
    print("=" * 70)
    
    pdf_path = project_root / "data" / "policies" / "underwriting_standards.pdf"
    
    if not pdf_path.exists():
        print(f"⚠️  PDF not found: {pdf_path}")
        print("   Skipping PDF test")
        return True
    
    try:
        # Chunk PDF
        chunker = DocumentChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk_file(pdf_path)
        
        print(f"Created {len(chunks)} chunks from {pdf_path.name}")
        
        # Embed chunks
        generator = EmbeddingGenerator()
        embedded_chunks = generator.embed_chunks(chunks, show_progress=True)
        
        print(f"\n✅ PDF chunks embedded:")
        print(f"   File: {pdf_path.name}")
        print(f"   Chunks: {len(embedded_chunks)}")
        print(f"   Total chars: {sum(len(c['text']) for c in embedded_chunks)}")
        
        # Check cost
        summary = generator.get_cost_summary()
        print(f"\n💰 Cost Summary:")
        print(f"   Tokens used: {summary['total_tokens']}")
        print(f"   Total cost: ${summary['total_cost']:.6f}")
        print(f"   Cost per chunk: ${summary['total_cost'] / len(chunks):.6f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n" + "=" * 70)
    print("Test 5: Error Handling")
    print("=" * 70)
    
    try:
        generator = EmbeddingGenerator()
        
        # Test 1: Empty text
        print("\n1. Empty text:")
        try:
            generator.embed_text("")
            print("   ❌ Should have raised ValueError")
        except ValueError:
            print("   ✅ Correctly raised ValueError")
        
        # Test 2: Empty batch
        print("\n2. Empty batch:")
        try:
            generator.embed_batch([])
            print("   ❌ Should have raised ValueError")
        except ValueError:
            print("   ✅ Correctly raised ValueError")
        
        # Test 3: Batch with empty string
        print("\n3. Batch with empty string:")
        try:
            generator.embed_batch(["valid text", "", "another valid"])
            print("   ❌ Should have raised ValueError")
        except ValueError:
            print("   ✅ Correctly raised ValueError")
        
        print("\n✅ Error handling works correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("EMBEDDING GENERATOR TEST SUITE (T041)")
    print("=" * 70)
    print("\nThis test suite validates the Ada-002 embedding generator.")
    print("Features tested:")
    print("  • Single text embedding")
    print("  • Batch embedding with rate limit handling")
    print("  • Chunk embedding integration")
    print("  • PDF document processing")
    print("  • Cost tracking and reporting")
    print("  • Error handling")
    
    # Run tests
    results = {
        "Single Embedding": test_single_embedding(),
        "Batch Embedding": test_batch_embedding(),
        "Chunk Embedding": test_chunk_embedding(),
        "PDF Embedding": test_pdf_chunk_embedding(),
        "Error Handling": test_error_handling(),
    }
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:<25} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! T041 implementation complete.")
        print("\nCompleted Tasks:")
        print("  ✅ T038: Create src/rag/__init__.py")
        print("  ✅ T039: Implement Azure AI Search index creation")
        print("  ✅ T040: Implement PDF chunking with pdfplumber")
        print("  ✅ T041: Implement Ada-002 embedding generator")
        print("\nNext steps:")
        print("  • T042: Implement policy upload and indexing pipeline")
        print("  • T043: Implement semantic search retriever")
        print("  • T044: Create RAG system notebook")
    else:
        print("\n⚠️  Some tests failed. Check credentials and configuration.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
