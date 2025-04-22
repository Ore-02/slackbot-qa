import os
import pdfplumber
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
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
        
        chunks = []
        
        # Process page by page to avoid loading the entire document into memory
        with pdfplumber.open(file_path) as pdf:
            # Limit to max 50 pages for memory reasons
            max_pages = min(len(pdf.pages), 50)
            
            # Process page by page instead of loading all text at once
            current_chunk = ""
            
            for page_num in range(max_pages):
                try:
                    # Get one page at a time
                    page = pdf.pages[page_num]
                    
                    # Extract text from page
                    text = page.extract_text() or ""
                    
                    if not text.strip():
                        continue
                        
                    # Add page separator
                    page_text = f"\n\n--- Page {page_num + 1} ---\n\n{text}"
                    
                    # Process this page's text into chunks
                    current_chunk += page_text
                    
                    # If current chunk exceeds chunk size, split it
                    while len(current_chunk) >= chunk_size:
                        # Find a good breaking point
                        end_pos = chunk_size
                        if len(current_chunk) > end_pos:
                            # Try to find a sentence end or paragraph break
                            for delimiter in ["\n\n", ".\n", ". ", ".\n\n"]:
                                pos = current_chunk.rfind(delimiter, 0, end_pos + 100)
                                if pos > end_pos - 200 and pos != -1:
                                    end_pos = pos + len(delimiter)
                                    break
                        
                        # Extract the chunk
                        chunk = current_chunk[:end_pos].strip()
                        if chunk:
                            chunks.append(chunk)
                        
                        # Keep the remainder with overlap
                        overlap_start = max(0, end_pos - chunk_overlap)
                        current_chunk = current_chunk[overlap_start:]
                
                except Exception as e:
                    logger.warning(f"Error processing page {page_num} of {file_path}: {str(e)}")
                    continue
            
            # Don't forget the last chunk if it has content
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
        
        if not chunks:
            logger.warning(f"No text extracted from PDF: {file_path}")
            return []
        
        logger.info(f"Extracted {len(chunks)} chunks from PDF: {file_path} (max {max_pages} pages)")
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
