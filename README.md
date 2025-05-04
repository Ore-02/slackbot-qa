## Slack Bot for Document Processing
A Python-based Slackbot that automatically processes documents shared in channels, providing instant answers and reference citations based on file content.



## Installation 
Ensure you have Python 3.10+ installed. Clone the repository and install dependencies:

```bash
git clone https://github.com/your-org/pdf-qa-slackbot.git
cd pdf-qa-slackbot
pip install -r requirements.txt
```

---

## Configuration
1. **Create a `.env` file** in the project root based on `.env.example`:
   ```dotenv
   # Slack Credentials
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGNING_SECRET=your-signing-secret

   # Google AI Credentials
   GOOGLE_API_KEY=your-google-api-key

   # Flask Session Secret
   SESSION_SECRET=your-session-secret
   ```
2. **Slack App Setup** (if not already):
   - Go to https://api.slack.com/apps → **Create New App** → From scratch → choose a name and workspace.
   - Under **OAuth & Permissions**, add scopes:
     - `app_mentions:read`
     - `chat:write`
     - `files:read`
     - `im:history`, `im:write`
     - `channels:history`
   - Enable **Event Subscriptions**:
     - Request URL: `https://<your-domain>/slack/events`
     - Subscribe to events: `app_mention`, `message.im`, `file_shared`, `message.channels`.
   - Install the app and copy **Bot User OAuth Token** & **Signing Secret** into `.env`.

---

## Usage
Run the application:

```bash
python main.py
```

### Processing Documents
The bot automatically processes supported files silently (no channel notifications) in these scenarios:
- When a file is shared in a channel where the bot is present.
- When a file is uploaded directly to a channel where the bot is present.
- On startup, the bot scans and indexes all existing files in the workspace.

Processed file IDs are tracked to prevent duplicate indexing and allow efficient incremental updates.

### Asking Questions
You can query the bot in three ways:
1. **Channel Mention**:
   ```
   @bot-name What are our core values?
   ```
2. **Direct Message**:
   ```
   What is the product roadmap timeline?
   ```
3. **Thread Reply**:
   ```
   (In thread) Can you provide more details on the SRE requirements?
   ```
The bot will search the indexed content, generate an answer via Gemini 1.5 Flash, and include source references linking back to the original document chunks.

---

## Supported File Types
- PDF
- DOCX
- TXT
- MD
- XLSX

---

## Features
- **Automatic Document Monitoring**: Detects new files across all channels where installed.
- **Content Extraction**: Uses `pdfplumber` for PDFs and native parsers for other formats.
- **Vector Embeddings & Search**: Stores document chunks with metadata for similarity and keyword search.
- **AI-Powered Answers**: Leverages Google Gemini 1.5 Flash for high-quality responses.
- **Source Citations**: Provides inline citations pointing to document origins.
- **Thread & DM Support**: Keeps conversations organized and private queries separate.
- **Silent Processing**: Indexes files without generating Slack notifications.
- **Duplicate Prevention**: Tracks processed file IDs to avoid re-indexing.
- **Complete Workspace Scanning**: Indexes all historical files on startup.
- **Slack Challenge Handling**: Automatically responds to Slack URL verification.

---

## Architecture
**Components:**
- **Flask Server (`app.py`)**: Handles incoming Slack events & verification.
- **Slack Bot (`slack_bot.py`)**: Core logic for message handling.
- **PDF Processor (`pdf_processor.py`)**: Extracts and chunks PDF text.
- **Vector Store (`vector_store.py`)**: Manages embeddings & similarity search.
- **Processed Files (`processed_files.py`)**: Tracks what’s been indexed.
- **Gemini Client (`gemini_client.py`)**: Interfaces with Google’s AI API.

**Data Flow:**
1. User uploads or mentions.  
2. Slack Events API → Flask endpoint.  
3. File text extraction & embedding.  
4. Query triggers search & AI generation.  
5. Bot replies with answers + citations.

---

## Logging
- Info logs for file processing (filename, ID, timestamp).
- Error logs for exceptions in extraction, embedding, or API calls.
- Logs written to stdout by default; can be redirected to files via standard tooling.

---

## Troubleshooting
- **Bot not responding**: Verify event subscriptions & OAuth scopes.  
- **File extraction errors**: Check logs for stack traces; confirm file type support.  
- **Answer quality issues**: Adjust chunk size/overlap in `pdf_processor.py` or tweak prompt templates.

---

## Future Enhancements
- Support additional formats (e.g., PPTX, CSV).  
- Expand Data Sources  
- Build a web UI dashboard for managing indexed documents.  


---

