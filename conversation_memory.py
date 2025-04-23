"""
Module for managing conversation memory in threads
"""
import os
import json
import time
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_PATH = "vector_db"
CONVERSATIONS_FILE = "conversations.json"
MAX_CONVERSATION_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_MESSAGES_PER_THREAD = 50  # Maximum messages to keep per thread

class ConversationMemory:
    """Class to track and manage conversation memory across different threads"""

    def __init__(self):
        """Initialize the memory manager"""
        self.conversations = {}  # Map of thread_id -> conversation data
        self._load_from_file()

    def add_message(self, thread_id: str, channel_id: str, user: str, text: str, is_bot: bool = False) -> None:
        """
        Add a message to a conversation thread
        
        Args:
            thread_id: Thread ID (unique identifier for the conversation)
            channel_id: Channel ID where the message was sent
            user: User ID who sent the message
            text: Message text content
            is_bot: Whether the message is from the bot
        """
        # Create conversation entry if it doesn't exist
        if thread_id not in self.conversations:
            self.conversations[thread_id] = {
                "channel_id": channel_id,
                "messages": [],
                "last_updated": time.time()
            }
        
        # Add the message
        message = {
            "user": user,
            "text": text,
            "timestamp": time.time(),
            "is_bot": is_bot
        }
        
        # Append to messages list
        self.conversations[thread_id]["messages"].append(message)
        
        # Update last_updated time
        self.conversations[thread_id]["last_updated"] = time.time()
        
        # Limit number of messages per thread to avoid memory issues
        if len(self.conversations[thread_id]["messages"]) > MAX_MESSAGES_PER_THREAD:
            # Remove oldest messages
            excess = len(self.conversations[thread_id]["messages"]) - MAX_MESSAGES_PER_THREAD
            self.conversations[thread_id]["messages"] = self.conversations[thread_id]["messages"][excess:]
        
        # Save to file
        self._save_to_file()

    def get_conversation_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a thread
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of message dictionaries
        """
        if thread_id in self.conversations:
            # Update last_updated time
            self.conversations[thread_id]["last_updated"] = time.time()
            
            # Return the messages
            return self.conversations[thread_id]["messages"]
        
        return []

    def get_history_as_text(self, thread_id: str) -> str:
        """
        Get the conversation history as formatted text for context
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Formatted conversation history text
        """
        if thread_id not in self.conversations:
            return ""
        
        # Format the conversation history
        history_text = ""
        for i, message in enumerate(self.conversations[thread_id]["messages"]):
            prefix = "🤖 Bot: " if message.get("is_bot", False) else "👤 User: "
            history_text += f"{prefix}{message.get('text', '')}\n\n"
        
        return history_text

    def clear_conversation(self, thread_id: str) -> None:
        """
        Clear a conversation history
        
        Args:
            thread_id: Thread ID to clear
        """
        if thread_id in self.conversations:
            del self.conversations[thread_id]
            self._save_to_file()

    def cleanup_old_conversations(self) -> int:
        """
        Remove old conversations based on last access time
        
        Returns:
            Number of conversations removed
        """
        now = time.time()
        removed_count = 0
        
        # Identify old conversations
        old_threads = []
        for thread_id, conversation in self.conversations.items():
            last_updated = conversation.get("last_updated", 0)
            if now - last_updated > MAX_CONVERSATION_AGE:
                old_threads.append(thread_id)
        
        # Remove old conversations
        for thread_id in old_threads:
            del self.conversations[thread_id]
            removed_count += 1
        
        # Save changes if any conversations were removed
        if removed_count > 0:
            self._save_to_file()
            logger.info(f"Cleaned up {removed_count} old conversations")
        
        return removed_count

    def _save_to_file(self) -> None:
        """Save conversations to file"""
        try:
            if not os.path.exists(VECTOR_DB_PATH):
                os.makedirs(VECTOR_DB_PATH)
                
            file_path = os.path.join(VECTOR_DB_PATH, CONVERSATIONS_FILE)
            
            with open(file_path, 'w') as f:
                json.dump(self.conversations, f)
        except Exception as e:
            logger.error(f"Error saving conversations: {str(e)}")

    def _load_from_file(self) -> None:
        """Load conversations from file"""
        try:
            file_path = os.path.join(VECTOR_DB_PATH, CONVERSATIONS_FILE)
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.conversations = json.load(f)
                    
                logger.info(f"Loaded conversation memory from {file_path}")
            else:
                logger.info(f"No existing conversation memory found at {file_path}")
        except Exception as e:
            logger.error(f"Error loading conversations: {str(e)}")

# Singleton instance
_memory_manager = None

def get_memory_manager() -> ConversationMemory:
    """
    Get or create a memory manager instance
    
    Returns:
        ConversationMemory instance
    """
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = ConversationMemory()
    
    return _memory_manager