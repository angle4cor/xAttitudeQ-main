# main.py
from flask import Flask, request, jsonify
import logging
from logging.handlers import TimedRotatingFileHandler
from config import USER_MENTION_NAME, USER_MENTION_ID
from handlers import process_notification
import os

app = Flask(__name__)

# Setup logging
log_directory = 'logs'
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

log_handler = TimedRotatingFileHandler(f'{log_directory}/xAttitude.log', when="midnight", interval=1)
log_handler.suffix = "%Y-%m-%d"
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log_handler.setLevel(logging.DEBUG)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.debug(f"Headers: {request.headers}")
    logger.debug(f"Raw data: {request.data.decode('utf-8')}")

    content_type = request.headers.get('Content-Type')
    logger.debug(f"Content type: {content_type}")

    if content_type == 'application/json':
        data = request.get_json()
    else:
        data = None

    logger.debug(f"Received data")

    event_type = request.headers.get('Webhook-Event')
    logger.debug(f"Webhook event type: {event_type}")

    try:
        if data is None:
            raise ValueError("No JSON data received")
        process_notification(data, event_type, USER_MENTION_ID, USER_MENTION_NAME)
    except Exception as e:
        logger.error(f"Error processing notification: {e}")

    return jsonify({'status': 'success'}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)