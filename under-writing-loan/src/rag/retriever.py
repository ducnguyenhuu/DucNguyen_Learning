"""
Semantic search retriever for policy documents using Azure AI Search.

This module handles:
- Query embedding using Azure OpenAI
- Vector similarity search in Azure AI Search
- Top-K retrieval with scoring
- Hybrid search (vector + keyword)

Based on research.md decision:
- Top-K: 3 chunks per query
- Search type: Hybrid (vector + keyword)
- Similarity threshold: 0.5 minimum
"""

import logging
from typing import List, Optional, Dict, Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from rag.embeddings import EmbeddingGenerator
from utils.config import Config

logger = logging.getLogger(__name__)


class PolicyRetriever:
    """
    Retrieve relevant policy chunks using semantic search.
    
    This class performs hybrid search (vector + keyword) on indexed
    policy documents to find the most relevant chunks for a query.
    
    Features:
    - Query embedding using Ada-002
    - Cosine similarity search
    - Top-K retrieval (default: 3)
    - Similarity score filtering (threshold: 0.01 for hybrid search scores)
    - Hybrid search for best results
    
    Examples:
        >>> retriever = PolicyRetriever()
        >>> results = retriever.search("What is the maximum DTI ratio?")
        >>> for result in results:
        ...     print(f"Score: {result['score']:.3f}")
        ...     print(f"Content: {result['content'][:100]}...")
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        embedder: Optional[EmbeddingGenerator] = None,
        top_k: int = 3,
        min_similarity: float = 0.01
    ):
        """
        Initialize PolicyRetriever with Azure AI Search credentials.
        
        Args:
            endpoint: Azure AI Search endpoint URL (defaults to Config)
            api_key: Azure AI Search query key (defaults to Config)
            index_name: Name of the search index (defaults to Config)
            embedder: EmbeddingGenerator instance (creates default if None)
            top_k: Number of top results to return (default: 3)
            min_similarity: Minimum similarity score threshold (default: 0.01)
                Note: Azure hybrid search scores are typically in the 0.01-0.05 range,
                not 0-1 like pure cosine similarity.
        
        Raises:
            ValueError: If credentials are missing
        
        Examples:
            >>> # Use default configuration
            >>> retriever = PolicyRetriever()
            
            >>> # Custom configuration
            >>> embedder = EmbeddingGenerator()
            >>> retriever = PolicyRetriever(
            ...     embedder=embedder,
            ...     top_k=5,
            ...     min_similarity=0.02
            ... )
        """
        self.endpoint = endpoint or Config.AZURE_SEARCH_ENDPOINT
        self.api_key = api_key or Config.AZURE_SEARCH_ADMIN_KEY
        self.index_name = index_name or Config.AZURE_SEARCH_INDEX_NAME
        self.top_k = top_k
        self.min_similarity = min_similarity
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure AI Search credentials not configured. "
                "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY in .env"
            )
        
        # Initialize Search Client
        credential = AzureKeyCredential(self.api_key)
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=credential
        )
        
        # Initialize or use provided embedder
        if embedder is None:
            self.embedder = EmbeddingGenerator()
            logger.info("Created default EmbeddingGenerator for query embedding")
        else:
            self.embedder = embedder
        
        logger.info(
            f"PolicyRetriever initialized: index={self.index_name}, "
            f"top_k={self.top_k}, min_similarity={self.min_similarity}"
        )
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        include_scores: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant policy chunks using hybrid search.
        
        This method performs:
        1. Query embedding using Ada-002
        2. Vector similarity search (cosine)
        3. Keyword search (BM25)
        4. Result fusion and ranking
        5. Score filtering
        
        Args:
            query: Natural language search query
            top_k: Number of results to return (overrides default)
            category_filter: Filter by document category (e.g., "credit", "income")
            include_scores: Include similarity scores in results (default: True)
        
        Returns:
            List of result dictionaries with keys:
            - chunk_id: Unique chunk identifier
            - content: Policy text content
            - doc_title: Document title
            - doc_category: Document category
            - chunk_index: Position in document
            - source_path: Original file path
            - score: Similarity score (if include_scores=True)
        
        Examples:
            >>> retriever = PolicyRetriever()
            >>> 
            >>> # Basic search
            >>> results = retriever.search("What is the maximum DTI ratio?")
            >>> print(f"Found {len(results)} relevant chunks")
            >>> 
            >>> # Category-filtered search
            >>> results = retriever.search(
            ...     "credit score requirements",
            ...     category_filter="credit"
            ... )
            >>> 
            >>> # Get more results
            >>> results = retriever.search("income verification", top_k=5)
        """
        if not query or not query.strip():
            logger.warning("Empty query provided - returning empty results")
            return []
        
        # Use provided top_k or fall back to instance default
        k = top_k if top_k is not None else self.top_k
        
        logger.info(f"🔍 Searching for: '{query}' (top_k={k})")
        
        try:
            # Step 1: Embed query
            logger.info("   Step 1/3: Embedding query...")
            query_embedding = self.embedder.embed_text(query)
            logger.info(f"   ✅ Query embedded ({len(query_embedding)} dimensions)")
            
            # Step 2: Prepare vector query
            logger.info("   Step 2/3: Preparing vector search...")
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=k,
                fields="embedding"
            )
            
            # Step 3: Execute hybrid search
            logger.info("   Step 3/3: Executing hybrid search (vector + keyword)...")
            
            # Build filter expression
            filter_expr = None
            if category_filter:
                filter_expr = f"doc_category eq '{category_filter}'"
                logger.info(f"   Applying category filter: {category_filter}")
            
            # Execute search
            search_results = self.search_client.search(
                search_text=query,  # Keyword search
                vector_queries=[vector_query],  # Vector search
                filter=filter_expr,
                top=k,
                select=[
                    "chunk_id",
                    "content",
                    "doc_title",
                    "doc_category",
                    "chunk_index",
                    "source_path"
                ]
            )
            
            # Step 4: Process results
            results = []
            for i, result in enumerate(search_results, start=1):
                # Get similarity score (reranker score if available, else search score)
                score = result.get('@search.score', 0.0)
                
                # Filter by minimum similarity
                if score < self.min_similarity:
                    logger.debug(
                        f"   Result {i}: score={score:.3f} < threshold={self.min_similarity:.3f} - filtered"
                    )
                    continue
                
                # Build result dictionary
                result_dict = {
                    "chunk_id": result.get("chunk_id", ""),
                    "content": result.get("content", ""),
                    "doc_title": result.get("doc_title", ""),
                    "doc_category": result.get("doc_category", ""),
                    "chunk_index": result.get("chunk_index", 0),
                    "source_path": result.get("source_path", "")
                }
                
                if include_scores:
                    result_dict["score"] = score
                
                results.append(result_dict)
                
                logger.info(
                    f"   Result {i}: {result_dict['doc_title']} "
                    f"(chunk {result_dict['chunk_index']}, score={score:.3f})"
                )
            
            # Log summary
            if len(results) == 0:
                logger.warning(
                    f"   ⚠️ No results found above similarity threshold ({self.min_similarity})"
                )
            else:
                logger.info(f"   ✅ Retrieved {len(results)} relevant chunks")
            
            return results
        
        except Exception as e:
            logger.error(f"   ❌ Search failed: {e}")
            raise
    
    def search_batch(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
        show_progress: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        Search multiple queries in batch.
        
        Args:
            queries: List of natural language queries
            top_k: Number of results per query (overrides default)
            show_progress: Show progress logging (default: True)
        
        Returns:
            List of result lists, one per query
        
        Examples:
            >>> retriever = PolicyRetriever()
            >>> queries = [
            ...     "What is the maximum DTI?",
            ...     "Credit score requirements?",
            ...     "Income verification methods?"
            ... ]
            >>> results = retriever.search_batch(queries)
            >>> for i, query_results in enumerate(results):
            ...     print(f"Query {i+1}: {len(query_results)} results")
        """
        if show_progress:
            logger.info(f"🔍 Batch search: {len(queries)} queries")
        
        all_results = []
        
        for i, query in enumerate(queries, start=1):
            if show_progress:
                logger.info(f"\n📝 Query {i}/{len(queries)}: '{query}'")
            
            results = self.search(query, top_k=top_k)
            all_results.append(results)
        
        if show_progress:
            total_results = sum(len(r) for r in all_results)
            logger.info(
                f"\n✅ Batch search complete: {total_results} total results "
                f"across {len(queries)} queries"
            )
        
        return all_results
    
    def get_context_string(
        self,
        query: str,
        separator: str = "\n\n---\n\n",
        include_metadata: bool = True
    ) -> str:
        """
        Search and format results as a single context string.
        
        This is useful for feeding retrieved chunks to LLM prompts.
        
        Args:
            query: Natural language search query
            separator: String to separate chunks (default: "\\n\\n---\\n\\n")
            include_metadata: Include document title and chunk info (default: True)
        
        Returns:
            Formatted context string ready for LLM prompt
        
        Examples:
            >>> retriever = PolicyRetriever()
            >>> context = retriever.get_context_string("What is the maximum DTI?")
            >>> prompt = f"Based on these policies:\\n\\n{context}\\n\\nAnswer: ..."
        """
        results = self.search(query, include_scores=False)
        
        if not results:
            return ""
        
        chunks = []
        for i, result in enumerate(results, start=1):
            if include_metadata:
                chunk = (
                    f"[Policy {i}: {result['doc_title']} - Chunk {result['chunk_index']}]\\n"
                    f"{result['content']}"
                )
            else:
                chunk = result['content']
            
            chunks.append(chunk)
        
        context = separator.join(chunks)
        
        logger.info(
            f"✅ Context string created: {len(results)} chunks, "
            f"{len(context)} chars"
        )
        
        return context
    
    def get_retrieval_stats(self, query: str) -> Dict[str, Any]:
        """
        Get detailed statistics about retrieval for a query.
        
        Args:
            query: Natural language search query
        
        Returns:
            Dictionary with retrieval statistics:
            - query: Original query
            - query_length: Query character count
            - results_count: Number of results returned
            - avg_score: Average similarity score
            - max_score: Highest similarity score
            - min_score: Lowest similarity score
            - categories: List of document categories retrieved
            - total_content_length: Total characters in results
        
        Examples:
            >>> retriever = PolicyRetriever()
            >>> stats = retriever.get_retrieval_stats("maximum DTI ratio")
            >>> print(f"Found {stats['results_count']} results")
            >>> print(f"Average score: {stats['avg_score']:.3f}")
        """
        results = self.search(query, include_scores=True)
        
        if not results:
            return {
                "query": query,
                "query_length": len(query),
                "results_count": 0,
                "avg_score": 0.0,
                "max_score": 0.0,
                "min_score": 0.0,
                "categories": [],
                "total_content_length": 0
            }
        
        scores = [r['score'] for r in results]
        categories = list(set(r['doc_category'] for r in results))
        total_length = sum(len(r['content']) for r in results)
        
        stats = {
            "query": query,
            "query_length": len(query),
            "results_count": len(results),
            "avg_score": sum(scores) / len(scores),
            "max_score": max(scores),
            "min_score": min(scores),
            "categories": categories,
            "total_content_length": total_length
        }
        
        logger.info(
            f"📊 Retrieval stats: {stats['results_count']} results, "
            f"avg_score={stats['avg_score']:.3f}, "
            f"categories={categories}"
        )
        
        return stats
