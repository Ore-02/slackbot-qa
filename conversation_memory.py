"""
Module for managing conversation memory in threads
"""
import os
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MEMORY_FILE_PATH = "vector_db/conversations.json"
MAX_HISTORY_LENGTH = 5  # Number of turns to keep in the conversation history
MAX_SESSION_AGE = 60 * 60 * 24  # 24 hours in seconds

class ConversationMemory:
    """Class to track and manage conversation memory across different threads"""
    
    def __init__(self):
        """Initialize the memory manager"""
        self.conversations = {}  # thread_id -> conversation history
        self.last_access = {}  # thread_id -> timestamp
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
        # Create a new conversation if it doesn't exist
        if thread_id not in self.conversations:
            self.conversations[thread_id] = {
                "channel_id": channel_id,
                "messages": []
            }
        
        # Add the message
        self.conversations[thread_id]["messages"].append({
            "timestamp": time.time(),
            "user": user,
            "text": text,
            "is_bot": is_bot
        })
        
        # Trim history if needed
        if len(self.conversations[thread_id]["messages"]) > MAX_HISTORY_LENGTH * 2:  # Keep pairs of user and bot messages
            self.conversations[thread_id]["messages"] = self.conversations[thread_id]["messages"][-MAX_HISTORY_LENGTH * 2:]
        
        # Update last access time
        self.last_access[thread_id] = time.time()
        
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
            # Update last access time
            self.last_access[thread_id] = time.time()
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
        messages = self.get_conversation_history(thread_id)
        if not messages:
            return ""
        
        # Format the conversation history
        formatted_history = "Previous Conversation:\n"
        for msg in messages:
            speaker = "Bot" if msg.get("is_bot", False) else "User"
            formatted_history += f"{speaker}: {msg.get('text', '')}\n"
        
        return formatted_history
    
    def clear_conversation(self, thread_id: str) -> None:
        """
        Clear a conversation history
        
        Args:
            thread_id: Thread ID to clear
        """
        if thread_id in self.conversations:
            del self.conversations[thread_id]
            if thread_id in self.last_access:
                del self.last_access[thread_id]
            self._save_to_file()
    
    def cleanup_old_conversations(self) -> int:
        """
        Remove old conversations based on last access time
        
        Returns:
            Number of conversations removed
        """
        current_time = time.time()
        threads_to_remove = []
        
        for thread_id, last_accessed in self.last_access.items():
            if current_time - last_accessed > MAX_SESSION_AGE:
                threads_to_remove.append(thread_id)
        
        for thread_id in threads_to_remove:
            if thread_id in self.conversations:
                del self.conversations[thread_id]
            del self.last_access[thread_id]
        
        if threads_to_remove:
            self._save_to_file()
            
        return len(threads_to_remove)
    
    def _save_to_file(self) -> None:
        """Save conversations to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(MEMORY_FILE_PATH), exist_ok=True)
            
            data = {
                "conversations": self.conversations,
                "last_access": self.last_access
            }
            
            with open(MEMORY_FILE_PATH, 'w') as f:
                json.dump(data, f)
            
            logger.debug(f"Saved {len(self.conversations)} conversations to {MEMORY_FILE_PATH}")
        except Exception as e:
            logger.error(f"Error saving conversations: {str(e)}")
    
    def _load_from_file(self) -> None:
        """Load conversations from file"""
        try:
            if os.path.exists(MEMORY_FILE_PATH):
                with open(MEMORY_FILE_PATH, 'r') as f:
                    data = json.load(f)
                    
                self.conversations = data.get("conversations", {})
                self.last_access = data.get("last_access", {})
                
                # Cleanup old conversations
                removed = self.cleanup_old_conversations()
                
                logger.info(f"Loaded {len(self.conversations)} conversations from {MEMORY_FILE_PATH} (removed {removed} old conversations)")
            else:
                logger.info(f"No existing conversation memory found at {MEMORY_FILE_PATH}")
                self.conversations = {}
                self.last_access = {}
        except Exception as e:
            logger.error(f"Error loading conversations: {str(e)}")
            self.conversations = {}
            self.last_access = {}

def get_memory_manager() -> ConversationMemory:
    """
    Get or create a memory manager instance
    
    Returns:
        ConversationMemory instance
    """
    return ConversationMemory()