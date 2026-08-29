"""
Azure AI Search index management for lending policy documents.

This module handles:
- Creating search indexes with vector fields for embeddings
- Chunking documents for optimal retrieval
- Managing index lifecycle (create, delete, reset)

Based on research.md decision:
- Index name: lending-policies-index
- Vector dimensions: 1536 (Ada-002 embeddings)
- Search type: Hybrid (vector + keyword)
"""

import logging
from typing import List, Optional
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)

from utils.config import Config

logger = logging.getLogger(__name__)


class PolicyIndexer:
    """
    Manages Azure AI Search index for lending policy documents.
    
    Creates and configures search index with:
    - Full-text search on document content
    - Vector search on embeddings (1536 dimensions for Ada-002)
    - Metadata fields for filtering and ranking
    
    Examples:
        >>> indexer = PolicyIndexer()
        >>> indexer.create_index()
        >>> print(f"Index created: {indexer.index_name}")
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None
    ):
        """
        Initialize PolicyIndexer with Azure AI Search credentials.
        
        Args:
            endpoint: Azure AI Search endpoint URL (defaults to Config.AZURE_SEARCH_ENDPOINT)
            api_key: Azure AI Search admin key (defaults to Config.AZURE_SEARCH_ADMIN_KEY)
            index_name: Name of the search index (defaults to Config.AZURE_SEARCH_INDEX_NAME)
        
        Raises:
            ValueError: If credentials are missing
        """
        self.endpoint = endpoint or Config.AZURE_SEARCH_ENDPOINT
        self.api_key = api_key or Config.AZURE_SEARCH_ADMIN_KEY
        self.index_name = index_name or Config.AZURE_SEARCH_INDEX_NAME
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure AI Search credentials not configured. "
                "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY in .env"
            )
        
        # Initialize Search Index Client
        credential = AzureKeyCredential(self.api_key)
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=credential
        )
        
        # Initialize Search Client (for document operations)
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=credential
        )
        
        logger.info(
            f"PolicyIndexer initialized with endpoint: {self.endpoint}, "
            f"index: {self.index_name}"
        )
    
    def create_index(self, delete_if_exists: bool = False) -> SearchIndex:
        """
        Create Azure AI Search index with vector search capabilities.
        
        Index schema (from research.md):
        - chunk_id: Unique identifier (key)
        - content: Full-text searchable content
        - embedding: 1536-dimensional vector for semantic search
        - doc_title: Filterable document title
        - doc_category: Filterable category (e.g., "underwriting", "compliance")
        - chunk_index: Position of chunk in original document
        
        Args:
            delete_if_exists: If True, delete existing index before creating new one
        
        Returns:
            SearchIndex: The created index object
        
        Examples:
            >>> indexer = PolicyIndexer()
            >>> index = indexer.create_index(delete_if_exists=True)
            >>> print(f"Index '{index.name}' created with {len(index.fields)} fields")
        """
        # Check if index exists
        try:
            existing_index = self.index_client.get_index(self.index_name)
            if delete_if_exists:
                logger.info(f"Deleting existing index: {self.index_name}")
                self.index_client.delete_index(self.index_name)
            else:
                logger.info(f"Index '{self.index_name}' already exists. Use delete_if_exists=True to recreate.")
                return existing_index
        except Exception:
            # Index doesn't exist - we'll create it
            logger.info(f"Index '{self.index_name}' does not exist. Creating new index.")
        
        # Define vector search configuration
        # Using HNSW (Hierarchical Navigable Small World) algorithm for efficient ANN search
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-config",
                    parameters={
                        "m": 4,  # Number of bi-directional links (default: 4)
                        "efConstruction": 400,  # Size of dynamic candidate list (default: 400)
                        "efSearch": 500,  # Size of search candidate list (default: 500)
                        "metric": "cosine"  # Distance metric for similarity
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config"
                )
            ]
        )
        
        # Define index fields
        fields = [
            # Primary key
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
                sortable=False
            ),
            
            # Full-text searchable content
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=False,
                sortable=False
            ),
            
            # Vector field for semantic search (1536 dims for Ada-002)
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="vector-profile"
            ),
            
            # Metadata fields
            SearchableField(
                name="doc_title",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=True
            ),
            
            SimpleField(
                name="doc_category",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=False,
                facetable=True
            ),
            
            SimpleField(
                name="chunk_index",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
                facetable=False
            ),
            
            # Optional: Store original file path
            SimpleField(
                name="source_path",
                type=SearchFieldDataType.String,
                filterable=False,
                sortable=False,
                facetable=False
            )
        ]
        
        # Create index
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search
        )
        
        # Create index in Azure
        result = self.index_client.create_index(index)
        logger.info(f"✅ Index '{self.index_name}' created successfully with vector search enabled")
        logger.info(f"   Fields: {len(fields)}")
        logger.info(f"   Vector dimensions: 1536 (Ada-002)")
        logger.info(f"   Search type: Hybrid (vector + keyword)")
        
        return result
    
    def delete_index(self) -> None:
        """
        Delete the search index.
        
        Examples:
            >>> indexer = PolicyIndexer()
            >>> indexer.delete_index()
        """
        try:
            self.index_client.delete_index(self.index_name)
            logger.info(f"✅ Index '{self.index_name}' deleted successfully")
        except Exception as e:
            logger.error(f"❌ Error deleting index '{self.index_name}': {e}")
            raise
    
    def index_exists(self) -> bool:
        """
        Check if the index exists.
        
        Returns:
            True if index exists, False otherwise
        
        Examples:
            >>> indexer = PolicyIndexer()
            >>> if not indexer.index_exists():
            ...     indexer.create_index()
        """
        try:
            self.index_client.get_index(self.index_name)
            return True
        except Exception:
            return False
    
    def get_index_stats(self) -> dict:
        """
        Get statistics about the index.
        
        Returns:
            Dictionary with document count and storage size
        
        Examples:
            >>> indexer = PolicyIndexer()
            >>> stats = indexer.get_index_stats()
            >>> print(f"Documents: {stats['document_count']}")
        """
        try:
            index = self.index_client.get_index(self.index_name)
            stats = {
                "index_name": self.index_name,
                "field_count": len(index.fields),
                "vector_search_enabled": index.vector_search is not None
            }
            logger.info(f"Index stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting index stats: {e}")
            raise
    
    def index_documents(
        self,
        file_paths: List[Path],
        chunker: Optional['DocumentChunker'] = None,
        embedder: Optional[object] = None,
        batch_size: int = 10,
        category_map: Optional[dict] = None
    ) -> dict:
        """
        Process and index policy documents with embeddings.
        
        Pipeline: chunk → embed → upload to Azure AI Search
        
        This method implements the complete indexing workflow:
        1. Chunk each document using DocumentChunker
        2. Generate embeddings using EmbeddingGenerator
        3. Upload chunks with embeddings to Azure AI Search
        
        Args:
            file_paths: List of PDF or text file paths to index
            chunker: DocumentChunker instance (creates default if None)
            embedder: EmbeddingGenerator instance (must provide)
            batch_size: Number of documents to upload per batch (default: 10)
            category_map: Optional dict mapping filename stems to categories
                         (e.g., {"underwriting_standards": "underwriting"})
        
        Returns:
            Dictionary with indexing statistics:
            - total_files: Number of files processed
            - total_chunks: Total chunks created
            - total_tokens: Total tokens embedded
            - total_cost: Total embedding cost in USD
            - failed_files: List of files that failed to process
        
        Raises:
            ValueError: If embedder is not provided or index doesn't exist
            Exception: If uploading to Azure AI Search fails
        
        Examples:
            >>> from pathlib import Path
            >>> from src.rag.embeddings import EmbeddingGenerator
            >>> 
            >>> indexer = PolicyIndexer()
            >>> embedder = EmbeddingGenerator()
            >>> 
            >>> # Index all policy PDFs
            >>> policy_dir = Path("data/policies")
            >>> files = list(policy_dir.glob("*.pdf"))
            >>> 
            >>> stats = indexer.index_documents(
            ...     file_paths=files,
            ...     embedder=embedder,
            ...     category_map={
            ...         "underwriting_standards": "underwriting",
            ...         "credit_requirements": "credit",
            ...         "income_verification": "income"
            ...     }
            ... )
            >>> 
            >>> print(f"Indexed {stats['total_chunks']} chunks from {stats['total_files']} files")
            >>> print(f"Total cost: ${stats['total_cost']:.6f}")
        """
        # Validate inputs
        if embedder is None:
            raise ValueError(
                "EmbeddingGenerator must be provided. "
                "Create one with: from src.rag.embeddings import EmbeddingGenerator"
            )
        
        if not self.index_exists():
            raise ValueError(
                f"Index '{self.index_name}' does not exist. "
                f"Call create_index() first."
            )
        
        # Create default chunker if not provided
        if chunker is None:
            chunker = DocumentChunker(chunk_size=500, overlap=50)
            logger.info("Using default DocumentChunker (500 tokens, 50 overlap)")
        
        # Initialize stats tracking
        stats = {
            "total_files": 0,
            "total_chunks": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "failed_files": []
        }
        
        # Category mapping (default to "general" if not specified)
        if category_map is None:
            category_map = {}
        
        logger.info(f"🚀 Starting indexing pipeline for {len(file_paths)} files")
        logger.info(f"   Pipeline: chunk → embed → upload")
        logger.info(f"   Batch size: {batch_size} documents")
        
        # Process each file
        all_documents = []
        
        for file_idx, file_path in enumerate(file_paths, start=1):
            try:
                logger.info(f"\n📄 [{file_idx}/{len(file_paths)}] Processing: {file_path.name}")
                
                # Step 1: Chunk document
                logger.info(f"   Step 1/3: Chunking document...")
                chunks = chunker.chunk_file(file_path)
                
                if not chunks:
                    logger.warning(f"   ⚠️ No chunks created from {file_path.name} - skipping")
                    stats["failed_files"].append(str(file_path))
                    continue
                
                logger.info(f"   ✅ Created {len(chunks)} chunks")
                
                # Step 2: Generate embeddings
                logger.info(f"   Step 2/3: Generating embeddings...")
                chunk_texts = [chunk["text"] for chunk in chunks]
                embeddings = embedder.embed_batch(chunk_texts)
                
                logger.info(f"   ✅ Generated {len(embeddings)} embeddings")
                
                # Step 3: Prepare documents for upload
                logger.info(f"   Step 3/3: Preparing documents for upload...")
                
                # Get category for this file
                file_stem = file_path.stem
                category = category_map.get(file_stem, "general")
                
                for chunk, embedding in zip(chunks, embeddings):
                    # Create unique chunk ID
                    chunk_id = f"{file_stem}_chunk_{chunk['index']}"
                    
                    # Create document matching Azure AI Search schema
                    document = {
                        "chunk_id": chunk_id,
                        "content": chunk["text"],
                        "embedding": embedding,
                        "doc_title": file_path.stem.replace("_", " ").title(),
                        "doc_category": category,
                        "chunk_index": chunk["index"],
                        "source_path": str(file_path)
                    }
                    
                    all_documents.append(document)
                
                # Update stats
                stats["total_files"] += 1
                stats["total_chunks"] += len(chunks)
                
                logger.info(f"   ✅ Prepared {len(chunks)} documents for indexing")
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {file_path.name}: {e}")
                stats["failed_files"].append(str(file_path))
                continue
        
        # Upload all documents in batches
        if all_documents:
            logger.info(f"\n📤 Uploading {len(all_documents)} documents to Azure AI Search...")
            logger.info(f"   Index: {self.index_name}")
            logger.info(f"   Batch size: {batch_size}")
            
            try:
                # Upload in batches
                for i in range(0, len(all_documents), batch_size):
                    batch = all_documents[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(all_documents) + batch_size - 1) // batch_size
                    
                    logger.info(f"   Uploading batch {batch_num}/{total_batches} ({len(batch)} documents)...")
                    
                    result = self.search_client.upload_documents(documents=batch)
                    
                    # Check for failures
                    succeeded = sum(1 for r in result if r.succeeded)
                    failed = len(result) - succeeded
                    
                    if failed > 0:
                        logger.warning(f"   ⚠️ Batch {batch_num}: {succeeded} succeeded, {failed} failed")
                    else:
                        logger.info(f"   ✅ Batch {batch_num}: All {succeeded} documents uploaded successfully")
                
                logger.info(f"✅ Upload complete: {len(all_documents)} documents indexed")
                
            except Exception as e:
                logger.error(f"❌ Error uploading documents to Azure AI Search: {e}")
                raise
        
        # Get cost summary from embedder
        cost_summary = embedder.get_cost_summary()
        stats["total_tokens"] = cost_summary["total_tokens"]
        stats["total_cost"] = cost_summary["total_cost"]
        
        # Print final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Indexing Pipeline Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Files processed: {stats['total_files']}/{len(file_paths)}")
        logger.info(f"Total chunks: {stats['total_chunks']}")
        logger.info(f"Total tokens: {stats['total_tokens']:,}")
        logger.info(f"Total cost: ${stats['total_cost']:.6f}")
        
        if stats["failed_files"]:
            logger.warning(f"Failed files ({len(stats['failed_files'])}): {stats['failed_files']}")
        
        logger.info(f"{'='*60}\n")
        
        return stats


class DocumentChunker:
    """
    Chunks policy documents into smaller segments for optimal retrieval.
    
    Based on research.md decision:
    - Chunk size: 500 tokens (approximately 375 words or 2000 characters)
    - Overlap: 50 tokens (10% overlap to maintain context across chunks)
    
    Examples:
        >>> chunker = DocumentChunker(chunk_size=500, overlap=50)
        >>> chunks = chunker.chunk_text(long_document_text)
        >>> print(f"Created {len(chunks)} chunks from document")
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        separator: str = "\n\n"
    ):
        """
        Initialize DocumentChunker with chunking parameters.
        
        Args:
            chunk_size: Target size of each chunk in tokens (default: 500)
            overlap: Number of overlapping tokens between chunks (default: 50)
            separator: Text separator for splitting (default: paragraph breaks)
        
        Examples:
            >>> chunker = DocumentChunker(chunk_size=500, overlap=50)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separator = separator
        
        logger.info(
            f"DocumentChunker initialized: chunk_size={chunk_size} tokens, "
            f"overlap={overlap} tokens"
        )
    
    def chunk_text(self, text: str, doc_id: str = "unknown") -> List[dict]:
        """
        Chunk text into overlapping segments.
        
        Simple character-based chunking (approximation):
        - 1 token ≈ 4 characters on average
        - 500 tokens ≈ 2000 characters
        - 50 token overlap ≈ 200 characters
        
        Args:
            text: Full document text to chunk
            doc_id: Document identifier for logging
        
        Returns:
            List of chunk dictionaries with 'text' and 'index' keys
        
        Examples:
            >>> chunker = DocumentChunker()
            >>> text = "Long policy document..." * 100
            >>> chunks = chunker.chunk_text(text, doc_id="policy-001")
            >>> print(f"Chunk 0: {chunks[0]['text'][:100]}...")
        """
        # Approximate token-to-character conversion (1 token ≈ 4 chars)
        chunk_size_chars = self.chunk_size * 4
        overlap_chars = self.overlap * 4
        
        chunks = []
        start_idx = 0
        chunk_index = 0
        
        while start_idx < len(text):
            # Calculate end index for this chunk
            end_idx = start_idx + chunk_size_chars
            
            # Extract chunk
            chunk_text = text[start_idx:end_idx]
            
            # Only add non-empty chunks
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "index": chunk_index,
                    "start_char": start_idx,
                    "end_char": min(end_idx, len(text))
                })
                chunk_index += 1
            
            # Move start pointer (with overlap)
            start_idx = end_idx - overlap_chars
            
            # Prevent infinite loop if overlap >= chunk_size
            if overlap_chars >= chunk_size_chars:
                start_idx = end_idx
        
        logger.info(
            f"✅ Chunked document '{doc_id}': {len(text)} chars → {len(chunks)} chunks "
            f"(~{self.chunk_size} tokens each)"
        )
        
        return chunks
    
    def chunk_file(self, file_path: Path) -> List[dict]:
        """
        Read and chunk a text or PDF file.
        
        Supports:
        - .txt files: Direct text extraction
        - .pdf files: Text extraction using pdfplumber
        
        Args:
            file_path: Path to text or PDF file
        
        Returns:
            List of chunk dictionaries with metadata
        
        Examples:
            >>> chunker = DocumentChunker()
            >>> chunks = chunker.chunk_file(Path("data/policies/underwriting_standards.pdf"))
            >>> print(f"Extracted {len(chunks)} chunks from PDF")
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
            Exception: If PDF extraction fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file content based on type
        if file_path.suffix.lower() == ".txt":
            logger.info(f"📄 Reading text file: {file_path.name}")
            text = file_path.read_text(encoding="utf-8")
        
        elif file_path.suffix.lower() == ".pdf":
            logger.info(f"📄 Extracting text from PDF: {file_path.name}")
            text = self._extract_pdf_text(file_path)
        
        else:
            raise ValueError(
                f"Unsupported file type: {file_path.suffix}. "
                f"Supported types: .txt, .pdf"
            )
        
        return self.chunk_text(text, doc_id=file_path.stem)
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted text content
        
        Raises:
            Exception: If PDF extraction fails
        
        Examples:
            >>> chunker = DocumentChunker()
            >>> text = chunker._extract_pdf_text(Path("policy.pdf"))
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber is required for PDF extraction. "
                "Install with: pip install pdfplumber"
            )
        
        try:
            full_text = []
            
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"📖 Processing {total_pages} pages from {pdf_path.name}")
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text from page
                    page_text = page.extract_text()
                    
                    if page_text:
                        full_text.append(page_text)
                        logger.debug(
                            f"  Page {page_num}/{total_pages}: "
                            f"Extracted {len(page_text)} characters"
                        )
                    else:
                        logger.warning(
                            f"  ⚠️ Page {page_num}/{total_pages}: No text extracted "
                            f"(may be image-based or empty)"
                        )
            
            # Join all page texts with double newline separator
            combined_text = "\n\n".join(full_text)
            
            logger.info(
                f"✅ PDF extraction complete: {len(combined_text)} chars "
                f"from {total_pages} pages"
            )
            
            if not combined_text.strip():
                logger.error(
                    f"❌ No text extracted from PDF: {pdf_path.name}. "
                    f"File may be image-based or corrupted."
                )
                raise ValueError(
                    f"No text content extracted from PDF: {pdf_path.name}. "
                    f"This may be an image-based PDF requiring OCR."
                )
            
            return combined_text
        
        except Exception as e:
            logger.error(f"❌ Failed to extract PDF text: {e}")
            raise
