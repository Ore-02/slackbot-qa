"""
Enhanced vector store for document storage and retrieval using keyword-based search
"""
import os
import json
import logging
import math
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_PATH = "vector_db"
COLLECTION_NAME = "document_store"
DOCUMENT_INDEX_NAME = "document_index"

class EnhancedVectorStore:
    """An enhanced vector store with keyword-based search"""
    
    def __init__(self):
        """Initialize the vector store"""
        self.documents = []  # List of document chunks
        self.document_index = {}  # Map of words to document indices
        self._load_from_file()
        self._build_index()
    
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> None:
        """
        Add texts to the store with their metadata
        
        Args:
            texts: List of text chunks to add
            metadatas: List of metadata dictionaries for each text chunk
        """
        if not texts:
            return
        
        if not metadatas:
            metadatas = [{} for _ in texts]
        
        for i, (text, metadata) in enumerate(zip(texts, metadatas)):
            # Create a document object
            doc = {
                "text": text,
                "metadata": metadata,
                "added_at": time.time()
            }
            
            # Add to documents
            self.documents.append(doc)
        
        # Rebuild the index
        self._build_index()
        
        # Save to file
        self._save_to_file()
    
    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """
        Find relevant documents using keyword matching
        
        Args:
            query: Query text
            k: Number of results to return
            
        Returns:
            List of Document objects
        """
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        if not keywords or not self.documents:
            return []
        
        # Score documents based on keyword matches
        scored_docs = []
        for i, doc in enumerate(self.documents):
            score = 0
            doc_text = doc["text"].lower()
            
            # Basic tf-idf style scoring
            for keyword in keywords:
                # Check if keyword is in document
                if keyword in doc_text:
                    # Count occurrences (term frequency)
                    count = doc_text.count(keyword)
                    
                    # Calculate a score based on frequency and keyword rarity
                    # The fewer documents a keyword appears in, the more valuable it is
                    tf = count / len(doc_text.split())
                    
                    # Get the number of documents containing the keyword
                    docs_with_keyword = len(self.document_index.get(keyword, []))
                    if docs_with_keyword > 0:
                        idf = math.log(len(self.documents) / docs_with_keyword)
                    else:
                        idf = 0
                    
                    # Add to score
                    score += tf * idf * 100  # Scale up for better discrimination
            
            # Boost score for exact phrase matches
            if score > 0 and len(keywords) > 1:
                # Create phrase patterns
                phrases = self._create_phrase_patterns(query)
                for phrase in phrases:
                    if phrase in doc_text:
                        # Strong boost for exact phrase matches
                        score *= 1.5
            
            # Add recency bias (newer documents rank higher)
            if score > 0 and "added_at" in doc:
                # Calculate age factor (1.0 for new docs, decreases over time)
                age_in_days = (time.time() - doc["added_at"]) / (60 * 60 * 24)
                recency_factor = max(0.7, 1.0 - (age_in_days / 365.0))  # Reduce by at most 30% over a year
                score *= recency_factor
                    
            if score > 0:
                scored_docs.append((score, doc))
        
        # Sort by score (highest first)
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Convert to LangChain Document format
        results = []
        for _, doc in scored_docs[:k]:
            results.append(
                Document(
                    page_content=doc["text"],
                    metadata=doc["metadata"]
                )
            )
            
        return results
    
    def _build_index(self) -> None:
        """Build the document index for faster searching"""
        self.document_index = {}
        
        for i, doc in enumerate(self.documents):
            text = doc["text"].lower()
            
            # Extract tokens
            tokens = set(self._tokenize(text))
            
            # Add document index to each token's posting list
            for token in tokens:
                if token not in self.document_index:
                    self.document_index[token] = []
                
                if i not in self.document_index[token]:
                    self.document_index[token].append(i)
        
        logger.debug(f"Built index with {len(self.document_index)} unique tokens")
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words"""
        # Remove special characters and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into words
        return text.split()
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query"""
        # Remove common words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'on', 'it', 
                     'this', 'that', 'to', 'of', 'for', 'in', 'with', 'by', 'as',
                     'have', 'has', 'had', 'i', 'you', 'he', 'she', 'we', 'they'}
        
        # Convert to lowercase and tokenize
        words = self._tokenize(query)
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def _create_phrase_patterns(self, query: str) -> List[str]:
        """Create phrase patterns from the query for exact matching"""
        # Clean the query
        query = re.sub(r'[^\w\s]', ' ', query.lower())
        
        # Split by stop words to create phrases
        stop_pattern = r'\s+(?:a|an|the|and|or|but|is|are|on|it|this|that|to|of|for|in|with|by|as)\s+'
        phrases = re.split(stop_pattern, query)
        
        # Filter out short phrases
        return [phrase.strip() for phrase in phrases if len(phrase.strip().split()) > 1]
    
    def _save_to_file(self) -> None:
        """Save documents to file"""
        try:
            if not os.path.exists(VECTOR_DB_PATH):
                os.makedirs(VECTOR_DB_PATH)
                
            file_path = os.path.join(VECTOR_DB_PATH, f"{COLLECTION_NAME}.json")
            index_path = os.path.join(VECTOR_DB_PATH, f"{DOCUMENT_INDEX_NAME}.json")
            
            # Save documents
            with open(file_path, 'w') as f:
                json.dump(self.documents, f)
            
            # Save index separately (optional, can be rebuilt)
            # with open(index_path, 'w') as f:
            #     json.dump(self.document_index, f)
                
            logger.info(f"Saved {len(self.documents)} documents to {file_path}")
        except Exception as e:
            logger.error(f"Error saving documents: {str(e)}")
    
    def _load_from_file(self) -> None:
        """Load documents from file"""
        try:
            file_path = os.path.join(VECTOR_DB_PATH, f"{COLLECTION_NAME}.json")
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.documents = json.load(f)
                    
                logger.info(f"Loaded {len(self.documents)} documents from {file_path}")
            else:
                logger.info(f"No existing document store found at {file_path}")
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")

