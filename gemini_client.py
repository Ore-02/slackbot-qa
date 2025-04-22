import os
import logging
from typing import List
import google.generativeai as genai
from langchain_core.documents import Document
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Google Generative AI with API key
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

def generate_answer(query: str, relevant_docs: List[Document]) -> str:
    """
    Generate an answer to a user query using Gemini 1.5 Flash
    
    Args:
        query: User's question
        relevant_docs: List of relevant documents retrieved from vector store
        
    Returns:
        Generated answer from Gemini
    """
    try:
        # Prepare the context from relevant documents
        context = ""
        for i, doc in enumerate(relevant_docs):
            source = doc.metadata.get("source", "Unknown source")
            context += f"Document {i+1} (from {source}):\n{doc.page_content}\n\n"
        
        # Create the prompt
        prompt = f"""You are a helpful AI assistant. Answer the user's question based on the provided documents.
        
Context Documents:
{context}

Question: {query}

Provide a clear, concise answer based only on the information in the context documents. If the documents don't contain relevant information to answer the question, honestly state that you don't have enough information.
"""
        
        # Get Gemini model (1.5 Flash)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Return the answer text
        return response.text
    
    except Exception as e:
        logger.error(f"Error generating answer with Gemini: {str(e)}")
        return f"I'm sorry, but I encountered an error when trying to generate an answer: {str(e)}"
