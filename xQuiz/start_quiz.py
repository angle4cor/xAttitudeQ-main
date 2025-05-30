import logging
from xQuiz.quiz_handler import QuizHandler
from api_calls import create_forum_topic
from config import USER_MENTION_ID, QUIZ_FORUM_ID

logger = logging.getLogger(__name__)

def start_quiz():
    """
    Creates a new quiz forum topic, then starts the quiz in it.
    """
    title = "Nowy Quiz Wrestlingowy"
    post_html = "<p>start quiz</p>"  # API expects HTML!
    # Create the topic and get its ID
    topic_id = create_forum_topic(title, post_html, USER_MENTION_ID, QUIZ_FORUM_ID)
    logger.info(f"Created new quiz topic with ID: {topic_id}")
    if topic_id:
        quiz_handler = QuizHandler()
        quiz_handler.handle_quiz_topic_create(topic_id, post_html)
    else:
        logger.error("Failed to create quiz topic!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_quiz()