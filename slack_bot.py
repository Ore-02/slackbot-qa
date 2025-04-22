import os
import logging
import time
import threading
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pdf_processor import extract_text_from_pdf, process_pdf_file
from vector_store import get_vector_store, add_texts_to_vector_store, search_vector_store
from gemini_client import generate_answer
from processed_files import get_file_tracker

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

def download_pdf(file_url, file_id, file_name):
    """Download a PDF file from Slack"""
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
        logger.error(f"Error downloading PDF: {e}")
        return None

def process_pdf(file_path, file_id, file_name, channel_id=None, ts=None, silent=True):
    """Process a PDF file and store its content in the vector database"""
    try:
        # Extract text from PDF
        text_chunks = extract_text_from_pdf(file_path)
        
        if not text_chunks:
            if channel_id and ts and not silent:
                slack_client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=ts,
                    text=f"I couldn't extract any text from the PDF file '{file_name}'."
                )
            logger.warning(f"No text extracted from PDF: {file_name}")
            return
        
        # Add PDF chunks to vector store with metadata
        vector_store = get_vector_store()
        metadata = [{"source": file_name, "file_id": file_id, "page": i} for i in range(len(text_chunks))]
        add_texts_to_vector_store(vector_store, text_chunks, metadata)
        
        # Send confirmation message if requested and channel info is provided
        if channel_id and ts and not silent:
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=ts,
                text=f"I've processed the PDF '{file_name}' and added it to my knowledge base. You can now ask questions about it!"
            )
        
        # Clean up: Remove downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        if channel_id and ts and not silent:
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=ts,
                text=f"Sorry, I encountered an error processing the PDF file '{file_name}': {str(e)}"
            )

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
        
        # Check if it's a PDF
        if file["filetype"] != "pdf":
            return
        
        # Download and process the PDF silently
        logger.info(f"Processing shared PDF file: {file['name']}")
        file_path = download_pdf(file["url_private"], file_id, file["name"])
        if file_path:
            # Process silently without sending notifications
            process_pdf(file_path, file_id, file["name"])
            file_tracker.mark_as_processed(file_id, file["name"])
    
    except SlackApiError as e:
        logger.error(f"Error handling file shared event: {e}")

@slack_app.event("message")
def handle_message_events(body, logger):
    """Handle message events"""
    event = body.get("event", {})
    
    # Ignore bot messages and non-text messages
    if event.get("bot_id") or "text" not in event:
        return
    
    channel_id = event.get("channel")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    
    # Check if message has file attachments
    if "files" in event:
        for file in event["files"]:
            if file.get("filetype") == "pdf":
                file_id = file.get("id")
                
                # Skip if already processed
                if file_tracker.is_processed(file_id):
                    logger.info(f"Skipping already processed file: {file['name']}")
                    continue
                
                # Download and process the PDF silently
                logger.info(f"Processing PDF from message: {file['name']}")
                file_path = download_pdf(file["url_private"], file_id, file["name"])
                if file_path:
                    # Process silently without sending notifications
                    process_pdf(file_path, file_id, file["name"])
                    file_tracker.mark_as_processed(file_id, file["name"])
        
        # If this message only contained files, don't process as a question
        if not text.strip():
            return
    
    # Handle messages in DMs
    channel_type = event.get("channel_type", "")
    
    # Process the message as a question if it's in a DM (im) 
    # or if it's in a thread where the bot was previously mentioned
    if channel_type == "im" and text:
        # Message is in DM, process as a question
        process_question(text, channel_id, thread_ts)
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
                process_question(text, channel_id, thread_ts)
        except SlackApiError as e:
            logger.error(f"Error checking thread history: {e}")
            
def process_question(text, channel_id, thread_ts):
    """Process a message as a question and generate an answer"""
    try:
        if not text.strip():
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="Hello! I can answer questions about PDF documents. What would you like to know?"
            )
            return
        
        # Search for relevant chunks
        vector_store = get_vector_store()
        relevant_chunks = search_vector_store(vector_store, text)
        
        if not relevant_chunks:
            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="I don't have any relevant information to answer your question. Please upload PDF documents first."
            )
            return
        
        # Send processing message
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Thinking..."
        )
        
        # Generate answer using Gemini
        answer = generate_answer(text, relevant_chunks)
        
        # Create sources footnote
        sources = set()
        for doc in relevant_chunks:
            if "source" in doc.metadata:
                sources.add(doc.metadata["source"])
        
        source_text = ""
        if sources:
            source_text = "\n\n*Sources:* " + ", ".join([f"`{s}`" for s in sources])
        
        # Send answer
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"{answer}{source_text}"
        )
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Sorry, I encountered an error while trying to answer your question: {str(e)}"
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

def scan_existing_pdfs():
    """Scan and process existing PDF files in the workspace"""
    try:
        logger.info("Starting scan for existing PDF files...")
        
        # Get list of all PDF files in the workspace
        # Use pagination to get all files (up to a reasonable limit)
        cursor = None
        all_files = []
        max_pages = 5  # Limit to 5 pages (500 files) for safety
        
        for _ in range(max_pages):
            try:
                if cursor:
                    response = slack_client.files_list(types="pdf", limit=100, cursor=cursor)
                else:
                    response = slack_client.files_list(types="pdf", limit=100)
                
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
        
        logger.info(f"Found {len(all_files)} total PDF files.")
        
        # Process files that haven't been processed yet
        processed_count = 0
        for i, file in enumerate(all_files):
            file_id = file.get("id")
            file_name = file.get("name")
            
            try:
                # Skip files that have already been processed
                if file_tracker.is_processed(file_id):
                    logger.info(f"Skipping already processed PDF: {file_name}")
                    continue
                
                logger.info(f"Processing PDF {i+1}/{len(all_files)}: {file_name}")
                file_path = download_pdf(file["url_private"], file_id, file_name)
                
                if file_path:
                    # Process the PDF silently (no channel notifications)
                    process_pdf(file_path, file_id, file_name)
                    file_tracker.mark_as_processed(file_id, file_name)
                    processed_count += 1
                    
                    # Give the system time to clear memory
                    time.sleep(2)
                    
                    # Process in smaller batches to avoid memory issues
                    if processed_count % 5 == 0:
                        logger.info(f"Processed {processed_count} files, taking a short break...")
                        time.sleep(10)  # Longer break every 5 files
            except Exception as e:
                logger.error(f"Error processing existing PDF {file_name}: {e}")
        
        logger.info(f"Completed scanning PDF files. Processed {processed_count} new files.")
    
    except Exception as e:
        logger.error(f"Error scanning existing PDFs: {e}")

# Start scanning existing PDFs in a separate thread when the app starts
def start_scanning_thread():
    """Start a thread to scan existing PDFs"""
    scan_thread = threading.Thread(target=scan_existing_pdfs)
    scan_thread.daemon = True
    scan_thread.start()

# Schedule scanning thread to start after a delay
def schedule_scan():
    """Schedule the scanning thread to start after a delay"""
    threading.Timer(10.0, start_scanning_thread).start()

# Schedule the scan when the module is imported
schedule_scan()
