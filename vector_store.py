import os
import logging
import json
from typing import List, Dict, Any
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants
VECTOR_DB_PATH = "vector_db"
COLLECTION_NAME = "pdf_content"

# Simple in-memory storage for our PDF chunks
pdf_documents = []

class SimpleVectorStore:
    """A simple replacement for ChromaDB that works without embeddings"""
    
    def __init__(self):
        self.documents = []
        
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None):
        """Add texts to the store with their metadata"""
        if not texts:
            return
            
        if metadatas is None:
            metadatas = [{} for _ in texts]
            
        for text, metadata in zip(texts, metadatas):
            self.documents.append({
                "text": text,
                "metadata": metadata
            })
        
        # Save documents to file
        self._save_to_file()
            
    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Find relevant documents using keyword matching"""
        # Load documents from file
        self._load_from_file()
        
        # Extract keywords from the query
        keywords = self._extract_keywords(query)
        
        # Score documents based on keyword matches
        scored_docs = []
        for doc in self.documents:
            score = 0
            text = doc["text"].lower()
            
            for keyword in keywords:
                if keyword in text:
                    score += 1
                    
            if score > 0:
                scored_docs.append((score, doc))
        
        # Sort by score (highest first)
        scored_docs.sort(reverse=True)
        
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
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query"""
        # Remove common words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'on', 'it', 'this', 'that', 'to', 'of', 'for', 'in'}
        
        # Convert to lowercase and split
        words = query.lower().split()
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def _save_to_file(self):
        """Save documents to file"""
        try:
            if not os.path.exists(VECTOR_DB_PATH):
                os.makedirs(VECTOR_DB_PATH)
                
            file_path = os.path.join(VECTOR_DB_PATH, f"{COLLECTION_NAME}.json")
            
            with open(file_path, 'w') as f:
                json.dump(self.documents, f)
                
            logger.info(f"Saved {len(self.documents)} documents to {file_path}")
        except Exception as e:
            logger.error(f"Error saving documents: {str(e)}")
    
    def _load_from_file(self):
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

def get_vector_store() -> SimpleVectorStore:
    """
    Get or create a simple vector store
    
    Returns:
        SimpleVectorStore instance
    """
    try:
        # Create directory for vector store if it doesn't exist
        if not os.path.exists(VECTOR_DB_PATH):
            os.makedirs(VECTOR_DB_PATH)
        
        # Create a simple vector store
        vector_store = SimpleVectorStore()
        
        return vector_store
    
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise

def add_texts_to_vector_store(vector_store: SimpleVectorStore, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> None:
    """
    Add texts to the vector store
    
    Args:
        vector_store: SimpleVectorStore instance
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

def search_vector_store(vector_store: SimpleVectorStore, query: str, k: int = 5) -> List[Document]:
    """
    Search for relevant documents in the vector store
    
    Args:
        vector_store: SimpleVectorStore instance
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
