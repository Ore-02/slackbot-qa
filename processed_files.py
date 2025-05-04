
"""
Module for tracking processed PDF files
"""
import os
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROCESSED_FILES_PATH = "vector_db/processed_files.json"

class ProcessedFileTracker:
    """Class to track which files have been processed to avoid duplication"""
    
    def __init__(self):
        """Initialize the tracker"""
        self._processed_files = set()
        self.processed_files = {}
        self._last_updated = None
        self._content_hashes = set()
        self._file_paths = set()
        self._load_from_file()

    def calculate_hash(self, file_path):
        """Calculate SHA-256 hash of file content"""
        import hashlib
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {str(e)}")
            return None
    
    def is_processed(self, file_id, file_path=None, content_hash=None):
        """Check if a file has been processed"""
        # Check by file ID
        if file_id in self._processed_files:
            return True
            
        # Check by content hash if provided
        if content_hash and content_hash in self._content_hashes:
            return True
            
        # Check by file path if provided
        if file_path and file_path in self._file_paths:
            return True
            
        return False
    
    def mark_as_processed(self, file_id, file_name, file_path=None, content_hash=None):
        """Mark a file as processed"""
        if not self.is_processed(file_id, file_path, content_hash):
            self._processed_files.add(file_id)
            self.processed_files[file_id] = {
                "name": file_name,
                "path": file_path,
                "content_hash": content_hash,
                "timestamp": str(int(os.path.getmtime(PROCESSED_FILES_PATH))) if os.path.exists(PROCESSED_FILES_PATH) else "0"
            }
            if content_hash:
                self._content_hashes.add(content_hash)
            if file_path:
                self._file_paths.add(file_path)
            self._save_to_file()
            return True
        return False
    
    def get_processed_count(self):
        """Get the number of processed files"""
        return len(self._processed_files)
    
    def _save_to_file(self):
        """Save processed files to file"""
        try:
            # Update last updated timestamp
            self._last_updated = time.time()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(PROCESSED_FILES_PATH), exist_ok=True)
            
            with open(PROCESSED_FILES_PATH, 'w') as f:
                json.dump(self.processed_files, f)
                
            logger.info(f"Saved {len(self.processed_files)} processed file records to {PROCESSED_FILES_PATH}")
        except Exception as e:
            logger.error(f"Error saving processed files: {str(e)}")
    
    def _load_from_file(self):
        """Load processed files from file"""
        try:
            if os.path.exists(PROCESSED_FILES_PATH):
                with open(PROCESSED_FILES_PATH, 'r') as f:
                    self.processed_files = json.load(f)
                    # Initialize the set of processed file IDs
                    self._processed_files = set(self.processed_files.keys())
                    
                logger.info(f"Loaded {len(self.processed_files)} processed file records from {PROCESSED_FILES_PATH}")
            else:
                logger.info(f"No existing processed files record found at {PROCESSED_FILES_PATH}")
                self.processed_files = {}
                self._processed_files = set()
        except Exception as e:
            logger.error(f"Error loading processed files: {str(e)}")
            self.processed_files = {}
            self._processed_files = set()

def get_file_tracker():
    """Get or create a file tracker instance"""
    return ProcessedFileTracker()
