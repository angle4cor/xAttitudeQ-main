from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT'))
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Forum API configuration
FORUM_API_URL = "https://forum.wrestling.pl/api"
FORUM_API_KEY = os.getenv('FORUM_API_KEY')
USER_MENTION_ID = "23055"
USER_MENTION_NAME = "xAttitude"

# xAI API configuration
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_API_KEY = os.getenv('XAI_API_KEY')

QUIZ_FORUM_ID = "233"

# Validate required environment variables
if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, FORUM_API_KEY, XAI_API_KEY]):
    raise ValueError("Missing required environment variables")