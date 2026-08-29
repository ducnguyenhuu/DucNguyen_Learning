"""
Demo script showcasing PDF chunking implementation (T040).

This script demonstrates:
1. PDF text extraction using pdfplumber
2. Document chunking with configurable token size
3. Batch processing of multiple policy documents
4. Error handling for edge cases

Run: python examples/demo_pdf_chunking.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.indexer import DocumentChunker


def demo_single_pdf():
    """Demonstrate PDF extraction and chunking for a single document."""
    print("\n" + "=" * 70)
    print("Demo 1: Single PDF Processing")
    print("=" * 70)
    
    chunker = DocumentChunker(chunk_size=500, overlap=50)
    pdf_path = Path("data/policies/underwriting_standards.pdf")
    
    if pdf_path.exists():
        print(f"\nProcessing: {pdf_path.name}")
        chunks = chunker.chunk_file(pdf_path)
        
        print(f"\n✅ Results:")
        print(f"   Total chunks: {len(chunks)}")
        print(f"   Chunk size: ~{chunker.chunk_size} tokens (~{chunker.chunk_size * 4} chars)")
        print(f"   Overlap: {chunker.overlap} tokens ({chunker.overlap * 4} chars)")
        
        # Show first chunk
        print(f"\n📄 First chunk preview:")
        print(f"   Index: {chunks[0]['index']}")
        print(f"   Length: {len(chunks[0]['text'])} characters")
        print(f"   Content:\n")
        print("   " + "\n   ".join(chunks[0]['text'][:300].split("\n")))
        print("   ...")
    else:
        print(f"❌ PDF not found: {pdf_path}")


def demo_batch_processing():
    """Demonstrate batch processing of all policy PDFs."""
    print("\n" + "=" * 70)
    print("Demo 2: Batch PDF Processing")
    print("=" * 70)
    
    chunker = DocumentChunker(chunk_size=500, overlap=50)
    policies_dir = Path("data/policies")
    
    if not policies_dir.exists():
        print(f"❌ Policies directory not found: {policies_dir}")
        return
    
    pdf_files = sorted(policies_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {policies_dir}")
        return
    
    print(f"\nProcessing {len(pdf_files)} policy documents...\n")
    
    total_chunks = 0
    results = []
    
    for pdf_path in pdf_files:
        try:
            chunks = chunker.chunk_file(pdf_path)
            total_chunks += len(chunks)
            results.append({
                "name": pdf_path.name,
                "chunks": len(chunks),
                "chars": sum(len(c["text"]) for c in chunks),
                "status": "✅"
            })
        except Exception as e:
            results.append({
                "name": pdf_path.name,
                "chunks": 0,
                "chars": 0,
                "status": f"❌ {str(e)[:30]}"
            })
    
    # Display results table
    print(f"{'File Name':<35} {'Chunks':<10} {'Total Chars':<15} {'Status'}")
    print("-" * 70)
    
    for result in results:
        print(
            f"{result['name']:<35} "
            f"{result['chunks']:<10} "
            f"{result['chars']:<15} "
            f"{result['status']}"
        )
    
    print("-" * 70)
    print(f"{'TOTAL':<35} {total_chunks:<10} {sum(r['chars'] for r in results):<15}")


def demo_chunk_parameters():
    """Demonstrate different chunking configurations."""
    print("\n" + "=" * 70)
    print("Demo 3: Chunking Parameters Comparison")
    print("=" * 70)
    
    pdf_path = Path("data/policies/underwriting_standards.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Test different configurations
    configs = [
        {"chunk_size": 300, "overlap": 30},
        {"chunk_size": 500, "overlap": 50},  # Default
        {"chunk_size": 800, "overlap": 80},
    ]
    
    print(f"\nTesting with: {pdf_path.name}\n")
    print(f"{'Config':<25} {'Chunks':<10} {'Avg Size':<15}")
    print("-" * 50)
    
    for config in configs:
        chunker = DocumentChunker(**config)
        chunks = chunker.chunk_file(pdf_path)
        avg_size = sum(len(c["text"]) for c in chunks) / len(chunks)
        
        print(
            f"{config['chunk_size']} tokens, {config['overlap']} overlap"
            f"{'':<5} {len(chunks):<10} {avg_size:<15.0f}"
        )


def demo_error_handling():
    """Demonstrate error handling for edge cases."""
    print("\n" + "=" * 70)
    print("Demo 4: Error Handling")
    print("=" * 70)
    
    chunker = DocumentChunker()
    
    # Test case 1: Non-existent file
    print("\nTest 1: Non-existent file")
    try:
        chunker.chunk_file(Path("nonexistent.pdf"))
        print("   ❌ Should have raised FileNotFoundError")
    except FileNotFoundError:
        print("   ✅ Correctly handled: FileNotFoundError")
    
    # Test case 2: Unsupported file type
    print("\nTest 2: Unsupported file type (.docx)")
    test_file = Path("data/test.docx")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("test content")
    
    try:
        chunker.chunk_file(test_file)
        print("   ❌ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ Correctly handled: ValueError")
        print(f"      Message: {str(e)[:60]}...")
    finally:
        test_file.unlink()
    
    # Test case 3: Empty PDF (simulated)
    print("\nTest 3: Empty PDF handling")
    print("   ℹ️  Empty PDFs return ValueError: No text content extracted")
    print("   ℹ️  This helps identify image-based PDFs requiring OCR")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("PDF CHUNKING IMPLEMENTATION DEMO (T040)")
    print("=" * 70)
    print("\nThis demo showcases the DocumentChunker class with PDF support.")
    print("Features:")
    print("  • PDF text extraction using pdfplumber")
    print("  • Configurable token-based chunking (500 tokens default)")
    print("  • Overlap support for context preservation (50 tokens)")
    print("  • Batch processing of multiple documents")
    print("  • Comprehensive error handling")
    
    # Run all demos
    demo_single_pdf()
    demo_batch_processing()
    demo_chunk_parameters()
    demo_error_handling()
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\n✅ T040 Implementation: PDF chunking with pdfplumber")
    print("\nNext steps:")
    print("  • T041: Implement Ada-002 embedding generator")
    print("  • T042: Implement policy upload and indexing pipeline")
    print("  • T043: Implement semantic search retriever")
    print("\nFor more details, see: docs/T040_PDF_CHUNKING_IMPLEMENTATION.md")


if __name__ == "__main__":
    main()
