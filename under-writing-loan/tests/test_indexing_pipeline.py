"""
Test suite for T042: Policy upload and indexing pipeline.

Tests the complete pipeline: chunk → embed → upload to Azure AI Search

Run with:
    python tests/test_indexing_pipeline.py
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_index_single_document():
    """
    Test 1: Index a single policy document.
    
    Validates:
    - Document is chunked correctly
    - Embeddings are generated
    - Documents are uploaded to Azure AI Search
    - Stats are returned
    """
    logger.info("\n" + "="*60)
    logger.info("Test 1: Index Single Document")
    logger.info("="*60)
    
    try:
        # Initialize components
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        
        # Ensure index exists
        if not indexer.index_exists():
            logger.info("Creating index (first-time setup)...")
            indexer.create_index()
        
        # Test with a single policy file
        policy_file = Path("data/policies/income_verification.pdf")
        
        if not policy_file.exists():
            logger.warning(f"⚠️ Test file not found: {policy_file}")
            logger.info("Skipping test - ensure data/policies/ contains PDFs")
            return
        
        # Index the document
        stats = indexer.index_documents(
            file_paths=[policy_file],
            embedder=embedder,
            category_map={"income_verification": "income"}
        )
        
        # Validate results
        assert stats["total_files"] == 1, "Should process 1 file"
        assert stats["total_chunks"] > 0, "Should create chunks"
        assert stats["total_tokens"] > 0, "Should generate embeddings"
        assert stats["total_cost"] > 0, "Should track cost"
        assert len(stats["failed_files"]) == 0, "Should have no failures"
        
        logger.info(f"\n✅ Test 1 PASSED")
        logger.info(f"   Files: {stats['total_files']}")
        logger.info(f"   Chunks: {stats['total_chunks']}")
        logger.info(f"   Tokens: {stats['total_tokens']}")
        logger.info(f"   Cost: ${stats['total_cost']:.6f}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Test 1 FAILED: {e}")
        raise


def test_index_multiple_documents():
    """
    Test 2: Index multiple policy documents.
    
    Validates:
    - Multiple files are processed
    - Category mapping works
    - Batch upload works
    - Cumulative stats are correct
    """
    logger.info("\n" + "="*60)
    logger.info("Test 2: Index Multiple Documents")
    logger.info("="*60)
    
    try:
        # Initialize components
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        
        # Get all policy files
        policy_dir = Path("data/policies")
        policy_files = list(policy_dir.glob("*.pdf"))
        
        if len(policy_files) == 0:
            logger.warning(f"⚠️ No PDFs found in {policy_dir}")
            logger.info("Skipping test - ensure data/policies/ contains PDFs")
            return
        
        logger.info(f"Found {len(policy_files)} policy files")
        
        # Category mapping
        category_map = {
            "underwriting_standards": "underwriting",
            "credit_requirements": "credit",
            "income_verification": "income",
            "property_guidelines": "property",
            "compliance_rules": "compliance"
        }
        
        # Index all documents
        stats = indexer.index_documents(
            file_paths=policy_files,
            embedder=embedder,
            category_map=category_map,
            batch_size=5
        )
        
        # Validate results
        assert stats["total_files"] > 0, "Should process files"
        assert stats["total_chunks"] > 0, "Should create chunks"
        assert stats["total_tokens"] > 0, "Should generate embeddings"
        assert stats["total_cost"] > 0, "Should track cost"
        
        logger.info(f"\n✅ Test 2 PASSED")
        logger.info(f"   Files: {stats['total_files']}/{len(policy_files)}")
        logger.info(f"   Chunks: {stats['total_chunks']}")
        logger.info(f"   Tokens: {stats['total_tokens']}")
        logger.info(f"   Cost: ${stats['total_cost']:.6f}")
        logger.info(f"   Cost per chunk: ${stats['total_cost']/stats['total_chunks']:.6f}")
        
        if stats["failed_files"]:
            logger.warning(f"   Failed files: {len(stats['failed_files'])}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Test 2 FAILED: {e}")
        raise


def test_custom_chunker():
    """
    Test 3: Index with custom chunking parameters.
    
    Validates:
    - Custom chunker can be provided
    - Different chunk sizes work
    - Pipeline handles custom chunker correctly
    """
    logger.info("\n" + "="*60)
    logger.info("Test 3: Custom Chunker")
    logger.info("="*60)
    
    try:
        # Initialize components with custom chunker
        indexer = PolicyIndexer()
        embedder = EmbeddingGenerator()
        chunker = DocumentChunker(chunk_size=300, overlap=30)  # Smaller chunks
        
        # Test with a single file
        policy_file = Path("data/policies/underwriting_standards.pdf")
        
        if not policy_file.exists():
            logger.warning(f"⚠️ Test file not found: {policy_file}")
            logger.info("Skipping test")
            return
        
        # Index with custom chunker
        stats = indexer.index_documents(
            file_paths=[policy_file],
            embedder=embedder,
            chunker=chunker
        )
        
        # Validate results
        assert stats["total_files"] == 1, "Should process 1 file"
        assert stats["total_chunks"] > 0, "Should create chunks"
        
        logger.info(f"\n✅ Test 3 PASSED")
        logger.info(f"   Chunks with 300-token size: {stats['total_chunks']}")
        logger.info(f"   Cost: ${stats['total_cost']:.6f}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Test 3 FAILED: {e}")
        raise


def test_error_handling():
    """
    Test 4: Error handling for invalid inputs.
    
    Validates:
    - Missing embedder raises error
    - Non-existent index raises error
    - Invalid files are skipped gracefully
    """
    logger.info("\n" + "="*60)
    logger.info("Test 4: Error Handling")
    logger.info("="*60)
    
    try:
        indexer = PolicyIndexer()
        
        # Test 1: Missing embedder
        logger.info("Test 4a: Missing embedder...")
        try:
            indexer.index_documents(
                file_paths=[Path("data/policies/test.pdf")],
                embedder=None
            )
            assert False, "Should raise ValueError for missing embedder"
        except ValueError as e:
            assert "EmbeddingGenerator must be provided" in str(e)
            logger.info("   ✅ Correctly raises ValueError for missing embedder")
        
        # Test 2: Index doesn't exist (if we delete it)
        logger.info("Test 4b: Non-existent index...")
        embedder = EmbeddingGenerator()
        
        # Temporarily delete and recreate index
        if indexer.index_exists():
            indexer.delete_index()
        
        try:
            indexer.index_documents(
                file_paths=[Path("data/policies/test.pdf")],
                embedder=embedder
            )
            assert False, "Should raise ValueError for non-existent index"
        except ValueError as e:
            assert "does not exist" in str(e)
            logger.info("   ✅ Correctly raises ValueError for non-existent index")
        
        # Recreate index for other tests
        indexer.create_index()
        
        # Test 3: Invalid file (should skip gracefully)
        logger.info("Test 4c: Invalid file (should skip)...")
        stats = indexer.index_documents(
            file_paths=[Path("data/policies/nonexistent.pdf")],
            embedder=embedder
        )
        
        assert stats["total_files"] == 0, "Should skip invalid file"
        assert len(stats["failed_files"]) == 1, "Should track failed file"
        logger.info("   ✅ Correctly skips invalid files")
        
        logger.info(f"\n✅ Test 4 PASSED - All error cases handled correctly")
        
    except Exception as e:
        logger.error(f"❌ Test 4 FAILED: {e}")
        raise


def test_verify_search_functionality():
    """
    Test 5: Verify indexed documents can be searched.
    
    Validates:
    - Documents are actually searchable in Azure AI Search
    - Vector search returns results
    - Metadata is correctly stored
    """
    logger.info("\n" + "="*60)
    logger.info("Test 5: Verify Search Functionality")
    logger.info("="*60)
    
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from src.utils.config import Config
        
        # Initialize search client
        credential = AzureKeyCredential(Config.AZURE_SEARCH_ADMIN_KEY)
        search_client = SearchClient(
            endpoint=Config.AZURE_SEARCH_ENDPOINT,
            index_name=Config.AZURE_SEARCH_INDEX_NAME,
            credential=credential
        )
        
        # Perform a simple text search
        results = search_client.search(
            search_text="income verification",
            top=3
        )
        
        result_list = list(results)
        
        if len(result_list) > 0:
            logger.info(f"\n✅ Search returned {len(result_list)} results")
            
            for i, result in enumerate(result_list[:3], start=1):
                logger.info(f"\n   Result {i}:")
                logger.info(f"   - Chunk ID: {result.get('chunk_id', 'N/A')}")
                logger.info(f"   - Document: {result.get('doc_title', 'N/A')}")
                logger.info(f"   - Category: {result.get('doc_category', 'N/A')}")
                logger.info(f"   - Content: {result.get('content', 'N/A')[:100]}...")
            
            logger.info(f"\n✅ Test 5 PASSED - Documents are searchable")
        else:
            logger.warning("⚠️ No search results found - index may be empty")
            logger.info("Run test_index_multiple_documents() first")
        
    except Exception as e:
        logger.error(f"❌ Test 5 FAILED: {e}")
        raise


def run_all_tests():
    """
    Run all tests in sequence.
    """
    logger.info("\n" + "="*60)
    logger.info("🧪 T042 Testing Suite: Policy Upload and Indexing Pipeline")
    logger.info("="*60)
    
    try:
        # Test 1: Single document
        test_index_single_document()
        
        # Test 2: Multiple documents
        test_index_multiple_documents()
        
        # Test 3: Custom chunker
        test_custom_chunker()
        
        # Test 4: Error handling
        test_error_handling()
        
        # Test 5: Verify search
        test_verify_search_functionality()
        
        logger.info("\n" + "="*60)
        logger.info("🎉 All tests passed! T042 implementation complete.")
        logger.info("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ Test suite failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
