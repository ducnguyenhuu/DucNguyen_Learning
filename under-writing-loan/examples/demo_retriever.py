"""
Demo script for T043: Semantic search retriever.

This demonstrates semantic search capabilities for policy retrieval.

Run with:
    python examples/demo_retriever.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import logging
from src.rag.retriever import PolicyRetriever

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_search():
    """
    Demo 1: Basic semantic search with various queries.
    
    Shows how semantic search understands intent and finds relevant policies.
    """
    logger.info("\n" + "="*70)
    logger.info("🔍 Demo 1: Basic Semantic Search")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        # Test various queries
        queries = [
            "What is the maximum debt-to-income ratio allowed?",
            "What credit score do I need?",
            "How do you verify income?",
            "What are the property requirements?",
            "Are there compliance rules for documentation?"
        ]
        
        logger.info(f"\nTesting {len(queries)} different queries...\n")
        
        for i, query in enumerate(queries, start=1):
            logger.info(f"{'-'*70}")
            logger.info(f"Query {i}: {query}")
            logger.info(f"{'-'*70}")
            
            results = retriever.search(query)
            
            if results:
                logger.info(f"\n✅ Found {len(results)} relevant policy chunks:\n")
                
                for j, result in enumerate(results, start=1):
                    logger.info(f"   {j}. {result['doc_title']}")
                    logger.info(f"      Category: {result['doc_category']}")
                    logger.info(f"      Score: {result['score']:.3f}")
                    logger.info(f"      Content: {result['content'][:200]}...")
                    logger.info("")
            else:
                logger.warning("   ⚠️ No results found")
            
            logger.info("")
        
        logger.info("="*70)
        logger.info("✅ Demo 1 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 1 failed: {e}")
        raise


def demo_category_filtering():
    """
    Demo 2: Category-filtered search.
    
    Shows how to narrow search to specific policy categories.
    """
    logger.info("\n" + "="*70)
    logger.info("🏷️  Demo 2: Category-Filtered Search")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        query = "What are the requirements?"
        
        # Get all categories
        categories = ["credit", "income", "underwriting", "property", "compliance"]
        
        logger.info(f"\nQuery: '{query}'")
        logger.info(f"Testing across {len(categories)} categories...\n")
        
        for category in categories:
            logger.info(f"{'-'*70}")
            logger.info(f"Category: {category}")
            logger.info(f"{'-'*70}")
            
            results = retriever.search(query, category_filter=category)
            
            if results:
                logger.info(f"\n✅ Found {len(results)} results in '{category}' category:\n")
                
                for i, result in enumerate(results, start=1):
                    logger.info(f"   {i}. {result['doc_title']} (score: {result['score']:.3f})")
                    logger.info(f"      {result['content'][:150]}...")
                    logger.info("")
            else:
                logger.info(f"\n   No results in '{category}' category")
            
            logger.info("")
        
        logger.info("="*70)
        logger.info("✅ Demo 2 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 2 failed: {e}")
        raise


def demo_context_generation():
    """
    Demo 3: Generate context string for LLM prompts.
    
    Shows how to prepare retrieved context for GPT-4 compliance checking.
    """
    logger.info("\n" + "="*70)
    logger.info("📝 Demo 3: Context String Generation for LLM")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        compliance_questions = [
            "Is a DTI of 38% acceptable?",
            "Can we approve someone with a 650 credit score?",
            "What income documentation is required?"
        ]
        
        logger.info(f"\nGenerating context for {len(compliance_questions)} compliance questions...\n")
        
        for i, question in enumerate(compliance_questions, start=1):
            logger.info(f"{'-'*70}")
            logger.info(f"Question {i}: {question}")
            logger.info(f"{'-'*70}")
            
            # Get context string with metadata
            context = retriever.get_context_string(question, include_metadata=True)
            
            if context:
                logger.info(f"\n✅ Generated context ({len(context)} chars):\n")
                logger.info(context[:500] + "..." if len(context) > 500 else context)
                
                # Show how to use in prompt
                logger.info(f"\n💡 Example LLM Prompt:")
                logger.info(f"{'-'*70}")
                prompt = f"""Based on these lending policies:

