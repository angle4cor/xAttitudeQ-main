# utils.py
import pymysql
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

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

def get_answered_posts():
    answered_posts = {}
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT conversation_id, content FROM messages WHERE author != 'ai'")
        for row in cursor.fetchall():
            conversation_id = row['conversation_id']
            content = row['content']
            if conversation_id not in answered_posts:
                answered_posts[conversation_id] = []
            answered_posts[conversation_id].append(content)
    connection.close()
    return answered_posts