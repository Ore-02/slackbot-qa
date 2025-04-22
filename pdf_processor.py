import os
import pdfplumber
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Extract text from a PDF file and split it into chunks
    
    Args:
        file_path: Path to the PDF file
        chunk_size: Maximum size of each text chunk
        chunk_overlap: Overlap between consecutive chunks
        
    Returns:
        List of text chunks extracted from the PDF
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return []
        
        all_text = ""
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n\n"
        
        if not all_text.strip():
            logger.warning(f"No text extracted from PDF: {file_path}")
            return []
        
        # Split the text into chunks
        chunks = []
        current_pos = 0
        
        while current_pos < len(all_text):
            # Take a chunk of text
            end_pos = min(current_pos + chunk_size, len(all_text))
            
            # If we're not at the end and not at a whitespace, extend to next whitespace
            if end_pos < len(all_text) and not all_text[end_pos].isspace():
                # Look for the next whitespace
                next_space = all_text.find(" ", end_pos)
                if next_space != -1 and next_space - end_pos < 100:  # Don't extend too far
                    end_pos = next_space
            
            # Add the chunk
            chunk = all_text[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move position with overlap
            current_pos = end_pos - chunk_overlap
            if current_pos < 0:
                current_pos = end_pos  # Avoid infinite loops
        
        logger.info(f"Extracted {len(chunks)} chunks from PDF: {file_path}")
        return chunks
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        return []

def process_pdf_file(file_id: str, file_url: str, file_name: str) -> Optional[List[str]]:
    """
    Process a PDF file from Slack
    
    Args:
        file_id: Slack file ID
        file_url: URL to download the file
        file_name: Name of the file
        
    Returns:
        List of text chunks or None if processing failed
    """
    try:
        # Create temp directory if it doesn't exist
        if not os.path.exists("temp"):
            os.makedirs("temp")
        
        file_path = f"temp/{file_name}"
        
        # Here we would download the file
        # For simplicity, let's assume the file has already been downloaded
        
        # Extract text from PDF
        text_chunks = extract_text_from_pdf(file_path)
        
        # Clean up: Remove downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return text_chunks
    
    except Exception as e:
        logger.error(f"Error processing PDF file {file_name}: {str(e)}")
        return None
