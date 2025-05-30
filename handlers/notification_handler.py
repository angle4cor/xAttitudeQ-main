# handlers/notification_handler.py
import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import unquote, urlparse, urlunparse
import requests
from utils import get_answered_posts
from conversation_manager import (
    get_active_conversation_id,
    create_new_conversation,
    add_message_to_conversation,
    get_conversation_history,
    check_inactivity,
    mark_conversation_as_inactive,
)
from handlers.image_handler import handle_image_request
from api_calls import send_to_xai, post_forum_reply, check_if_image_request, determine_query_type
from config import USER_MENTION_NAME, USER_MENTION_ID

logger = logging.getLogger()

def process_notification(notification, notification_type, user_mention_id, user_mention_name):
    try:
        logger.debug(f"Processing notification type: {notification_type}")

        content = ''
        topic_id = None
        url = ''
        author_id = None
        username = None

        if notification_type == 'forumsTopic_create':
            topic_data = notification
            content = topic_data.get('content', '')
            topic_id = topic_data.get('id')
            url = topic_data.get('url', '')
            author_id = topic_data.get('author', {}).get('id')
            username = topic_data.get('author', {}).get('name')
        elif notification_type == 'forumsTopicPost_create':
            post_data = notification
            content = post_data.get('content', '')
            topic_id = post_data.get('item_id')
            url = post_data.get('url', '')
            author_id = post_data.get('author', {}).get('id')
            username = post_data.get('author', {}).get('name')
        else:
            logger.warning(f"Unhandled notification type: {notification_type}")
            return

        logger.debug(f"Extracted topic_id: {topic_id}")
        logger.debug(f"Author ID: {author_id}")
        logger.debug(f"Username: {username}")

        if username == user_mention_name:
            logger.info(f"Skipping processing for bot's own post.")
            return

        soup = BeautifulSoup(content, 'html.parser')
        mention_tag = soup.find('a', {'data-mentionid': user_mention_id})

        if not mention_tag:
            mention_tag = soup.find(text=re.compile(f"@{user_mention_name}"))

        if mention_tag:
            logger.info(f"Mention detected in notification content")

            answered_posts = get_answered_posts()

            if topic_id not in answered_posts or content not in answered_posts[topic_id]:
                question = soup.get_text().strip()
                question = unquote(question)

                sanitized_parts = []
                for part in question.split():
                    try:
                        parsed_url = urlparse(part)
                        if parsed_url.scheme and parsed_url.netloc:
                            sanitized_url = urlunparse(parsed_url._replace(netloc=parsed_url.netloc[:253]))
                            sanitized_parts.append(sanitized_url)
                        else:
                            sanitized_parts.append(part)
                    except Exception as e:
                        logger.error(f"Error parsing URL {part}: {e}")
                        sanitized_parts.append(part)

                sanitized_question = " ".join(sanitized_parts)
                logger.debug(f"Sanitized question: {sanitized_question}")

                conversation_id = get_active_conversation_id(topic_id, username)
                if not conversation_id:
                    logger.info(f"Conversation with topic ID {topic_id} is not active. Creating a new conversation.")
                    conversation_id = create_new_conversation(topic_id, username)

                is_image_query = determine_query_type(sanitized_question)
                if is_image_query:
                    xai_response = handle_image_request(content, sanitized_question)
                else:
                    add_message_to_conversation(str(conversation_id), "user", sanitized_question, username)
                    conversation_history = get_conversation_history(str(conversation_id))
                    context = "\n".join([f"{msg['author']}: {msg['content']}" for msg in conversation_history])
                    xai_response = send_to_xai(f"{context}\n{sanitized_question}")

                logger.debug(f"xAI response: {xai_response}")

                formatted_response = format_response(xai_response)

                try:
                    add_message_to_conversation(str(conversation_id), "ai", xai_response, user_mention_name)

                    reply_response = post_forum_reply(topic_id, formatted_response)
                    logger.info(f"Replied to topic {topic_id}: {xai_response}")
                    logger.debug(f"Reply post response: {reply_response}")

                    if check_inactivity(str(conversation_id)):
                        mark_conversation_as_inactive(str(conversation_id))
                        logger.info(f"Conversation with ID {conversation_id} has been marked as inactive.")

                except requests.exceptions.HTTPError as err:
                    logger.error(f"Error posting reply: {err}")
                    logger.error(f"Response content: {err.response.content}")

                return True
            else:
                logger.info(f"Topic {topic_id} already has a reply for this mention, skipping.")
        else:
            logger.info(f"No mention found in notification content, skipping.")
    except Exception as e:
        logger.error(f"Error: {e}")

    return False

def format_response(response):
    formatted_response = response.replace("\n", "<br>")
    formatted_response = f'<p style="text-align: justify;">{formatted_response}</p>'
    formatted_response = f'<div>{formatted_response}</div>'
    return formatted_response