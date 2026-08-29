"""
Demo script for T042: Policy upload and indexing pipeline.

This demonstrates the complete RAG indexing workflow:
1. Chunk policy documents (500 tokens, 50 overlap)
2. Generate embeddings (Ada-002, 1536 dimensions)
3. Upload to Azure AI Search (vector + keyword search)

Run with:
    python examples/demo_indexing_pipeline.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import logging
from src.rag.indexer import PolicyIndexer, DocumentChunker
from src.rag.embeddings import EmbeddingGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_complete_pipeline():
    """
    Demo: Complete indexing pipeline for all policy documents.
    
    Workflow:
    1. Initialize PolicyIndexer and EmbeddingGenerator
    2. Collect all policy PDFs from data/policies/
    3. Process each document: chunk → embed → upload
    4. Display statistics and cost breakdown
    """
    logger.info("\n" + "="*70)
    logger.info("🚀 Demo: Policy Upload and Indexing Pipeline")
    logger.info("="*70)
    
    try:
        # Step 1: Initialize components
        logger.info("\n📦 Step 1: Initialize components")
        logger.info("-" * 70)
        
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        
        logger.info("✅ PolicyIndexer initialized")
        logger.info("✅ EmbeddingGenerator initialized")
        
        # Step 2: Ensure index exists
        logger.info("\n🔍 Step 2: Check/create Azure AI Search index")
        logger.info("-" * 70)
        
        if not indexer.index_exists():
            logger.info("Creating new index...")
            indexer.create_index()
        else:
            logger.info(f"✅ Index '{indexer.index_name}' already exists")
        
        # Step 3: Collect policy files
        logger.info("\n📂 Step 3: Collect policy documents")
        logger.info("-" * 70)
        
        policy_dir = Path("data/policies")
        policy_files = list(policy_dir.glob("*.pdf"))
        
        if len(policy_files) == 0:
            logger.error(f"❌ No PDF files found in {policy_dir}")
            logger.info("Please add policy PDFs to data/policies/ directory")
            return
        
        logger.info(f"Found {len(policy_files)} policy documents:")
        for i, file in enumerate(policy_files, start=1):
            logger.info(f"  {i}. {file.name}")
        
        # Step 4: Define category mapping
        logger.info("\n🏷️  Step 4: Define document categories")
        logger.info("-" * 70)
        
        category_map = {
            "underwriting_standards": "underwriting",
            "credit_requirements": "credit",
            "income_verification": "income",
            "property_guidelines": "property",
            "compliance_rules": "compliance"
        }
        
        logger.info("Category mapping:")
        for filename, category in category_map.items():
            logger.info(f"  {filename} → {category}")
        
        # Step 5: Run indexing pipeline
        logger.info("\n⚙️  Step 5: Run indexing pipeline (chunk → embed → upload)")
        logger.info("-" * 70)
        
        stats = indexer.index_documents(
            file_paths=policy_files,
            embedder=embedder,
            category_map=category_map,
            batch_size=5
        )
        
        # Step 6: Display results
        logger.info("\n📊 Step 6: Results Summary")
        logger.info("-" * 70)
        
        logger.info(f"\n✅ Indexing Complete!")
        logger.info(f"\n📈 Statistics:")
        logger.info(f"  Files processed: {stats['total_files']}/{len(policy_files)}")
        logger.info(f"  Total chunks: {stats['total_chunks']}")
        logger.info(f"  Total tokens: {stats['total_tokens']:,}")
        logger.info(f"  Total cost: ${stats['total_cost']:.6f}")
        
        if stats['total_chunks'] > 0:
            logger.info(f"\n💰 Cost Breakdown:")
            logger.info(f"  Cost per chunk: ${stats['total_cost'] / stats['total_chunks']:.6f}")
            logger.info(f"  Cost per file: ${stats['total_cost'] / stats['total_files']:.6f}")
            
            # Estimate scaling
            logger.info(f"\n📈 Scaling Estimates:")
            cost_per_file = stats['total_cost'] / stats['total_files']
            logger.info(f"  10 files: ~${cost_per_file * 10:.4f}")
            logger.info(f"  50 files: ~${cost_per_file * 50:.4f}")
            logger.info(f"  100 files: ~${cost_per_file * 100:.4f}")
        
        if stats["failed_files"]:
            logger.warning(f"\n⚠️  Failed files ({len(stats['failed_files'])}):")
            for failed_file in stats["failed_files"]:
                logger.warning(f"  - {failed_file}")
        
        logger.info("\n" + "="*70)
        logger.info("✅ Demo Complete!")
        logger.info("="*70)
        
        logger.info("\n💡 Next Steps:")
        logger.info("  1. Test semantic search with demo_retrieval.py (T043)")
        logger.info("  2. View indexed documents in Azure Portal")
        logger.info("  3. Experiment with different chunking strategies")
        
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}")
        raise


def demo_single_document():
    """
    Demo: Index a single document with detailed logging.
    
    Shows step-by-step what happens during indexing:
    - Document loading
    - Chunking process
    - Embedding generation
    - Upload to Azure AI Search
    """
    logger.info("\n" + "="*70)
    logger.info("📄 Demo: Index Single Document (Detailed)")
    logger.info("="*70)
    
    try:
        # Initialize
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        chunker = DocumentChunker(chunk_size=500, overlap=50)
        
        # Ensure index exists
        if not indexer.index_exists():
            logger.info("Creating index...")
            indexer.create_index()
        
        # Pick a single file
        policy_file = Path("data/policies/income_verification.pdf")
        
        if not policy_file.exists():
            logger.error(f"❌ File not found: {policy_file}")
            logger.info("Using first available PDF instead...")
            policy_dir = Path("data/policies")
            policy_files = list(policy_dir.glob("*.pdf"))
            if not policy_files:
                logger.error("No PDFs found in data/policies/")
                return
            policy_file = policy_files[0]
        
        logger.info(f"\n📄 Processing: {policy_file.name}")
        logger.info("-" * 70)
        
        # Step 1: Chunk
        logger.info("\nStep 1: Chunking document...")
        chunks = chunker.chunk_file(policy_file)
        logger.info(f"  ✅ Created {len(chunks)} chunks")
        
        if len(chunks) > 0:
            logger.info(f"\n  Example chunk (first):")
            logger.info(f"    Index: {chunks[0]['index']}")
            logger.info(f"    Start: {chunks[0]['start_char']}")
            logger.info(f"    End: {chunks[0]['end_char']}")
            logger.info(f"    Length: {len(chunks[0]['text'])} chars")
            logger.info(f"    Preview: {chunks[0]['text'][:150]}...")
        
        # Step 2: Embed
        logger.info("\nStep 2: Generating embeddings...")
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = embedder.embed_batch(chunk_texts)
        logger.info(f"  ✅ Generated {len(embeddings)} embeddings")
        
        if len(embeddings) > 0:
            logger.info(f"\n  Example embedding (first):")
            logger.info(f"    Dimensions: {len(embeddings[0])}")
            logger.info(f"    First 5 values: {embeddings[0][:5]}")
            logger.info(f"    Min value: {min(embeddings[0]):.4f}")
            logger.info(f"    Max value: {max(embeddings[0]):.4f}")
        
        # Step 3: Upload
        logger.info("\nStep 3: Uploading to Azure AI Search...")
        stats = indexer.index_documents(
            file_paths=[policy_file],
            embedder=embedder,
            chunker=chunker,
            category_map={"income_verification": "income"}
        )
        
        logger.info(f"\n✅ Upload complete!")
        logger.info(f"  Chunks uploaded: {stats['total_chunks']}")
        logger.info(f"  Tokens used: {stats['total_tokens']}")
        logger.info(f"  Cost: ${stats['total_cost']:.6f}")
        
        logger.info("\n" + "="*70)
        logger.info("✅ Single document demo complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}")
        raise


def demo_custom_chunking():
    """
    Demo: Experiment with different chunking strategies.
    
    Compares:
    - Small chunks (300 tokens, 30 overlap)
    - Default chunks (500 tokens, 50 overlap)
    - Large chunks (800 tokens, 80 overlap)
    """
    logger.info("\n" + "="*70)
    logger.info("⚙️  Demo: Custom Chunking Strategies")
    logger.info("="*70)
    
    try:
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        
        # Ensure index exists
        if not indexer.index_exists():
            indexer.create_index()
        
        # Pick a test file
        policy_file = Path("data/policies/underwriting_standards.pdf")
        
        if not policy_file.exists():
            policy_dir = Path("data/policies")
            policy_files = list(policy_dir.glob("*.pdf"))
            if not policy_files:
                logger.error("No PDFs found")
                return
            policy_file = policy_files[0]
        
        logger.info(f"\n📄 Test document: {policy_file.name}")
        
        # Test different chunking strategies
        strategies = [
            ("Small chunks", 300, 30),
            ("Default chunks", 500, 50),
            ("Large chunks", 800, 80)
        ]
        
        results = []
        
        for name, chunk_size, overlap in strategies:
            logger.info(f"\n{'-'*70}")
            logger.info(f"⚙️  Testing: {name} ({chunk_size} tokens, {overlap} overlap)")
            logger.info(f"{'-'*70}")
            
            chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)
            
            # Reset cost tracking
            embedder.reset_cost_tracking()
            
            # Index with this strategy
            stats = indexer.index_documents(
                file_paths=[policy_file],
                embedder=embedder,
                chunker=chunker
            )
            
            results.append({
                "name": name,
                "chunk_size": chunk_size,
                "total_chunks": stats['total_chunks'],
                "total_tokens": stats['total_tokens'],
                "total_cost": stats['total_cost']
            })
            
            logger.info(f"  Chunks: {stats['total_chunks']}")
            logger.info(f"  Tokens: {stats['total_tokens']}")
            logger.info(f"  Cost: ${stats['total_cost']:.6f}")
        
        # Compare results
        logger.info(f"\n{'='*70}")
        logger.info("📊 Strategy Comparison")
        logger.info(f"{'='*70}")
        
        logger.info(f"\n{'Strategy':<20} {'Chunks':<10} {'Tokens':<10} {'Cost':<10}")
        logger.info("-" * 70)
        
        for result in results:
            logger.info(
                f"{result['name']:<20} "
                f"{result['total_chunks']:<10} "
                f"{result['total_tokens']:<10} "
                f"${result['total_cost']:<9.6f}"
            )
        
        logger.info("\n💡 Observations:")
        logger.info("  - Smaller chunks = more chunks, more API calls, higher cost")
        logger.info("  - Larger chunks = fewer chunks, fewer calls, lower cost")
        logger.info("  - Trade-off: granularity vs cost vs retrieval precision")
        
        logger.info("\n" + "="*70)
        logger.info("✅ Chunking comparison complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Demo: Policy upload and indexing pipeline (T042)"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "single", "chunking"],
        default="full",
        help="Demo mode: full pipeline, single document, or chunking comparison"
    )
    
    args = parser.parse_args()
    
    if args.mode == "full":
        demo_complete_pipeline()
    elif args.mode == "single":
        demo_single_document()
    elif args.mode == "chunking":
        demo_custom_chunking()
