import os
from dotenv import load_dotenv
from vector_store import get_vector_store, search_vector_store
from gemini_client import generate_answer

# Load environment variables
load_dotenv()

def test_question_answering():
    # Set up a test question
    test_question = "What is Oreoluwa's work experience?"
    
    # Get the vector store
    vector_store = get_vector_store()
    
    # Search for relevant documents
    relevant_docs = search_vector_store(vector_store, test_question)
    
    print(f"Found {len(relevant_docs)} relevant documents")
    
    # Print a snippet of each document
    for i, doc in enumerate(relevant_docs):
        print(f"\nDocument {i+1} (source: {doc.metadata.get('source', 'Unknown')})")
        # Just show the first 200 characters
        print(f"Content snippet: {doc.page_content[:200]}...")
    
    # If we found relevant documents, generate an answer
    if relevant_docs:
        print("\nGenerating answer with Gemini...\n")
        answer = generate_answer(test_question, relevant_docs)
        print(f"Question: {test_question}")
        print(f"Answer: {answer}")
    else:
        print("No relevant documents found to answer the question.")

if __name__ == "__main__":
    test_question_answering()