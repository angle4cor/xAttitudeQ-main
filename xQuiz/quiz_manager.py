import logging
import random
from datetime import datetime, timedelta
import pymysql
from api_calls import send_to_xai
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

def get_db_connection():
    """Tworzy i zwraca połączenie z bazą danych."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

class QuizAnswerQueue:
    def __init__(self):
        self.connection = get_db_connection()
    
    def __del__(self):
        """Zamyka połączenie z bazą przy usuwaniu obiektu."""
        if hasattr(self, 'connection') and self.connection.open:
            self.connection.close()
    
    def add_answer(self, question_id, user_name, answer):
        """
        Dodaje odpowiedź do kolejki.
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO quiz_answer_queue (question_id, user_name, answer, timestamp)
                    VALUES (%s, %s, %s, %s)
                """, (question_id, user_name, answer, datetime.utcnow()))
                self.connection.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding answer to queue: {e}")
            self.connection.rollback()
            return False
    
    def get_pending_answers(self, question_id):
        """
        Pobiera listę nieprzetworzonych odpowiedzi dla pytania.
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, user_name, answer, timestamp
                    FROM quiz_answer_queue
                    WHERE question_id = %s 
                      AND processed = FALSE
                    ORDER BY timestamp ASC
                """, (question_id,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching pending answers: {e}")
            return []
    
    def mark_answers_as_processed(self, answer_ids):
        """
        Oznacza odpowiedzi jako przetworzone.
        """
        if not answer_ids:
            return True
        try:
            placeholders = ','.join(['%s'] * len(answer_ids))
            with self.connection.cursor() as cursor:
                cursor.execute(f"""
                    UPDATE quiz_answer_queue
                    SET processed = TRUE
                    WHERE id IN ({placeholders})
                """, answer_ids)
                self.connection.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking answers as processed: {e}")
            self.connection.rollback()
            return False
    
    def should_process_answers(self, question_id):
        """
        Sprawdza, czy należy przetworzyć odpowiedzi w kolejce.
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        MIN(timestamp) as first_answer,
                        COUNT(*) as answer_count
                    FROM quiz_answer_queue
                    WHERE question_id = %s 
                      AND processed = FALSE
                """, (question_id,))
                result = cursor.fetchone()
                if not result or not result['first_answer']:
                    return False
                time_passed = datetime.utcnow() - result['first_answer']
                return time_passed >= timedelta(minutes=1) or result['answer_count'] >= 3
        except Exception as e:
            logger.error(f"Error checking if answers should be processed: {e}")
            return False

def create_new_quiz_game(topic_id, question, answer, hints, category):
    """
    Tworzy nową grę quizową - dodaje pytanie oraz odpowiadające podpowiedzi do bazy.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO quiz_questions (topic_id, question, answer, category)
                VALUES (%s, %s, %s, %s)
            """, (topic_id, question, answer, category))
            question_id = cursor.lastrowid
            logger.info(f"Created new quiz question with ID: {question_id}")
            # Zapisz wszystkie początkowe podpowiedzi
            for i, hint in enumerate(hints, 1):
                if hint:  # Sprawdź, czy podpowiedź nie jest pusta
                    cursor.execute("""
                        INSERT INTO quiz_hints (question_id, hint_order, hint_text)
                        VALUES (%s, %s, %s)
                    """, (question_id, i, hint))
            connection.commit()
            return question_id
    except Exception as e:
        logger.error(f"Error creating quiz game: {e}")
        connection.rollback()
        return None
    finally:
        connection.close()

def get_quiz_scores():
    """
    Pobiera ranking wyników quizu.
    Ranguje wszystkich użytkowników na podstawie zdobytych punktów od największej do najmniejszej wartości.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT user_name, score
                FROM quiz_scores
                ORDER BY score DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting quiz scores: {e}")
        return []
    finally:
        connection.close()

def update_user_score(user_name, points):
    """
    Aktualizuje wynik użytkownika.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO quiz_scores (user_name, score)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE score = score + %s
            """, (user_name, points, points))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating user score: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_next_hint(question, posts_history=None):
    conversation = ""
    if posts_history:
        conversation = "\n".join(f"{post['author']}: {post['content']}" for post in posts_history)
    prompt = (
        f'Na podstawie tej rozmowy o pytaniu "{question}" wygeneruj jedną kreatywną podpowiedź w formacie JSON:\n'
        '{ "hint": "Twoja podpowiedź tutaj." }\n'
        "Nie dodawaj żadnego komentarza, nie dodawaj tekstu przed ani po JSON."
    )
    response = send_to_xai(prompt)
    try:
        data = json.loads(response)
        return data.get("hint")
    except Exception as e:
        logger.error(f"Błąd parsowania podpowiedzi: {e}, response: {response}")
        return None

def get_next_hint_db(question_id):
    """
    Pobiera następną zapisaną podpowiedź z bazy danych dla pytania.
    Używana tylko, gdy podpowiedzi były generowane wcześniej.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT hint_text
                FROM quiz_hints
                WHERE question_id = %s
                  AND hint_order = (
                        SELECT COALESCE(MAX(hint_order), 0) + 1
                        FROM quiz_hints
                        WHERE question_id = %s
                  )
            """, (question_id, question_id))
            result = cursor.fetchone()
            return result['hint_text'] if result else None
    except Exception as e:
        logger.error(f"Error getting next hint from DB: {e}")
        return None
    finally:
        connection.close()

def get_current_question(topic_id):
    """
    Pobiera ostatnio dodane pytanie dla danego tematu.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, question, answer, created_at
                FROM quiz_questions
                WHERE topic_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (topic_id,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting current question: {e}")
        return None
    finally:
        connection.close()

def add_hint_to_quiz(question_id, hint_text, hint_order=None):
    """
    Dodaje nową podpowiedź do pytania quizowego.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if hint_order is None:
                cursor.execute("""
                    SELECT COALESCE(MAX(hint_order), 0) + 1 as next_order
                    FROM quiz_hints
                    WHERE question_id = %s
                """, (question_id,))
                result = cursor.fetchone()
                hint_order = result['next_order']
            cursor.execute("""
                INSERT INTO quiz_hints (question_id, hint_text, hint_order)
                VALUES (%s, %s, %s)
            """, (question_id, hint_text, hint_order))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding hint to quiz: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_random_quiz_question():
    prompt = (
        "Wygeneruj jedno pytanie quizowe o wrestlingu. Odpowiedz WYŁĄCZNIE w formacie JSON:\n"
        "{\n"
        '  "question": "Pytanie tekstowe tutaj.",\n'
        '  "answer": "Odpowiedź tekstowa tutaj.",\n'
        '  "hints": []\n'
        "}\n"
        "Nie dodawaj żadnego komentarza, nie dodawaj tekstu przed ani po JSON."
    )
    response = send_to_xai(prompt)
    try:
        data = json.loads(response)
        assert "question" in data and "answer" in data and "hints" in data
        return data
    except Exception as e:
        logger.error(f"Błąd parsowania odpowiedzi z xAI: {e}, response: {response}")
        return None

def get_random_pro_wrestling_joke():
    """
    Tworzy losowy żart związany z wrestlingiem przy użyciu xAI.
    """
    prompt = "Opowiedz śmieszny żart o pro wrestlingu."
    return send_to_xai(prompt)