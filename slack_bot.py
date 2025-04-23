import os
import logging
import time
import threading
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from document_processor import process_document, download_and_process_file
from enhanced_vector_store import get_enhanced_vector_store, add_texts_to_vector_store, search_vector_store
from gemini_client import generate_answer
from processed_files import get_file_tracker
from conversation_memory import get_memory_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Create WebClient instance
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

# Store our own bot info
BOT_ID = None
try:
    auth_test = slack_client.auth_test()
    BOT_ID = auth_test["bot_id"]
    logger.info(f"Bot ID: {BOT_ID}")
except SlackApiError as e:
    logger.error(f"Error obtaining bot ID: {e}")

# Initialize the file tracker
file_tracker = get_file_tracker()

# Initialize the conversation memory manager
memory_manager = get_memory_manager()

# Initialize the vector store
vector_store = get_enhanced_vector_store()

# Define supported file extensions
SUPPORTED_FILE_TYPES = ['pdf', 'docx', 'txt', 'md', 'xlsx']

def download_document(file_url, file_id, file_name):
    """Download a document file from Slack"""
    try:
        # Create temp directory if it doesn't exist
        if not os.path.exists("temp"):
            os.makedirs("temp")
        
        # Get file info
        response = slack_client.files_info(file=file_id)
        download_url = response["file"]["url_private"]
        
        file_path = f"temp/{file_name}"
        
        headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
        import requests
        r = requests.get(download_url, headers=headers)
        
        with open(file_path, "wb") as f:
            f.write(r.content)
        
        return file_path
    except SlackApiError as e:
        logger.error(f"Error downloading document: {e}")
        return None

def process_document_file(file_path, file_id, file_name, channel_id=None, thread_ts=None, silent=True):
    """Process a document file and store its content in the vector database"""
    try:
        # Extract text from document 
        text_chunks = process_document(file_path, file_id, file_name)
        
        if not text_chunks:
            if channel_id and thread_ts and not silent:
                slack_client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"I couldn't extract any text from the file '{file_name}'."
                )
            logger.warning(f"No text extracted from document: {file_name}")
            return
        
        # Add document chunks to vector store with metadata
        metadata = [{"source": file_name, "file_id": file_id, "chunk": i} for i in range(len(text_chunks))]
        add_texts_to_vector_store(vector_store, text_chunks, metadata)
        
        # Send confirmation message if requested and channel info is provided
        if channel_id and thread_ts and not silent:
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"I've processed '{file_name}' and added it to my knowledge base. You can now ask questions about it!"
            )
        
        # Clean up: Remove downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return True
            
    except Exception as e:
        logger.error(f"Error processing document '{file_name}': {str(e)}")
        if channel_id and thread_ts and not silent:
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"Sorry, I encountered an error processing '{file_name}': {str(e)}"
            )
        return False

@slack_app.event("file_shared")
def handle_file_shared(event, say):
    """Handle file_shared events"""
    try:
        file_id = event.get("file_id")
        
        # Skip if already processed
        if file_tracker.is_processed(file_id):
            logger.info(f"Skipping already processed file: {file_id}")
            return
        
        # Get file info
        file_info = slack_client.files_info(file=file_id)
        file = file_info["file"]
        file_name = file.get("name", "")
        file_type = file.get("filetype", "").lower()
        
        # Check if it's a supported file type
        if file_type not in SUPPORTED_FILE_TYPES:
            logger.info(f"Unsupported file type: {file_type}")
            return
        
        # Download and process the document silently
        logger.info(f"Processing shared {file_type.upper()} file: {file_name}")
        file_path = download_document(file["url_private"], file_id, file_name)
        if file_path:
            # Process silently without sending notifications
            success = process_document_file(file_path, file_id, file_name)
            if success:
                file_tracker.mark_as_processed(file_id, file_name)
    
    except SlackApiError as e:
        logger.error(f"Error handling file shared event: {e}")

