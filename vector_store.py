import os
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define constants
VECTOR_DB_PATH = "vector_db"
COLLECTION_NAME = "pdf_content"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_vector_store() -> Chroma:
    """
    Get or create a Chroma vector store
    
    Returns:
        Chroma vector store instance
    """
    try:
        # Create directory for vector store if it doesn't exist
        if not os.path.exists(VECTOR_DB_PATH):
            os.makedirs(VECTOR_DB_PATH)
        
        # Set up the embedding function
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        # Create or get the vector store collection
        chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        
        # Check if collection exists, create if it doesn't
        try:
            collection = chroma_client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_function
            )
        except:
            collection = chroma_client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_function
            )
        
        # Create a Langchain wrapper around the collection
        vectorstore = Chroma(
            client=chroma_client,
            collection_name=COLLECTION_NAME,
            embedding_function=embedding_function
        )
        
        return vectorstore
    
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise

def add_texts_to_vector_store(vector_store: Chroma, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> None:
    """
    Add texts to the vector store
    
    Args:
        vector_store: Chroma vector store instance
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

def search_vector_store(vector_store: Chroma, query: str, k: int = 5) -> List[Document]:
    """
    Search for relevant documents in the vector store
    
    Args:
        vector_store: Chroma vector store instance
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
