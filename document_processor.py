"""
Module for processing various document formats
"""
import os
import logging
import tempfile
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported file extensions and their processors
SUPPORTED_EXTENSIONS = {
    '.pdf': 'process_pdf',
    '.docx': 'process_docx',
    '.txt': 'process_txt',
    '.md': 'process_txt',
    '.xlsx': 'process_xlsx'
}

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
        import pdfplumber
        
        # Limit number of pages to process to avoid memory issues
        max_pages = 50
        chunks = []
        
        with pdfplumber.open(file_path) as pdf:
            # Process only the first max_pages
            num_pages = min(len(pdf.pages), max_pages)
            
            all_text = ""
            
            # First pass: extract text from each page
            for i in range(num_pages):
                try:
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    if text.strip():
                        all_text += f"--- Page {i+1} ---\n\n{text}\n\n"
                except Exception as e:
                    logger.error(f"Error extracting text from page {i+1}: {str(e)}")
                    all_text += f"--- Page {i+1} ---\n\n[Error extracting text from this page]\n\n"
            
            # Second pass: split into chunks
            if all_text:
                # Simple chunking by character count
                current_chunk = ""
                for i in range(0, len(all_text), chunk_size - chunk_overlap):
                    current_chunk = all_text[i:i + chunk_size]
                    if current_chunk:
                        chunks.append(current_chunk)
        
        if chunks:
            logger.info(f"Extracted {len(chunks)} chunks from PDF: {file_path} (max {max_pages} pages)")
        else:
            logger.warning(f"No text extracted from PDF: {file_path}")
        
        return chunks
    except Exception as e:
        logger.error(f"Error in extract_text_from_pdf: {str(e)}")
        return []

def extract_text_from_docx(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """
    Extract text from a DOCX file and split it into chunks
    
    Args:
        file_path: Path to the DOCX file
        chunk_size: Maximum size of each text chunk
        chunk_overlap: Overlap between consecutive chunks
        
    Returns:
        List of text chunks extracted from the DOCX
    """
    try:
        import docx
        
        chunks = []
        all_text = ""
        
        doc = docx.Document(file_path)
        
        # Extract text from paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                all_text += text + "\n\n"
        
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    all_text += row_text + "\n"
            all_text += "\n"
        
        # Split into chunks
        if all_text:
            # Simple chunking by character count
            for i in range(0, len(all_text), chunk_size - chunk_overlap):
                current_chunk = all_text[i:i + chunk_size]
                if current_chunk:
                    chunks.append(current_chunk)
        
        if chunks:
            logger.info(f"Extracted {len(chunks)} chunks from DOCX: {file_path}")
        else:
            logger.warning(f"No text extracted from DOCX: {file_path}")
        
        return chunks
    except Exception as e:
        logger.error(f"Error in extract_text_from_docx: {str(e)}")
        return []

def extract_text_from_txt(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """
    Extract text from a text file (TXT or MD) and split it into chunks
    
    Args:
        file_path: Path to the text file
        chunk_size: Maximum size of each text chunk
        chunk_overlap: Overlap between consecutive chunks
        
    Returns:
        List of text chunks extracted from the text file
    """
    try:
        chunks = []
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            all_text = f.read()
        
        # Split into chunks
        if all_text:
            # Simple chunking by character count
            for i in range(0, len(all_text), chunk_size - chunk_overlap):
                current_chunk = all_text[i:i + chunk_size]
                if current_chunk:
                    chunks.append(current_chunk)
        
        if chunks:
            logger.info(f"Extracted {len(chunks)} chunks from text file: {file_path}")
        else:
            logger.warning(f"No text extracted from text file: {file_path}")
        
        return chunks
    except Exception as e:
        logger.error(f"Error in extract_text_from_txt: {str(e)}")
        return []

def extract_text_from_xlsx(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """
    Extract text from an Excel file and split it into chunks
    
    Args:
        file_path: Path to the Excel file
        chunk_size: Maximum size of each text chunk
        chunk_overlap: Overlap between consecutive chunks
        
    Returns:
        List of text chunks extracted from the Excel file
    """
    try:
        import pandas as pd
        
        chunks = []
        all_text = ""
        
        # Read all sheets
        xlsx = pd.ExcelFile(file_path)
        for sheet_name in xlsx.sheet_names:
            df = pd.read_excel(xlsx, sheet_name)
            
            # Add sheet name
            all_text += f"--- Sheet: {sheet_name} ---\n\n"
            
            # Add column headers
            all_text += " | ".join(str(col) for col in df.columns) + "\n"
            
            # Add separator
            all_text += "-" * 40 + "\n"
            
            # Add rows
            for _, row in df.iterrows():
                all_text += " | ".join(str(cell) for cell in row) + "\n"
            
            all_text += "\n\n"
        
        # Split into chunks
        if all_text:
            # Simple chunking by character count
            for i in range(0, len(all_text), chunk_size - chunk_overlap):
                current_chunk = all_text[i:i + chunk_size]
                if current_chunk:
                    chunks.append(current_chunk)
        
        if chunks:
            logger.info(f"Extracted {len(chunks)} chunks from Excel: {file_path}")
        else:
            logger.warning(f"No text extracted from Excel: {file_path}")
        
        return chunks
    except Exception as e:
        logger.error(f"Error in extract_text_from_xlsx: {str(e)}")
        return []

def process_document(file_path: str, file_id: str, file_name: str) -> Optional[List[str]]:
    """
    Process a document file based on its extension
    
    Args:
        file_path: Path to the file
        file_id: ID of the file
        file_name: Name of the file
        
    Returns:
        List of text chunks or None if processing failed
    """
    try:
        _, file_extension = os.path.splitext(file_name.lower())
        
        if file_extension not in SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported file type: {file_extension}")
            return None
        
        # Get the appropriate processing function
        processor_name = SUPPORTED_EXTENSIONS[file_extension]
        
        if processor_name == 'process_pdf':
            return extract_text_from_pdf(file_path)
        elif processor_name == 'process_docx':
            return extract_text_from_docx(file_path)
        elif processor_name == 'process_txt':
            return extract_text_from_txt(file_path)
        elif processor_name == 'process_xlsx':
            return extract_text_from_xlsx(file_path)
        else:
            logger.warning(f"No processor found for {file_extension}")
            return None
    
    except Exception as e:
        logger.error(f"Error processing document {file_name}: {str(e)}")
        return None

def download_and_process_file(url: str, file_id: str, file_name: str, headers: Dict[str, str]) -> Optional[List[str]]:
    """
    Download a file from a URL and process it
    
    Args:
        url: URL to download the file
        file_id: ID of the file
        file_name: Name of the file
        headers: HTTP headers for the request
        
    Returns:
        List of text chunks or None if processing failed
    """
    try:
        import requests
        
        # Create temp directory if it doesn't exist
        if not os.path.exists("temp"):
            os.makedirs("temp")
        
        file_path = f"temp/{file_name}"
        
        # Download the file
        r = requests.get(url, headers=headers)
        with open(file_path, "wb") as f:
            f.write(r.content)
        
        # Process the file
        chunks = process_document(file_path, file_id, file_name)
        
        # Clean up: Remove downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return chunks
    
    except Exception as e:
        logger.error(f"Error downloading and processing file {file_name}: {str(e)}")
        return None