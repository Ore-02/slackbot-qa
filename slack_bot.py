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

# Define scanning intervals
SCAN_INTERVAL_MINUTES = 60  # Scan for new documents every hour
CLEANUP_INTERVAL_DAYS = 7  # Clean up old conversations every week

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
        global SCAN_ENABLED
        if not SCAN_ENABLED:
            logger.info("Document scanning is disabled")
            return
            
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

# Helper function for one-time scanning (used for testing)
def run_document_scan_once():
    """Run a document scan once without scheduling"""
    scan_thread = threading.Thread(target=scan_existing_documents)
    scan_thread.daemon = True
    scan_thread.start()

# Define slash commands
@slack_app.command("/documents")
def handle_documents_command(ack, body, respond):
    """Handle /documents slash command to list all processed documents"""
    # Acknowledge the command request immediately
    ack()

    # Get response URL for async response
    response_url = body.get("response_url")

    # Add error handling around the response
    try:
        # Get processed files from tracker
        processed_files = file_tracker.processed_files

        if not processed_files:
            respond("No documents have been processed yet.")
            return

        # Organize files by type
        files_by_type = {}
        for file_id, file_info in processed_files.items():
            file_name = file_info.get("name", "Unknown")
            # Extract file extension
            _, ext = os.path.splitext(file_name)
            ext = ext.lower().lstrip('.')

            if ext not in files_by_type:
                files_by_type[ext] = []

            files_by_type[ext].append(file_name)

        # Format response
        response = "*Documents in Memory:*\n\n"

        total_docs = len(processed_files)
        response += f"*Total Documents:* {total_docs}\n\n"

        # Add summary by file type
        response += "*By File Type:*\n"
        for file_type, files in files_by_type.items():
            response += f"• {file_type.upper()}: {len(files)} files\n"

        response += "\n*Document List:*\n"

        # Add all documents organized by type
        for file_type, files in files_by_type.items():
            response += f"\n*{file_type.upper()} Files:*\n"
            for i, file_name in enumerate(sorted(files), 1):
                response += f"{i}. `{file_name}`\n"

        # Get vector store stats
        try:
            doc_count = len(vector_store.documents)
            response += f"\n*Vector Store:* {doc_count} chunks indexed"
        except Exception as e:
            response += f"\n*Vector Store:* Error getting stats - {str(e)}"

        # Add last scan timestamp
        last_scan = file_tracker._last_updated
        if last_scan:
            from datetime import datetime
            scan_time = datetime.fromtimestamp(last_scan).strftime('%Y-%m-%d %H:%M:%S')
            response += f"\n\n*Last Scan:* {scan_time}"

        # Send response with proper formatting
        respond({
            "response_type": "in_channel",
            "text": response
        })

    except Exception as e:
        logger.error(f"Error handling /documents command: {str(e)}")
        respond({
            "response_type": "ephemeral",
            "text": f"Error retrieving document list: {str(e)}"
        })

# Global flag to control document scanning
SCAN_ENABLED = True

@slack_app.command("/clear-documents")
def handle_clear_documents_command(ack, body, respond):
    """Handle /clear-documents slash command to delete documents from memory"""
    # Acknowledge the command request
    ack()
    
    try:
        global SCAN_ENABLED
        # Get the command text
        text = body.get('text', '').strip().lower()
        
        if text == 'all':
            # Clear all documents
            file_tracker.processed_files.clear()
            file_tracker._processed_files.clear()
            file_tracker._save_to_file()
            
            # Clear vector store and its file
            vector_store.documents = []
            vector_store._build_index()
            vector_store._save_to_file()
            
            # Clear the storage files
            if os.path.exists("vector_db/document_store.json"):
                os.remove("vector_db/document_store.json")
            if os.path.exists("vector_db/processed_files.json"):
                os.remove("vector_db/processed_files.json")
            
            # Disable scanning
            SCAN_ENABLED = False
            
            respond("Successfully cleared all documents from memory and disabled auto-scanning. Use `/clear-documents scan-on` to re-enable scanning.")
            
        elif text == 'scan-on':
            SCAN_ENABLED = True
            respond("Document scanning enabled. Documents will be ingested on next scan.")
            
        elif text == 'scan-off':
            SCAN_ENABLED = False
            respond("Document scanning disabled. Documents will not be automatically ingested.")
            
        elif text:
            # Get document name to delete
            found = False
            for file_id, file_info in list(file_tracker.processed_files.items()):
                if text in file_info['name'].lower():
                    # Remove from tracker
                    del file_tracker.processed_files[file_id]
                    file_tracker._processed_files.remove(file_id)
                    
                    # Remove related chunks from vector store
                    vector_store.documents = [doc for doc in vector_store.documents 
                                           if doc.get('metadata', {}).get('file_id') != file_id]
                    found = True
            
            if found:
                # Save changes and rebuild index
                file_tracker._save_to_file()
                vector_store._build_index()
                vector_store._save_to_file()
                respond(f"Successfully removed document containing '{text}' from memory.")
            else:
                respond(f"No document found containing '{text}'.")
        else:
            respond("Usage:\n• `/clear-documents all` - Clear all documents\n• `/clear-documents <name>` - Clear specific document")
            
    except Exception as e:
        logger.error(f"Error handling /clear-documents command: {str(e)}")
        respond(f"Error clearing documents: {str(e)}")

