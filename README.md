# PDF Q&A Slackbot

A Python-based Slackbot that monitors PDF uploads, embeds their content in a vector database, and answers user questions using Gemini 1.5 Flash.

## Features

- Monitors Slack workspace for PDF uploads (new and existing files)
- Extracts text from PDFs using pdfplumber
- Embeds content using sentence-transformers/all-MiniLM-L6-v2
- Stores embeddings and metadata in ChromaDB vector database
- Answers user questions by searching the vector database for relevant content
- Generates answers using Google's Gemini 1.5 Flash model
- Responds in Slack with generated answers and source references

## Setup

1. Clone this repository
2. Create a `.env` file based on `.env.example` and fill in your credentials
3. Install the required dependencies
4. Run the application

## Environment Variables

- `SLACK_BOT_TOKEN`: Your Slack Bot Token (starts with xoxb-)
- `SLACK_SIGNING_SECRET`: Your Slack Signing Secret
- `GOOGLE_API_KEY`: Your Google API Key for Gemini
- `SESSION_SECRET`: Secret key for Flask sessions
- `SLACK_CHANNEL_ID`: (Optional) Specific channel ID for development

## Usage

1. Invite the bot to your Slack channels
2. Upload PDF files to the channel or mention the bot in a channel with existing PDFs
3. The bot will process the PDFs and store their content
4. Mention the bot with a question about the PDFs, e.g., `@pdfbot What does the document say about X?`
5. The bot will search for relevant information and respond with an answer

## Directory Structure

- `main.py`: Entry point for the application
- `app.py`: Flask application for handling Slack events
- `slack_bot.py`: Core Slackbot functionality
- `pdf_processor.py`: PDF text extraction
- `vector_store.py`: Vector database management
- `gemini_client.py`: Integration with Google's Gemini model

## Implementation Details

- Uses slack_bolt for Slack integration
- Extracts text from PDFs using pdfplumber
- Embeds content using sentence-transformers
- Stores embeddings and metadata in ChromaDB
- Generates answers using Gemini 1.5 Flash via Google AI SDK