@slack_app.event("message")
def handle_message_events(body, logger):
    """Handle message events"""
    event = body.get("event", {})
    
    # Ignore bot messages and non-text messages
    if event.get("bot_id") or "text" not in event:
        return
    
    # Extract message details
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    timestamp = event.get("ts")
    thread_ts = event.get("thread_ts") or timestamp
    
    # Store the message in memory (for conversation history)
    memory_manager.add_message(
        thread_id=thread_ts,
        channel_id=channel_id,
        user=user_id,
        text=text,
        is_bot=False
    )
    
    # Check if message has file attachments
    if "files" in event:
        for file in event["files"]:
            file_id = file.get("id")
            file_name = file.get("name", "")
            file_type = file.get("filetype", "").lower()
            
            # Skip if already processed
            if file_tracker.is_processed(file_id):
                logger.info(f"Skipping already processed file: {file_name}")
                continue
            
            # Check if it's a supported file type
            if file_type not in SUPPORTED_FILE_TYPES:
                continue
                
            # Download and process the document silently
            logger.info(f"Processing {file_type.upper()} from message: {file_name}")
            file_path = download_document(file["url_private"], file_id, file_name)
            if file_path:
                # Process silently without sending notifications
                success = process_document_file(file_path, file_id, file_name)
                if success:
                    file_tracker.mark_as_processed(file_id, file_name)
        
        # If this message only contained files, don't process as a question
        if not text.strip():
            return
    
    # Handle messages in DMs
    channel_type = event.get("channel_type", "")
    
    # Process the message as a question if it's in a DM (im) 
    # or if it's in a thread where the bot was previously mentioned
    if channel_type == "im" and text:
        # Message is in DM, process as a question
        process_question(text, channel_id, thread_ts, user_id)
    elif "thread_ts" in event and text:
        # Check if this is a thread where the bot was previously active
        try:
            # Get thread history
            thread_history = slack_client.conversations_replies(
                channel=channel_id,
                ts=event.get("thread_ts")
            )
            
            # Check if bot is in the thread
            bot_in_thread = False
            for message in thread_history.get("messages", []):
                if message.get("bot_id") == BOT_ID:
                    bot_in_thread = True
                    break
            
            if bot_in_thread:
                # Bot is active in this thread, process as a question
                process_question(text, channel_id, thread_ts, user_id)
        except SlackApiError as e:
            logger.error(f"Error checking thread history: {e}")
            
def process_question(text, channel_id, thread_ts, user_id=None):
    """Process a message as a question and generate an answer"""
    try:
        if not text.strip():
            response_text = "Hello! I can answer questions about documents in this workspace. What would you like to know?"
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=response_text
            )
            
            # Store bot response in memory
            if user_id:
                memory_manager.add_message(
                    thread_id=thread_ts,
                    channel_id=channel_id,
                    user="bot",
                    text=response_text,
                    is_bot=True
                )
            return
        
        # Search for relevant chunks
        relevant_chunks = search_vector_store(vector_store, text)
        
        if not relevant_chunks:
            response_text = "I don't have any relevant information to answer your question. Please upload documents first."
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=response_text
            )
            
            # Store bot response in memory
            if user_id:
                memory_manager.add_message(
                    thread_id=thread_ts,
                    channel_id=channel_id,
                    user="bot",
                    text=response_text,
                    is_bot=True
                )
            return
        
        # Send processing message
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Thinking..."
        )
        
        # Get conversation history
        conversation_history = ""
        if thread_ts:
            conversation_history = memory_manager.get_history_as_text(thread_ts)
        
        # Generate answer using Gemini with conversation history
        answer = generate_answer(text, relevant_chunks, conversation_history)
        
        # Create sources footnote
        sources = set()
        for doc in relevant_chunks:
            if "source" in doc.metadata:
                sources.add(doc.metadata["source"])
        
        source_text = ""
        if sources:
            source_text = "\n\n*Sources:* " + ", ".join([f"`{s}`" for s in sources])
        
        # Final response
        response_text = f"{answer}{source_text}"
        
        # Send answer
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=response_text
        )
        
        # Store bot response in memory
        if user_id:
            memory_manager.add_message(
                thread_id=thread_ts,
                channel_id=channel_id,
                user="bot",
                text=answer,  # Store without source text for better conversation flow
                is_bot=True
            )
    
    except Exception as e:
        error_message = f"Sorry, I encountered an error while trying to answer your question: {str(e)}"
        logger.error(f"Error processing question: {e}")
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=error_message
        )
        
        # Store error response in memory
        if user_id:
            memory_manager.add_message(
                thread_id=thread_ts,
                channel_id=channel_id,
                user="bot",
                text=error_message,
                is_bot=True
            )

