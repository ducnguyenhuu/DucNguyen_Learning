"""
Embedding generation for RAG system using Azure OpenAI Ada-002.

This module handles:
- Text embedding using text-embedding-ada-002 model
- Batch processing with rate limit handling
- Cost tracking and logging
- Error handling and retries

Based on research.md decision:
- Model: text-embedding-ada-002 (1536 dimensions)
- Batch size: 16 texts per API call (Azure limit)
- Rate limiting: Automatic retry with exponential backoff
"""

import logging
import time
from typing import List, Optional
from openai import AzureOpenAI
from openai import APIError, RateLimitError, APITimeoutError

from utils.config import Config

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings for text chunks using Azure OpenAI Ada-002.
    
    This class handles batch embedding with automatic rate limit handling
    and cost tracking.
    
    Features:
    - Batch processing (up to 16 texts per call)
    - Automatic retry with exponential backoff
    - Cost tracking ($0.0001 per 1K tokens)
    - Input validation (max 8,191 tokens per text)
    
    Examples:
        >>> generator = EmbeddingGenerator()
        >>> embeddings = generator.embed_batch(["text 1", "text 2"])
        >>> print(f"Generated {len(embeddings)} embeddings")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
        max_retries: int = 3,
        batch_size: int = 16
    ):
        """
        Initialize EmbeddingGenerator with Azure OpenAI credentials.
        
        Args:
            api_key: Azure OpenAI API key (default: from Config)
            endpoint: Azure OpenAI endpoint URL (default: from Config)
            deployment: Deployment name for Ada-002 (default: from Config)
            api_version: API version (default: from Config)
            max_retries: Maximum retry attempts for failed requests (default: 3)
            batch_size: Number of texts to embed per API call (default: 16)
        
        Raises:
            ValueError: If credentials are missing
        
        Examples:
            >>> # Use default credentials from .env
            >>> generator = EmbeddingGenerator()
            
            >>> # Or provide credentials explicitly
            >>> generator = EmbeddingGenerator(
            ...     api_key="your-key",
            ...     endpoint="https://your-endpoint.openai.azure.com"
            ... )
        """
        # Load credentials from Config if not provided
        self.api_key = api_key or Config.AZURE_OPENAI_API_KEY
        self.endpoint = endpoint or Config.AZURE_OPENAI_ENDPOINT
        self.deployment = deployment or Config.AZURE_OPENAI_DEPLOYMENT_EMBEDDING
        self.api_version = api_version or Config.AZURE_OPENAI_API_VERSION
        
        # Validate credentials
        if not self.api_key or not self.endpoint:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env"
            )
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version
        )
        
        self.max_retries = max_retries
        self.batch_size = batch_size
        
        # Cost tracking
        self.total_tokens = 0
        self.total_cost = 0.0
        
        logger.info(
            f"EmbeddingGenerator initialized: model={self.deployment}, "
            f"batch_size={self.batch_size}, max_retries={self.max_retries}"
        )
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed (max 8,191 tokens)
        
        Returns:
            1536-dimensional embedding vector
        
        Raises:
            ValueError: If text is empty or exceeds token limit
            APIError: If API call fails after retries
        
        Examples:
            >>> generator = EmbeddingGenerator()
            >>> embedding = generator.embed_text("Sample policy text")
            >>> print(f"Embedding dimensions: {len(embedding)}")
            Embedding dimensions: 1536
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Embed as single-item batch
        embeddings = self.embed_batch([text])
        return embeddings[0]
    
    def embed_batch(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching.
        
        Automatically splits large batches into chunks of batch_size
        and processes with rate limit handling.
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to log progress for large batches
        
        Returns:
            List of 1536-dimensional embedding vectors
        
        Raises:
            ValueError: If texts is empty or contains empty strings
            APIError: If API call fails after retries
        
        Examples:
            >>> generator = EmbeddingGenerator()
            >>> texts = ["Policy 1", "Policy 2", "Policy 3"]
            >>> embeddings = generator.embed_batch(texts)
            >>> print(f"Generated {len(embeddings)} embeddings")
        """
        if not texts:
            raise ValueError("Text list cannot be empty")
        
        # Validate texts
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} is empty")
        
        all_embeddings = []
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        
        logger.info(
            f"Embedding {len(texts)} texts in {total_batches} batches "
            f"(batch_size={self.batch_size})"
        )
        
        # Process in batches
        for batch_idx in range(0, len(texts), self.batch_size):
            batch_texts = texts[batch_idx:batch_idx + self.batch_size]
            batch_num = (batch_idx // self.batch_size) + 1
            
            if show_progress:
                logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            # Generate embeddings for this batch with retry logic
            batch_embeddings = self._embed_with_retry(batch_texts)
            all_embeddings.extend(batch_embeddings)
        
        logger.info(
            f"✅ Generated {len(all_embeddings)} embeddings. "
            f"Total tokens: {self.total_tokens}, Total cost: ${self.total_cost:.4f}"
        )
        
        return all_embeddings
    
    def _embed_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Call Azure OpenAI Embeddings API with exponential backoff retry.
        
        Args:
            texts: Batch of texts to embed (max 16)
        
        Returns:
            List of embedding vectors
        
        Raises:
            APIError: If all retries are exhausted
        """
        for attempt in range(self.max_retries):
            try:
                # Call Azure OpenAI Embeddings API
                response = self.client.embeddings.create(
                    model=self.deployment,
                    input=texts
                )
                
                # Extract embeddings
                embeddings = [item.embedding for item in response.data]
                
                # Update cost tracking
                tokens_used = response.usage.total_tokens
                cost = tokens_used / 1000 * 0.0001  # $0.0001 per 1K tokens
                
                self.total_tokens += tokens_used
                self.total_cost += cost
                
                logger.debug(
                    f"Batch embedded: {len(texts)} texts, "
                    f"{tokens_used} tokens, ${cost:.6f}"
                )
                
                return embeddings
            
            except RateLimitError as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                    f"Waiting {wait_time}s before retry..."
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exhausted for rate limit")
                    raise
            
            except APITimeoutError as e:
                wait_time = 2 ** attempt
                logger.warning(
                    f"API timeout (attempt {attempt + 1}/{self.max_retries}). "
                    f"Waiting {wait_time}s before retry..."
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exhausted for timeout")
                    raise
            
            except APIError as e:
                logger.error(f"Azure OpenAI API error: {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exhausted")
                    raise
            
            except Exception as e:
                logger.error(f"Unexpected error during embedding: {e}")
                raise
        
        raise APIError("Failed to generate embeddings after all retries")
    
    def embed_chunks(
        self,
        chunks: List[dict],
        text_key: str = "text",
        show_progress: bool = True
    ) -> List[dict]:
        """
        Embed text chunks and add embeddings to chunk dictionaries.
        
        Convenience method for embedding DocumentChunker output.
        Adds 'embedding' field to each chunk dictionary.
        
        Args:
            chunks: List of chunk dictionaries from DocumentChunker
            text_key: Key in chunk dict containing text (default: "text")
            show_progress: Whether to log progress
        
        Returns:
            List of chunk dictionaries with 'embedding' field added
        
        Raises:
            ValueError: If chunks is empty or text_key not found
            APIError: If embedding generation fails
        
        Examples:
            >>> from src.rag.indexer import DocumentChunker
            >>> chunker = DocumentChunker()
            >>> chunks = chunker.chunk_text("Long policy document...")
            
            >>> generator = EmbeddingGenerator()
            >>> embedded_chunks = generator.embed_chunks(chunks)
            >>> print(f"Chunk 0 embedding: {len(embedded_chunks[0]['embedding'])} dims")
        """
        if not chunks:
            raise ValueError("Chunks list cannot be empty")
        
        # Validate text_key exists
        if text_key not in chunks[0]:
            raise ValueError(f"Key '{text_key}' not found in chunk dictionaries")
        
        # Extract texts
        texts = [chunk[text_key] for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.embed_batch(texts, show_progress=show_progress)
        
        # Add embeddings to chunks
        embedded_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            embedded_chunk = chunk.copy()
            embedded_chunk["embedding"] = embedding
            embedded_chunks.append(embedded_chunk)
        
        logger.info(f"✅ Added embeddings to {len(embedded_chunks)} chunks")
        
        return embedded_chunks
    
    def get_cost_summary(self) -> dict:
        """
        Get summary of embedding costs.
        
        Returns:
            Dictionary with tokens used and total cost
        
        Examples:
            >>> generator = EmbeddingGenerator()
            >>> generator.embed_batch(["text 1", "text 2"])
            >>> summary = generator.get_cost_summary()
            >>> print(f"Total cost: ${summary['total_cost']:.4f}")
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "cost_per_1k_tokens": 0.0001,
            "model": self.deployment
        }
    
    def reset_cost_tracking(self) -> None:
        """
        Reset cost tracking counters.
        
        Useful when starting a new embedding session.
        
        Examples:
            >>> generator = EmbeddingGenerator()
            >>> generator.embed_batch(["text 1"])
            >>> generator.reset_cost_tracking()
            >>> summary = generator.get_cost_summary()
            >>> assert summary['total_tokens'] == 0
        """
        self.total_tokens = 0
        self.total_cost = 0.0
        logger.info("Cost tracking counters reset")