{context}

Question: {question}

Answer: """
                logger.info(prompt[:400] + "..." if len(prompt) > 400 else prompt)
            else:
                logger.warning("   ⚠️ No relevant context found")
            
            logger.info("\n")
        
        logger.info("="*70)
        logger.info("✅ Demo 3 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 3 failed: {e}")
        raise


def demo_similarity_comparison():
    """
    Demo 4: Compare similarity scores across queries.
    
    Shows how well semantic search understands different phrasings.
    """
    logger.info("\n" + "="*70)
    logger.info("📊 Demo 4: Similarity Score Comparison")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        # Same concept, different phrasings
        query_groups = [
            {
                "concept": "Debt-to-Income Ratio",
                "queries": [
                    "What is the maximum DTI?",
                    "What is the maximum debt-to-income ratio?",
                    "How much debt can someone have relative to income?",
                    "What's the limit on monthly debt compared to earnings?"
                ]
            },
            {
                "concept": "Credit Score",
                "queries": [
                    "What credit score is required?",
                    "Minimum FICO score?",
                    "What's the credit requirement?",
                    "How good does your credit need to be?"
                ]
            }
        ]
        
        for group in query_groups:
            logger.info(f"\n{'-'*70}")
            logger.info(f"Concept: {group['concept']}")
            logger.info(f"{'-'*70}\n")
            
            for query in group['queries']:
                logger.info(f"Query: \"{query}\"")
                
                results = retriever.search(query)
                
                if results:
                    logger.info(f"  Top result: {results[0]['doc_title']}")
                    logger.info(f"  Score: {results[0]['score']:.3f}")
                    logger.info(f"  Match: {results[0]['content'][:100]}...")
                else:
                    logger.info(f"  No results")
                
                logger.info("")
        
        logger.info("="*70)
        logger.info("✅ Demo 4 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 4 failed: {e}")
        raise


def demo_retrieval_stats():
    """
    Demo 5: Retrieval statistics and analysis.
    
    Shows detailed metrics about search quality and coverage.
    """
    logger.info("\n" + "="*70)
    logger.info("📈 Demo 5: Retrieval Statistics")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        test_queries = [
            "debt-to-income ratio",
            "credit score requirements",
            "income verification methods",
            "property appraisal standards"
        ]
        
        logger.info(f"\nAnalyzing {len(test_queries)} queries...\n")
        
        all_stats = []
        
        for query in test_queries:
            stats = retriever.get_retrieval_stats(query)
            all_stats.append(stats)
            
            logger.info(f"{'-'*70}")
            logger.info(f"Query: {query}")
            logger.info(f"{'-'*70}")
            logger.info(f"  Results: {stats['results_count']}")
            logger.info(f"  Avg Score: {stats['avg_score']:.3f}")
            logger.info(f"  Score Range: {stats['min_score']:.3f} - {stats['max_score']:.3f}")
            logger.info(f"  Categories: {', '.join(stats['categories']) if stats['categories'] else 'None'}")
            logger.info(f"  Content Length: {stats['total_content_length']} chars")
            logger.info("")
        
        # Summary statistics
        logger.info(f"{'='*70}")
        logger.info("📊 Summary Statistics")
        logger.info(f"{'='*70}")
        
        total_results = sum(s['results_count'] for s in all_stats)
        avg_score = sum(s['avg_score'] for s in all_stats if s['results_count'] > 0) / len([s for s in all_stats if s['results_count'] > 0])
        all_categories = set()
        for s in all_stats:
            all_categories.update(s['categories'])
        
        logger.info(f"  Total queries: {len(test_queries)}")
        logger.info(f"  Total results: {total_results}")
        logger.info(f"  Average results per query: {total_results / len(test_queries):.1f}")
        logger.info(f"  Average similarity score: {avg_score:.3f}")
        logger.info(f"  Categories covered: {', '.join(sorted(all_categories))}")
        
        logger.info("\n" + "="*70)
        logger.info("✅ Demo 5 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 5 failed: {e}")
        raise


def demo_rag_workflow():
    """
    Demo 6: Complete RAG workflow simulation.
    
    Shows end-to-end flow: Query → Retrieve → Context → Answer
    """
    logger.info("\n" + "="*70)
    logger.info("🔄 Demo 6: Complete RAG Workflow")
    logger.info("="*70)
    
    try:
        retriever = PolicyRetriever()
        
        # Simulated user questions
        user_questions = [
            "Can we approve an applicant with a DTI of 42%?",
            "Is a credit score of 620 sufficient?",
            "What documents do we need to verify income?"
        ]
        
        logger.info("\nSimulating complete RAG workflow for compliance checking...\n")
        
        for i, question in enumerate(user_questions, start=1):
            logger.info(f"{'='*70}")
            logger.info(f"Workflow {i}: {question}")
            logger.info(f"{'='*70}\n")
            
            # Step 1: Retrieve relevant policies
            logger.info("Step 1: Retrieve relevant policy chunks")
            results = retriever.search(question)
            logger.info(f"  ✅ Retrieved {len(results)} relevant chunks\n")
            
            # Step 2: Build context
            logger.info("Step 2: Build context for LLM")
            context = retriever.get_context_string(question, include_metadata=True)
            logger.info(f"  ✅ Context: {len(context)} characters\n")
            
            # Step 3: Show retrieved policies
            logger.info("Step 3: Review retrieved policies")
            for j, result in enumerate(results, start=1):
                logger.info(f"  Policy {j}: {result['doc_title']}")
                logger.info(f"    Category: {result['doc_category']}")
                logger.info(f"    Relevance: {result['score']:.3f}")
                logger.info(f"    Content: {result['content'][:150]}...")
                logger.info("")
            
            # Step 4: Simulate LLM prompt
            logger.info("Step 4: Prepare LLM prompt (simulated)")
            prompt_template = f"""You are a lending compliance assistant.

