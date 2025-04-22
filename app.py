import os
import logging
from flask import Flask
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bot import slack_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize the SlackRequestHandler
handler = SlackRequestHandler(slack_app)

@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Endpoint for handling Slack events"""
    return handler.handle(request=app.request)

@app.route("/", methods=["GET"])
def home():
    """Home page"""
    return "PDF Q&A Slackbot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
