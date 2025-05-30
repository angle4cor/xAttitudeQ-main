# conversation_manager.py
from datetime import datetime, timezone, timedelta
import pymysql
import logging
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Define the inactivity timeout
INACTIVITY_TIMEOUT = timedelta(minutes=15)

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

def get_next_conversation_id():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT MAX(CAST(conversation_id AS UNSIGNED)) AS max_id FROM conversations")
            max_id = cursor.fetchone()['max_id']
            return str(max_id + 1) if max_id else "1"
    finally:
        connection.close()

def create_new_conversation(topic_id, username, conversation_id=None):
    if conversation_id is None:
        conversation_id = get_next_conversation_id()
    else:
        conversation_id = str(conversation_id)  # Ensure it is a string
    logging.debug(f"Creating new conversation with ID: {conversation_id}")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO conversations (conversation_id, last_activity, is_active, topic_id, username)
                VALUES (%s, %s, %s, %s, %s)
            """, (conversation_id, datetime.now(timezone.utc), True, topic_id, username))
            connection.commit()
    except Exception as e:
        logging.error(f"Error creating new conversation: {e}")
    finally:
        connection.close()
    return conversation_id

def add_message_to_conversation(conversation_id, author, content, username):
    conversation_id = str(conversation_id)  # Ensure it is a string
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO messages (conversation_id, author, timestamp, content, username)
                VALUES (%s, %s, %s, %s, %s)
            """, (conversation_id, author, datetime.now(timezone.utc), content, username))
            cursor.execute("""
                UPDATE conversations
                SET last_activity=%s
                WHERE conversation_id=%s
            """, (datetime.now(timezone.utc), conversation_id))
            connection.commit()
    except Exception as e:
        logging.error(f"Error adding message to conversation: {e}")
    finally:
        connection.close()

def get_active_conversation_id(topic_id, username):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT conversation_id, last_activity
                FROM conversations
                WHERE topic_id = %s AND username = %s AND is_active = TRUE
                ORDER BY last_activity DESC
                LIMIT 1
            """, (topic_id, username))
            result = cursor.fetchone()
            if result:
                last_activity = result['last_activity']
                # Ensure last_activity is aware of the timezone
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_activity <= INACTIVITY_TIMEOUT:
                    return str(result['conversation_id'])
    finally:
        connection.close()
    return None

def get_conversation_history(conversation_id):
    conversation_id = str(conversation_id)  # Ensure it is a string
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT author, timestamp, content, username
                FROM messages
                WHERE conversation_id=%s
                ORDER BY timestamp
            """, (conversation_id,))
            result = cursor.fetchall()
    finally:
        connection.close()
    return result

def mark_conversation_as_inactive(conversation_id):
    conversation_id = str(conversation_id)  # Ensure it is a string
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE conversations
                SET is_active=False
                WHERE conversation_id=%s
            """, (conversation_id,))
            connection.commit()
    finally:
        connection.close()

def check_inactivity(conversation_id):
    conversation_id = str(conversation_id)  # Ensure it is a string
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT last_activity
                FROM conversations
                WHERE conversation_id=%s
            """, (conversation_id,))
            last_activity = cursor.fetchone()['last_activity']
            # Ensure last_activity is aware of the timezone
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_activity > INACTIVITY_TIMEOUT:
                mark_conversation_as_inactive(conversation_id)
                return True
    finally:
        connection.close()
    return False

def is_conversation_active(conversation_id):
    conversation_id = str(conversation_id)  # Ensure it is a string
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT is_active
                FROM conversations
                WHERE conversation_id=%s
            """, (conversation_id,))
            result = cursor.fetchone()['is_active']
    finally:
        connection.close()
    return result