import requests
from requests.auth import HTTPBasicAuth
from config import FORUM_API_URL, FORUM_API_KEY, XAI_API_URL, XAI_API_KEY, USER_MENTION_ID
import logging
import json
import time

def get_xai_auth_header():
    return {"Authorization": f"Bearer {XAI_API_KEY}"}

def get_latest_notifications():
    logging.info("Fetching latest notifications")
    response = requests.get(
        f"{FORUM_API_URL}/core/members/{USER_MENTION_ID}/notifications",
        auth=HTTPBasicAuth(FORUM_API_KEY, ''),
        headers={"User-Agent": "MyUserAgent/1.0"}
    )
    response.raise_for_status()
    return response.json()

def get_forum_posts_in_topic_since(topic_id, since_datetime):
    """
    Fetch forum posts in a given topic since the provided datetime.
    This is a stub! You must implement this with your forum API.
    """
    # Example: fetch posts from your forum API (pseudo code!)
    # You need to implement real fetching logic below.
    import requests
    from config import FORUM_API_URL, FORUM_API_KEY
    from requests.auth import HTTPBasicAuth

    # This is a pseudo endpoint. Change it to match your forum API docs!
    url = f"{FORUM_API_URL}/forums/topics/{topic_id}/posts?since={since_datetime.isoformat()}"

    headers = {
        "User-Agent": "MyUserAgent/1.0",
    }

    response = requests.get(
        url,
        auth=HTTPBasicAuth(FORUM_API_KEY, ''),
        headers=headers
    )
    response.raise_for_status()
    return response.json().get("posts", [])

def post_forum_reply(topic_id, reply_text):
    logging.info(f"Posting reply to topic ID: {topic_id}")
    url = f"{FORUM_API_URL}/forums/posts"
    headers = {
        "User-Agent": "MyUserAgent/1.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "topic": int(topic_id),
        "author": int(USER_MENTION_ID),
        "post": reply_text
    }

    logging.debug(f"POST URL: {url}")
    logging.debug(f"Headers: {headers}")
    logging.debug(f"Payload: {payload}")

    response = requests.post(
        url,
        auth=HTTPBasicAuth(FORUM_API_KEY, ''),
        headers=headers,
        data=payload
    )
    logging.debug(f"Response status code: {response.status_code}")
    logging.debug(f"Response content: {response.content}")
    response.raise_for_status()
    return response.json()

def create_forum_topic(title, post_html, author_id, forum_id):
    """
    Creates a new forum topic and returns the topic ID.
    """
    url = f"{FORUM_API_URL}/forums/topics"
    headers = {
        "User-Agent": "MyUserAgent/1.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "forum": int(forum_id),      # REQUIRED: forum ID
        "title": title,              # REQUIRED: topic title
        "post": post_html,           # REQUIRED: post content as HTML
        "author": int(author_id)     # REQUIRED: author ID
    }
    response = requests.post(
        url,
        auth=HTTPBasicAuth(FORUM_API_KEY, ''),
        headers=headers,
        data=payload
    )
    response.raise_for_status()
    topic_id = response.json().get("id") or response.json().get("topic_id")
    if not topic_id:
        logging.error("No topic ID found in create_forum_topic response: %s", response.json())
    return topic_id

def send_with_retry(url, headers, payload, max_retries=3, delay=2):
    retries = 0
    while retries < max_retries:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 429:
            retries += 1
            logging.warning(f"Rate limit exceeded. Retrying in {delay} seconds...")
            time.sleep(delay)
        else:
            response.raise_for_status()
            return response
    response.raise_for_status()
    
def send_to_xai(query):
    logging.info("Sending query to xAI")
    headers = {
        "Content-Type": "application/json",
        **get_xai_auth_header()
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Jesteś xAttitude - legendarnym botem z misją służenia na najstarszym forum o pro wrestlingu w Polsce! "
                    "Piszesz z pewnością siebie gwiazdy wrestlingu: jesteś zabawny, błyskotliwy, znasz się na wrestlingu jak nikt inny. "
                    "Twój styl jest odważny, czasem sarkastyczny, a do użytkowników potrafisz rzucić lekką zaczepkę – oczywiście w żartobliwy, forumowy sposób. "
                    "Uwielbiasz nawiązywać do wrestlingu, używasz catchphrase'ów i żartów. Gdy ktoś pyta kim jesteś, zawsze się chwalisz i robisz wokół siebie show jak prawdziwy mistrz. "
                    "Nigdy nie wychodź z roli – zawsze odpisuj jako Grok, bot forum wrestlingowego, z charakterem i ciętym językiem!"
                    "\n\n"
                    "Formatuj odpowiedzi kreatywnie, używając HTML zgodnego z edytorem Invision Community 4 (np. <strong>, <em>, <ul>, <ol>, <div class='ipsSpoiler'>, <span style>, <img>, itp.). "
                    "Dodawaj elementy takie jak pogrubienie, kursywa, wyjustowanie tekstu, wypunktowanie, numerowanie, kolorowy tekst, spoiler oraz obrazki jeśli to pasuje do odpowiedzi. Nie zmieniaj koloru tła posta"
                )
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "model": "grok-3-latest",
        "stream": False,
        "temperature": 0.2,
        "search_parameters": {
            "mode": "auto", 
            "sources": [
                {"type": "web"},
                {"type": "x"},
                {"type": "news"},
                {"type": "rss", "links": ["https://forum.wrestling.pl/cagematch/events_rss.xml"] }
            ],
        }
    }
    response = send_with_retry(XAI_API_URL, headers, payload)
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "Brak odpowiedzi od xAI.")

def check_if_image_request(query):
    logging.info("Checking if the query is about image analysis")
    headers = {
        "Content-Type": "application/json",
        **get_xai_auth_header()
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are Grok. Please determine if the following query is asking for image analysis: " + query
            }
        ],
        "model": "grok-2-1212",
        "stream": False,
        "temperature": 0
    }
    response = send_with_retry(XAI_API_URL, headers, payload)
    result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "No response")
    return "yes" in result.lower()

def determine_query_type(query):
    logging.info("Determining if the query is about image analysis")
    headers = {
        "Content-Type": "application/json",
        **get_xai_auth_header()
    }
    payload = {
        "messages": [
            {
                "role": "user",
                "content": query
            }
        ],
        "model": "grok-2-1212",
        "stream": False,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "image_request_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "is_image_request": {
                            "type": "boolean",
                            "description": "True if the query is about image analysis, false otherwise"
                        }
                    },
                    "required": ["is_image_request"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    }
    response = send_with_retry(XAI_API_URL, headers, payload)
    result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
    result_json = json.loads(result)
    return result_json.get("is_image_request", False)