"""
Demo script showcasing Ada-002 embedding generation (T041).

This script demonstrates:
1. Single text embedding
2. Batch embedding with cost tracking
3. Integration with DocumentChunker for PDF processing
4. Embedding dimension and format validation

Run: python examples/demo_embeddings.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.embeddings import EmbeddingGenerator
from src.rag.indexer import DocumentChunker


def demo_single_embedding():
    """Demonstrate single text embedding."""
    print("\n" + "=" * 70)
    print("Demo 1: Single Text Embedding")
    print("=" * 70)
    
    generator = EmbeddingGenerator()
    
    # Sample policy text
    policy_text = (
        "The maximum debt-to-income ratio for conventional mortgage loans "
        "is 43%. Borrowers with DTI ratios above 36% must demonstrate "
        "compensating factors such as significant cash reserves or "
        "excellent credit history."
    )
    
    print(f"\nText to embed:")
    print(f"  '{policy_text[:80]}...'")
    print(f"  Length: {len(policy_text)} characters")
    
    # Generate embedding
    embedding = generator.embed_text(policy_text)
    
    print(f"\n✅ Embedding generated:")
    print(f"  Dimensions: {len(embedding)}")
    print(f"  First 5 values: {[f'{v:.6f}' for v in embedding[:5]]}")
    print(f"  Value range: [{min(embedding):.6f}, {max(embedding):.6f}]")
    
    # Cost summary
    summary = generator.get_cost_summary()
    print(f"\n💰 Cost:")
    print(f"  Tokens: {summary['total_tokens']}")
    print(f"  Cost: ${summary['total_cost']:.6f}")


def demo_batch_embedding():
    """Demonstrate batch embedding with multiple policy statements."""
    print("\n" + "=" * 70)
    print("Demo 2: Batch Embedding")
    print("=" * 70)
    
    generator = EmbeddingGenerator(batch_size=3)
    
    # Sample policy statements
    policies = [
        "Borrowers must have a minimum credit score of 620 for conventional loan approval.",
        "The loan-to-value ratio cannot exceed 80% without private mortgage insurance.",
        "Income verification requires two consecutive years of W-2 forms or tax returns.",
        "Property appraisal must be completed by a state-certified appraiser.",
        "Borrowers with DTI ratios above 43% are not eligible for qualified mortgages.",
        "Self-employed borrowers must provide two years of profit and loss statements.",
        "Gift funds for down payment must be documented with donor statement and transfer proof.",
    ]
    
    print(f"\nEmbedding {len(policies)} policy statements:")
    for i, policy in enumerate(policies, 1):
        print(f"  {i}. {policy[:70]}...")
    
    print(f"\nBatch size: {generator.batch_size}")
    print(f"Expected batches: {(len(policies) + generator.batch_size - 1) // generator.batch_size}")
    
    # Generate embeddings
    embeddings = generator.embed_batch(policies, show_progress=False)
    
    print(f"\n✅ Batch embeddings generated:")
    print(f"  Count: {len(embeddings)}")
    print(f"  Dimensions: {len(embeddings[0])}")
    
    # Cost summary
    summary = generator.get_cost_summary()
    print(f"\n💰 Cost Summary:")
    print(f"  Total tokens: {summary['total_tokens']}")
    print(f"  Total cost: ${summary['total_cost']:.6f}")
    print(f"  Cost per statement: ${summary['total_cost'] / len(policies):.6f}")
    print(f"  Model: {summary['model']}")


def demo_chunk_embedding():
    """Demonstrate embedding document chunks."""
    print("\n" + "=" * 70)
    print("Demo 3: Document Chunk Embedding")
    print("=" * 70)
    
    # Create sample policy document
    policy_doc = """
    UNDERWRITING STANDARDS FOR CONVENTIONAL LOANS
    
    Section 1: Debt-to-Income Ratio Requirements
    The debt-to-income (DTI) ratio is calculated by dividing total monthly debt 
    obligations by gross monthly income. For conventional loans, the maximum 
    allowable DTI ratio is 43%. Borrowers with DTI ratios between 36% and 43% 
    must demonstrate strong compensating factors such as:
    - Significant liquid reserves (6+ months)
    - Excellent credit score (740+)
    - Stable employment history (5+ years)
    - Low loan-to-value ratio (<70%)
    
    Section 2: Credit Score Requirements
    Minimum credit score for conventional loan approval is 620. However, credit
    score significantly impacts loan terms:
    - 620-679: Requires 20% down payment, higher interest rate
    - 680-739: Standard terms with 10% down payment
    - 740+: Best rates available with as little as 5% down
    
    Section 3: Loan-to-Value Ratio Guidelines
    The loan-to-value (LTV) ratio compares the loan amount to the property's
    appraised value. For conventional loans:
    - LTV ≤ 80%: No private mortgage insurance (PMI) required
    - 80% < LTV ≤ 95%: PMI required until LTV reaches 78%
    - LTV > 95%: Not eligible for conventional financing
    
    Borrowers must maintain PMI until the LTV ratio falls below 78% through
    payments or property appreciation.
    """ * 2  # Repeat to create longer document
    
    # Chunk the document
    chunker = DocumentChunker(chunk_size=300, overlap=30)
    chunks = chunker.chunk_text(policy_doc, doc_id="underwriting-standards")
    
    print(f"\nDocument chunking:")
    print(f"  Total length: {len(policy_doc)} characters")
    print(f"  Chunk size: {chunker.chunk_size} tokens (~{chunker.chunk_size * 4} chars)")
    print(f"  Overlap: {chunker.overlap} tokens ({chunker.overlap * 4} chars)")
    print(f"  Chunks created: {len(chunks)}")
    
    # Embed chunks
    generator = EmbeddingGenerator()
    embedded_chunks = generator.embed_chunks(chunks)
    
    print(f"\n✅ Chunks embedded:")
    print(f"  Count: {len(embedded_chunks)}")
    print(f"  Each chunk has:")
    print(f"    - text: {len(embedded_chunks[0]['text'])} chars")
    print(f"    - embedding: {len(embedded_chunks[0]['embedding'])} dimensions")
    print(f"    - index: {embedded_chunks[0]['index']}")
    
    # Show embedding similarity example
    if len(embedded_chunks) >= 2:
        import math
        
        # Calculate cosine similarity between first two chunks
        emb1 = embedded_chunks[0]['embedding']
        emb2 = embedded_chunks[1]['embedding']
        
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        mag1 = math.sqrt(sum(a * a for a in emb1))
        mag2 = math.sqrt(sum(b * b for b in emb2))
        similarity = dot_product / (mag1 * mag2)
        
        print(f"\n📊 Similarity Analysis:")
        print(f"  Cosine similarity between adjacent chunks: {similarity:.4f}")
        print(f"  (High similarity expected due to {chunker.overlap} token overlap)")
    
    # Cost summary
    summary = generator.get_cost_summary()
    print(f"\n💰 Cost Summary:")
    print(f"  Tokens: {summary['total_tokens']}")
    print(f"  Cost: ${summary['total_cost']:.6f}")
    print(f"  Cost per chunk: ${summary['total_cost'] / len(chunks):.6f}")


def demo_pdf_embedding():
    """Demonstrate PDF embedding workflow."""
    print("\n" + "=" * 70)
    print("Demo 4: PDF Document Embedding")
    print("=" * 70)
    
    # Find a policy PDF
    policies_dir = Path("data/policies")
    pdf_files = list(policies_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("\n⚠️  No PDF files found in data/policies/")
        print("   Skipping PDF demo")
        return
    
    # Use first PDF
    pdf_path = pdf_files[0]
    print(f"\nProcessing: {pdf_path.name}")
    
    # Chunk PDF
    chunker = DocumentChunker(chunk_size=500, overlap=50)
    chunks = chunker.chunk_file(pdf_path)
    
    print(f"\n📄 PDF Processing:")
    print(f"  File: {pdf_path.name}")
    print(f"  Chunks created: {len(chunks)}")
    print(f"  Total characters: {sum(len(c['text']) for c in chunks)}")
    
    # Embed chunks
    generator = EmbeddingGenerator()
    embedded_chunks = generator.embed_chunks(chunks, show_progress=True)
    
    print(f"\n✅ PDF embedded:")
    print(f"  Embedded chunks: {len(embedded_chunks)}")
    print(f"  Embedding dimensions: {len(embedded_chunks[0]['embedding'])}")
    
    # Show first chunk preview
    print(f"\n📝 First chunk preview:")
    print(f"  {embedded_chunks[0]['text'][:200]}...")
    
    # Cost summary
    summary = generator.get_cost_summary()
    print(f"\n💰 Cost Summary:")
    print(f"  Tokens: {summary['total_tokens']}")
    print(f"  Cost: ${summary['total_cost']:.6f}")
    print(f"  Cost per chunk: ${summary['total_cost'] / len(chunks):.6f}")
    
    # Estimate cost for all PDFs
    total_pdfs = len(pdf_files)
    estimated_cost = summary['total_cost'] * total_pdfs
    print(f"\n📈 Scaling Estimate:")
    print(f"  PDFs in directory: {total_pdfs}")
    print(f"  Estimated total cost: ${estimated_cost:.6f}")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("ADA-002 EMBEDDING GENERATOR DEMO (T041)")
    print("=" * 70)
    print("\nThis demo showcases text embedding using Azure OpenAI Ada-002.")
    print("Features demonstrated:")
    print("  • Single text embedding generation")
    print("  • Batch processing with cost tracking")
    print("  • Document chunking integration")
    print("  • PDF processing workflow")
    print("  • Cost estimation and reporting")
    
    # Run demos
    demo_single_embedding()
    demo_batch_embedding()
    demo_chunk_embedding()
    demo_pdf_embedding()
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\n✅ T041 Implementation: Ada-002 embedding generator")
    print("\nKey Features:")
    print("  • 1536-dimensional embeddings (Ada-002 standard)")
    print("  • Batch processing with rate limit handling")
    print("  • Automatic retry with exponential backoff")
    print("  • Cost tracking: $0.0001 per 1K tokens")
    print("  • Integration with DocumentChunker for RAG pipeline")
    print("\nNext steps:")
    print("  • T042: Implement policy upload and indexing pipeline")
    print("  • T043: Implement semantic search retriever")
    print("  • T044: Create RAG system notebook")


if __name__ == "__main__":
    main()