@slack_app.command("/debug")
def handle_debug_command(ack, body, respond):
    """Handle /debug slash command to provide system status"""
    # Acknowledge the command request
    ack()

    try:
        # Get processed files from tracker
        processed_files = file_tracker._processed_files

        # Organize files by type
        files_by_type = {}
        for file_id, file_info in processed_files.items():
            file_name = file_info.get("file_name", "Unknown")
            # Extract file extension
            _, ext = os.path.splitext(file_name)
            ext = ext.lower().lstrip('.')

            if ext not in files_by_type:
                files_by_type[ext] = []

            files_by_type[ext].append(file_name)

        # Format response
        response = "*System Status Report:*\n\n"

        # Add document stats
        total_docs = len(processed_files)
        response += f"*Documents:*\n• Total processed: {total_docs}\n"

        # Add summary by file type
        for file_type, files in files_by_type.items():
            response += f"• {file_type.upper()}: {len(files)} files\n"

        # Get vector store stats
        try:
            doc_count = len(vector_store.documents)
            response += f"\n*Vector Store:*\n• Chunks indexed: {doc_count}\n"

            # Get memory usage estimate
            import sys
            memory_estimate_mb = sys.getsizeof(vector_store.documents) / (1024 * 1024)
            response += f"• Memory usage (est.): {memory_estimate_mb:.2f} MB\n"
        except Exception as e:
            response += f"\n*Vector Store:* Error getting stats - {str(e)}\n"

        # Get conversation memory stats
        try:
            conversation_count = len(memory_manager.conversations)
            active_threads = sum(1 for c in memory_manager.conversations.values() 
                               if time.time() - c.get("last_updated", 0) < 24 * 60 * 60)  # Active in last 24h
            response += f"\n*Conversation Memory:*\n• Active threads: {active_threads}\n• Total threads: {conversation_count}\n"
        except Exception as e:
            response += f"\n*Conversation Memory:* Error getting stats - {str(e)}\n"

        # Add last scan timestamp and scan frequency
        last_scan = file_tracker._last_updated
        if last_scan:
            from datetime import datetime
            scan_time = datetime.fromtimestamp(last_scan).strftime('%Y-%m-%d %H:%M:%S')
            response += f"\n*Last Scan:* {scan_time}\n"

        # Add scanning interval info
        response += f"*Scan Interval:* {SCAN_INTERVAL_MINUTES} minutes\n"

        # Add uptime info
        import os

        # Send response
        respond(response)

    except Exception as e:
        logger.error(f"Error handling /debug command: {str(e)}")
        respond(f"Error generating debug report: {str(e)}")

# Scanning and cleanup functions
def start_periodic_scanning():
    """Start a thread to scan existing documents and schedule next scan"""
    scan_thread = threading.Thread(target=scan_existing_documents)
    scan_thread.daemon = True
    scan_thread.start()

    # Schedule the next scan after the configured interval
    logger.info(f"Scheduling next document scan in {SCAN_INTERVAL_MINUTES} minutes")
    threading.Timer(SCAN_INTERVAL_MINUTES * 60, start_periodic_scanning).start()

def start_periodic_cleanup():
    """Clean up old conversations and schedule next cleanup"""
    try:
        removed = memory_manager.cleanup_old_conversations()
        logger.info(f"Cleaned up {removed} old conversation threads")
    except Exception as e:
        logger.error(f"Error cleaning up conversations: {str(e)}")

    # Schedule the next cleanup after the configured interval
    threading.Timer(CLEANUP_INTERVAL_DAYS * 24 * 60 * 60, start_periodic_cleanup).start()

# Schedule initial tasks with a delay to allow the app to initialize
threading.Timer(10.0, start_periodic_scanning).start()  # Start first scan after 10 seconds
threading.Timer(24 * 60 * 60, start_periodic_cleanup).start()  # Start first cleanup after 24 hours