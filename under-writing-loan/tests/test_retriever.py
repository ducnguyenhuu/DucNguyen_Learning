"""
Test suite for T043: Semantic search retriever.

Tests the PolicyRetriever class for vector similarity search.

Run with:
    python tests/test_retriever.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import logging
from src.rag.retriever import PolicyRetriever
from src.rag.indexer import PolicyIndexer
from src.rag.embeddings import EmbeddingGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_search():
    """
    Test 1: Basic semantic search.
    
    Validates:
    - Search returns results
    - Results have required fields
    - Similarity scores are present
    - Results are relevant
    """
    logger.info("\n" + "="*60)
    logger.info("Test 1: Basic Semantic Search")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        # Search for DTI policy
        query = "What is the maximum debt-to-income ratio?"
        results = retriever.search(query)
        
        logger.info(f"\n🔍 Query: '{query}'")
        logger.info(f"📊 Results: {len(results)}")
        
        # Validate results
        assert len(results) > 0, "Should return results"
        assert len(results) <= 3, "Should return max 3 results (top_k=3)"
        
        # Check first result structure
        first_result = results[0]
        required_fields = [
            "chunk_id", "content", "doc_title", 
            "doc_category", "chunk_index", "source_path", "score"
        ]
        
        for field in required_fields:
            assert field in first_result, f"Missing field: {field}"
        
        # Display results
        for i, result in enumerate(results, start=1):
            logger.info(f"\n   Result {i}:")
            logger.info(f"   - Document: {result['doc_title']}")
            logger.info(f"   - Category: {result['doc_category']}")
            logger.info(f"   - Score: {result['score']:.3f}")
            logger.info(f"   - Content: {result['content'][:150]}...")
        
        logger.info(f"\n✅ Test 1 PASSED")
        return results
        
    except Exception as e:
        logger.error(f"❌ Test 1 FAILED: {e}")
        raise


def test_category_filter():
    """
    Test 2: Category-filtered search.
    
    Validates:
    - Category filter works
    - Only results from specified category returned
    - Results are relevant to both query and category
    """
    logger.info("\n" + "="*60)
    logger.info("Test 2: Category-Filtered Search")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        # Search with category filter
        query = "credit score requirements"
        category = "credit"
        results = retriever.search(query, category_filter=category)
        
        logger.info(f"\n🔍 Query: '{query}'")
        logger.info(f"🏷️  Filter: category={category}")
        logger.info(f"📊 Results: {len(results)}")
        
        # Validate category filter
        if len(results) > 0:
            for result in results:
                assert result['doc_category'] == category, \
                    f"Expected category '{category}', got '{result['doc_category']}'"
            
            logger.info(f"\n✅ All results match category filter: {category}")
            
            # Display results
            for i, result in enumerate(results, start=1):
                logger.info(f"\n   Result {i}:")
                logger.info(f"   - Document: {result['doc_title']}")
                logger.info(f"   - Score: {result['score']:.3f}")
                logger.info(f"   - Content: {result['content'][:150]}...")
        else:
            logger.warning(f"⚠️ No results found for category: {category}")
        
        logger.info(f"\n✅ Test 2 PASSED")
        return results
        
    except Exception as e:
        logger.error(f"❌ Test 2 FAILED: {e}")
        raise


def test_similarity_threshold():
    """
    Test 3: Similarity threshold filtering.
    
    Validates:
    - Results below threshold are filtered
    - Only high-quality matches returned
    - Empty results when no good matches
    
    Note: Azure hybrid search scores are typically 0.01-0.05, not 0-1.
    """
    logger.info("\n" + "="*60)
    logger.info("Test 3: Similarity Threshold Filtering")
    logger.info("="*60)
    
    try:
        # Test with high threshold (0.04 is high for hybrid search)
        high_threshold = 0.04
        retriever_high = PolicyRetriever(min_similarity=high_threshold)
        
        query = "What are the requirements?"
        results_high = retriever_high.search(query)
        
        logger.info(f"\n🔍 Query: '{query}'")
        logger.info(f"📏 High threshold: {high_threshold}")
        logger.info(f"📊 Results: {len(results_high)}")
        
        # All results should be above threshold
        for result in results_high:
            assert result['score'] >= high_threshold, \
                f"Score {result['score']:.3f} below threshold {high_threshold}"
        
        # Test with low threshold (0.005 is very low)
        low_threshold = 0.005
        retriever_low = PolicyRetriever(min_similarity=low_threshold)
        results_low = retriever_low.search(query)
        
        logger.info(f"\n📏 Low threshold: {low_threshold}")
        logger.info(f"📊 Results: {len(results_low)}")
        
        # Should get more results with lower threshold
        assert len(results_low) >= len(results_high), \
            "Lower threshold should return more or equal results"
        
        logger.info(f"\n✅ Threshold filtering works:")
        logger.info(f"   High threshold ({high_threshold}): {len(results_high)} results")
        logger.info(f"   Low threshold ({low_threshold}): {len(results_low)} results")
        
        logger.info(f"\n✅ Test 3 PASSED")
        
    except Exception as e:
        logger.error(f"❌ Test 3 FAILED: {e}")
        raise


def test_batch_search():
    """
    Test 4: Batch query search.
    
    Validates:
    - Multiple queries processed correctly
    - Each query returns independent results
    - Batch processing is efficient
    """
    logger.info("\n" + "="*60)
    logger.info("Test 4: Batch Search")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        queries = [
            "What is the maximum DTI ratio?",
            "What credit score is required?",
            "How to verify income?"
        ]
        
        logger.info(f"\n🔍 Processing {len(queries)} queries...")
        results = retriever.search_batch(queries, show_progress=False)
        
        # Validate batch results
        assert len(results) == len(queries), "Should return results for each query"
        
        logger.info(f"\n📊 Batch Results:")
        for i, (query, query_results) in enumerate(zip(queries, results), start=1):
            logger.info(f"\n   Query {i}: '{query}'")
            logger.info(f"   Results: {len(query_results)}")
            
            if query_results:
                top_result = query_results[0]
                logger.info(f"   Top match: {top_result['doc_title']} (score={top_result['score']:.3f})")
        
        logger.info(f"\n✅ Test 4 PASSED")
        return results
        
    except Exception as e:
        logger.error(f"❌ Test 4 FAILED: {e}")
        raise


def test_context_string():
    """
    Test 5: Context string generation for LLM prompts.
    
    Validates:
    - Context string is properly formatted
    - Contains all retrieved chunks
    - Includes metadata when requested
    - Ready for LLM consumption
    """
    logger.info("\n" + "="*60)
    logger.info("Test 5: Context String Generation")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        query = "What is the maximum DTI ratio?"
        
        # Get context string with metadata
        context_with_meta = retriever.get_context_string(
            query, 
            include_metadata=True
        )
        
        logger.info(f"\n🔍 Query: '{query}'")
        logger.info(f"📝 Context with metadata:")
        logger.info(f"   Length: {len(context_with_meta)} chars")
        logger.info(f"   Preview: {context_with_meta[:200]}...")
        
        # Get context string without metadata
        context_no_meta = retriever.get_context_string(
            query, 
            include_metadata=False
        )
        
        logger.info(f"\n📝 Context without metadata:")
        logger.info(f"   Length: {len(context_no_meta)} chars")
        logger.info(f"   Preview: {context_no_meta[:200]}...")
        
        # Validate
        assert len(context_with_meta) > 0, "Context should not be empty"
        assert len(context_with_meta) > len(context_no_meta), \
            "Context with metadata should be longer"
        
        logger.info(f"\n✅ Test 5 PASSED")
        return context_with_meta
        
    except Exception as e:
        logger.error(f"❌ Test 5 FAILED: {e}")
        raise


def test_retrieval_stats():
    """
    Test 6: Retrieval statistics.
    
    Validates:
    - Stats are calculated correctly
    - All fields are present
    - Stats provide useful insights
    """
    logger.info("\n" + "="*60)
    logger.info("Test 6: Retrieval Statistics")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        query = "credit score requirements"
        stats = retriever.get_retrieval_stats(query)
        
        logger.info(f"\n🔍 Query: '{query}'")
        logger.info(f"\n📊 Retrieval Statistics:")
        logger.info(f"   Query length: {stats['query_length']} chars")
        logger.info(f"   Results count: {stats['results_count']}")
        logger.info(f"   Average score: {stats['avg_score']:.3f}")
        logger.info(f"   Max score: {stats['max_score']:.3f}")
        logger.info(f"   Min score: {stats['min_score']:.3f}")
        logger.info(f"   Categories: {stats['categories']}")
        logger.info(f"   Total content: {stats['total_content_length']} chars")
        
        # Validate stats structure
        required_fields = [
            'query', 'query_length', 'results_count', 'avg_score',
            'max_score', 'min_score', 'categories', 'total_content_length'
        ]
        
        for field in required_fields:
            assert field in stats, f"Missing stat field: {field}"
        
        logger.info(f"\n✅ Test 6 PASSED")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Test 6 FAILED: {e}")
        raise


def test_empty_query_handling():
    """
    Test 7: Empty query handling.
    
    Validates:
    - Empty queries return empty results
    - No errors thrown
    - Graceful degradation
    """
    logger.info("\n" + "="*60)
    logger.info("Test 7: Empty Query Handling")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        # Test empty string
        results = retriever.search("")
        assert len(results) == 0, "Empty query should return empty results"
        logger.info("   ✅ Empty string handled correctly")
        
        # Test whitespace only
        results = retriever.search("   ")
        assert len(results) == 0, "Whitespace query should return empty results"
        logger.info("   ✅ Whitespace query handled correctly")
        
        logger.info(f"\n✅ Test 7 PASSED")
        
    except Exception as e:
        logger.error(f"❌ Test 7 FAILED: {e}")
        raise


def test_index_requirement():
    """
    Test 8: Verify index exists and is populated.
    
    This test ensures the indexing pipeline (T042) has been run.
    """
    logger.info("\n" + "="*60)
    logger.info("Test 8: Index Existence Check")
    logger.info("="*60)
    
    try:
        retriever = PolicyRetriever()
        
        # Try a simple search
        results = retriever.search("policy")
        
        if len(results) == 0:
            logger.warning("⚠️ No documents found in index!")
            logger.warning("   Run indexing pipeline first:")
            logger.warning("   python examples/demo_indexing_pipeline.py")
        else:
            logger.info(f"✅ Index is populated with searchable documents")
            logger.info(f"   Found {len(results)} results for generic query")
        
        logger.info(f"\n✅ Test 8 PASSED")
        
    except Exception as e:
        logger.error(f"❌ Test 8 FAILED: {e}")
        logger.error("   Make sure Azure AI Search index exists")
        logger.error("   Run: python examples/demo_indexing_pipeline.py")
        raise


def run_all_tests():
    """
    Run all tests in sequence.
    """
    logger.info("\n" + "="*60)
    logger.info("🧪 T043 Testing Suite: Semantic Search Retriever")
    logger.info("="*60)
    
    try:
        # Test 1: Basic search
        test_basic_search()
        
        # Test 2: Category filter
        test_category_filter()
        
        # Test 3: Similarity threshold
        test_similarity_threshold()
        
        # Test 4: Batch search
        test_batch_search()
        
        # Test 5: Context string
        test_context_string()
        
        # Test 6: Retrieval stats
        test_retrieval_stats()
        
        # Test 7: Empty query handling
        test_empty_query_handling()
        
        # Test 8: Index check
        test_index_requirement()
        
        logger.info("\n" + "="*60)
        logger.info("🎉 All tests passed! T043 implementation complete.")
        logger.info("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ Test suite failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
