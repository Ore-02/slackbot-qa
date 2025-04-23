import os
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from langchain_core.documents import Document
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Google Generative AI with API key
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

def generate_answer(query: str, relevant_docs: List[Document], conversation_history: str = "") -> str:
    """
    Generate an answer to a user query using Gemini 1.5 Flash
    
    Args:
        query: User's question
        relevant_docs: List of relevant documents retrieved from vector store
        conversation_history: Previous conversation history formatted as text
        
    Returns:
        Generated answer from Gemini
    """
    try:
        # Prepare the context from relevant documents
        context = ""
        sources = set()
        
        # Group documents by source
        docs_by_source = {}
        for doc in relevant_docs:
            source = doc.metadata.get("source", "Unknown source")
            if source not in docs_by_source:
                docs_by_source[source] = []
            docs_by_source[source].append(doc)
            sources.add(source)
        
        # Combine documents from the same source
        for source, docs in docs_by_source.items():
            context += f"Information from '{source}':\n"
            for doc in docs:
                context += f"{doc.page_content}\n\n"
            context += "---\n\n"
        
        # Create the prompt with conversation history if available
        history_prompt = ""
        if conversation_history:
            history_prompt = f"""
Previous conversation:
{conversation_history}

"""
        
        # Create the prompt
        prompt = f"""You are a helpful AI assistant. Answer the user's question based on the provided documents.
        
{history_prompt}Context Documents:
{context}

Current Question: {query}

Instructions:
1. Provide a clear, concise answer based on the information in the context documents.
2. Consider the conversation history for context when answering.
3. If the documents contain information from multiple sources that are relevant, integrate the information.
4. If the documents don't contain relevant information to answer the question, honestly state that you don't have enough information.
5. Don't mention that you're looking at "context documents" - just provide the answer naturally.
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