def get_enhanced_vector_store() -> EnhancedVectorStore:
    """
    Get or create an enhanced vector store
    
    Returns:
        EnhancedVectorStore instance
    """
    try:
        # Create directory for vector store if it doesn't exist
        if not os.path.exists(VECTOR_DB_PATH):
            os.makedirs(VECTOR_DB_PATH)
        
        # Create a vector store
        vector_store = EnhancedVectorStore()
        
        return vector_store
    
    except Exception as e:
        logger.error(f"Error getting enhanced vector store: {str(e)}")
        raise

def add_texts_to_vector_store(vector_store: EnhancedVectorStore, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> None:
    """
    Add texts to the vector store
    
    Args:
        vector_store: EnhancedVectorStore instance
        texts: List of text chunks to add
        metadatas: List of metadata dictionaries for each text chunk
    """
    try:
        if not texts:
            logger.warning("No texts to add to vector store")
            return
        
        # Add texts to vector store
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        logger.info(f"Added {len(texts)} texts to vector store")
    
    except Exception as e:
        logger.error(f"Error adding texts to vector store: {str(e)}")
        raise

def search_vector_store(vector_store: EnhancedVectorStore, query: str, k: int = 5) -> List[Document]:
    """
    Search for relevant documents in the vector store
    
    Args:
        vector_store: EnhancedVectorStore instance
        query: Query text
        k: Number of results to return
        
    Returns:
        List of Document objects containing text and metadata
    """
    try:
        # Perform similarity search
        documents = vector_store.similarity_search(query, k=k)
        logger.info(f"Found {len(documents)} relevant documents for query: {query}")
        return documents
    
    except Exception as e:
        logger.error(f"Error searching vector store: {str(e)}")
        return []