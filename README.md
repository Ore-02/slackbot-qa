# PDF Q&A Slackbot

A Python-based Slackbot that monitors PDF uploads, embeds their content in a vector database, and answers user questions using Google's Gemini 1.5 Flash model.

## Features

- **Automatic PDF monitoring**: Detects PDF uploads across the entire Slack workspace
- **Content extraction**: Extracts and processes text from PDFs using pdfplumber
- **Text storage and search**: Stores documents with metadata and implements keyword-based search
- **Question answering**: Answers user questions by finding relevant PDF content
- **AI-powered responses**: Uses Google's Gemini 1.5 Flash model to generate high-quality answers
- **Source references**: Provides citations to source PDF documents
- **Thread support**: Continues conversations in threads for focused discussions
- **Direct message support**: Answers questions in DMs for private queries

## Setup Instructions

### Prerequisites

- A Slack workspace with permission to add apps
- Google API key for Gemini API access
- Python 3.10+ environment

### Step 1: Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Choose "From scratch", provide a name (e.g., "PDF Q&A Bot"), and select your workspace
3. Under "OAuth & Permissions", add the following scopes:
   - `app_mentions:read`: Listen for @mentions
   - `chat:write`: Send messages in channels
   - `files:read`: Access files uploaded to Slack
   - `im:history`, `im:write`: Read and write in direct messages
   - `channels:history`: Read channel messages
   - `commands`: Add slash commands (optional)
4. Install the app to your workspace
5. Copy the "Bot User OAuth Token" (starts with `xoxb-`) and the "Signing Secret"

### Step 2: Set Up Environment Variables

Create a `.env` file in the project root using `.env.example` as a template:

```
# Slack Credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret

# Google AI Credentials 
GOOGLE_API_KEY=your-google-api-key

# Flask Session Secret
SESSION_SECRET=your-session-secret
```

### Step 3: Configure Event Subscriptions

1. Deploy the application to a server with a public URL
2. In your Slack App settings, go to "Event Subscriptions" and enable events
3. Set the Request URL to `https://your-domain.com/slack/events`
   - The application automatically handles Slack's URL verification challenge
   - If verification fails, ensure your server is publicly accessible and returning responses correctly
4. Subscribe to the following bot events:
   - `app_mention`
   - `message.im`
   - `file_shared`
   - `message.channels`

### Step 4: Run the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start the application
python main.py
```

## Using the Bot

### Processing PDFs

The bot automatically processes PDFs in these scenarios:
1. When a PDF is shared in a channel where the bot is present
2. When a PDF is uploaded directly to a channel where the bot is present
3. When the bot starts, it scans for existing PDFs in the workspace

### Asking Questions

You can ask questions in three ways:

1. **Channel Mentions**: Mention the bot in any channel:
   ```
   @pdfbot What are the key qualifications for the SRE role?
   ```

2. **Direct Messages**: Send a question directly to the bot:
   ```
   What is the expected timeline for the project?
   ```

3. **Thread Replies**: Reply in a thread where the bot is active:
   ```
   Can you provide more details about the requirements?
   ```

The bot will:
1. Search for relevant content in the indexed PDFs
2. Generate a comprehensive answer using Gemini
3. Provide source references to the PDF documents

## Architecture

### Components

- **Flask App (`app.py`)**: HTTP server that handles Slack events
- **Slack Bot (`slack_bot.py`)**: Core logic for Slack interactions and message handling
- **PDF Processor (`pdf_processor.py`)**: Extracts and chunks text from PDF files
- **Vector Store (`vector_store.py`)**: Manages vector embeddings and similarity search
- **Gemini Client (`gemini_client.py`)**: Interface with Google's Generative AI

### Data Flow

1. User uploads a PDF or asks a question
2. Slack events API sends an event to the Flask server
3. PDF files are processed, chunked, and stored in a simple document store
4. For questions, relevant chunks are retrieved using keyword matching
5. Gemini model generates an answer based on the relevant content
6. Response is sent back to the user in Slack

## Troubleshooting

- **Bot not responding**: Ensure all event subscriptions are configured correctly
- **PDF processing errors**: Check the server logs for specific error messages
- **Answer quality issues**: You may need to adjust the chunk size or overlap parameters

## Future Enhancements

- Support for more document formats (DOCX, TXT, etc.)
- Conversation history for more context-aware responses
- Custom embedding models for domain-specific applications
- Document management UI for tracking indexed documents