Based on these company policies:
{context[:300]}...

Question: {question}

Provide a clear answer citing specific policies."""
            
            logger.info(f"  ✅ Prompt ready ({len(prompt_template)} chars)")
            logger.info(f"\n  Preview:")
            logger.info(f"  {'-'*66}")
            logger.info(f"  {prompt_template[:250]}...")
            logger.info(f"  {'-'*66}\n")
            
            logger.info("💡 Next: Send prompt to GPT-4 for grounded answer\n")
        
        logger.info("="*70)
        logger.info("✅ Demo 6 Complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ Demo 6 failed: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Demo: Semantic search retriever (T043)"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "basic", "category", "context", "similarity", "stats", "rag"],
        default="all",
        help="Demo mode to run"
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == "all" or args.mode == "basic":
            demo_basic_search()
        
        if args.mode == "all" or args.mode == "category":
            demo_category_filtering()
        
        if args.mode == "all" or args.mode == "context":
            demo_context_generation()
        
        if args.mode == "all" or args.mode == "similarity":
            demo_similarity_comparison()
        
        if args.mode == "all" or args.mode == "stats":
            demo_retrieval_stats()
        
        if args.mode == "all" or args.mode == "rag":
            demo_rag_workflow()
        
        logger.info("\n" + "="*70)
        logger.info("🎉 All demos complete!")
        logger.info("="*70)
        logger.info("\n💡 Next Steps:")
        logger.info("  - Integrate PolicyRetriever into ComplianceAgent (T047)")
        logger.info("  - Create notebook demo (T044)")
        logger.info("  - Add interactive search widget (T045)")
        
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}")
        logger.error("\nMake sure the index is populated:")
        logger.error("  python examples/demo_indexing_pipeline.py")
        raise