@slack_app.event("app_mention")
def handle_app_mentions(body, say):
    """Handle app mention events"""
    event = body.get("event", {})
    text = event.get("text", "")
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    
    # Remove the app mention from the text
    import re
    cleaned_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    
    # Use the shared process_question function to handle the query
    process_question(cleaned_text, channel, thread_ts)

def scan_existing_documents():
    """Scan and process existing document files in the workspace"""
    try:
        logger.info("Starting scan for existing documents...")
        
        # Build the types string for all supported file types
        file_types = ",".join(SUPPORTED_FILE_TYPES)
        
        # Get list of all supported document files in the workspace
        # Use pagination to get all files (up to a reasonable limit)
        cursor = None
        all_files = []
        max_pages = 5  # Limit to 5 pages (500 files) for safety
        
        for _ in range(max_pages):
            try:
                if cursor:
                    response = slack_client.files_list(types=file_types, limit=100, cursor=cursor)
                else:
                    response = slack_client.files_list(types=file_types, limit=100)
                
                files = response.get("files", [])
                all_files.extend(files)
                
                # Check if there are more files
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                    
                # Avoid hitting rate limits
                time.sleep(1)
            except SlackApiError as e:
                logger.error(f"Error listing files: {e}")
                break
        
        logger.info(f"Found {len(all_files)} total document files.")
        
        # Process files that haven't been processed yet
        processed_count = 0
        for i, file in enumerate(all_files):
            file_id = file.get("id")
            file_name = file.get("name")
            file_type = file.get("filetype", "").lower()
            
            try:
                # Skip files that have already been processed
                if file_tracker.is_processed(file_id):
                    logger.info(f"Skipping already processed {file_type.upper()}: {file_name}")
                    continue
                
                # Skip unsupported file types (shouldn't happen, but just in case)
                if file_type not in SUPPORTED_FILE_TYPES:
                    logger.info(f"Skipping unsupported file type: {file_type}")
                    continue
                
                logger.info(f"Processing {file_type.upper()} {i+1}/{len(all_files)}: {file_name}")
                
                # Get headers for downloading
                headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
                
                # Process the document
                text_chunks = download_and_process_file(
                    url=file.get("url_private"),
                    file_id=file_id,
                    file_name=file_name,
                    headers=headers
                )
                
                if text_chunks:
                    # Add document to vector store
                    metadata = [{"source": file_name, "file_id": file_id, "chunk": i} 
                              for i in range(len(text_chunks))]
                    add_texts_to_vector_store(vector_store, text_chunks, metadata)
                    
                    # Mark as processed
                    file_tracker.mark_as_processed(file_id, file_name)
                    processed_count += 1
                    
                    # Give the system time to clear memory
                    time.sleep(2)
                    
                    # Process in smaller batches to avoid memory issues
                    if processed_count % 5 == 0:
                        logger.info(f"Processed {processed_count} files, taking a short break...")
                        time.sleep(10)  # Longer break every 5 files
            except Exception as e:
                logger.error(f"Error processing existing {file_type} {file_name}: {e}")
        
        logger.info(f"Completed scanning document files. Processed {processed_count} new files.")
    
    except Exception as e:
        logger.error(f"Error scanning existing documents: {e}")

# Start scanning existing documents in a separate thread when the app starts
def start_scanning_thread():
    """Start a thread to scan existing documents"""
    scan_thread = threading.Thread(target=scan_existing_documents)
    scan_thread.daemon = True
    scan_thread.start()

# Schedule scanning thread to start after a delay
def schedule_scan():
    """Schedule the scanning thread to start after a delay"""
    threading.Timer(10.0, start_scanning_thread).start()

# Schedule the scan when the module is imported
schedule_scan()
