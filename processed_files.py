"""
Module for tracking processed PDF files
"""
import os
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Constants
PROCESSED_FILES_PATH = "vector_db/processed_files.json"

class ProcessedFileTracker:
    """Class to track which files have been processed to avoid duplication"""
    
    def __init__(self):
        """Initialize the tracker"""
        self.processed_files = {}
        self._load_from_file()
    
    def is_processed(self, file_id):
        """Check if a file has been processed"""
        return file_id in self.processed_files
    
    def mark_as_processed(self, file_id, file_name):
        """Mark a file as processed"""
        if file_id not in self.processed_files:
            self.processed_files[file_id] = {
                "name": file_name,
                "timestamp": str(int(os.path.getmtime(PROCESSED_FILES_PATH))) if os.path.exists(PROCESSED_FILES_PATH) else "0"
            }
            self._save_to_file()
            return True
        return False
    
    def get_processed_count(self):
        """Get the number of processed files"""
        return len(self.processed_files)
    
    def _save_to_file(self):
        """Save processed files to file"""
        try:
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
                    
                logger.info(f"Loaded {len(self.processed_files)} processed file records from {PROCESSED_FILES_PATH}")
            else:
                logger.info(f"No existing processed files record found at {PROCESSED_FILES_PATH}")
                self.processed_files = {}
        except Exception as e:
            logger.error(f"Error loading processed files: {str(e)}")
            self.processed_files = {}

def get_file_tracker():
    """Get or create a file tracker instance"""
    return ProcessedFileTracker()